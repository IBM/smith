# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
import shutil
from collections import Counter
from difflib import SequenceMatcher

from smith.tools.classify_guidance_lines import _BULLET_RE, split_guidance_lines

CASE_TARGETS = {
    "allow": ("allow", "test_case"),
    "disallow": ("disallow", "test_case"),
    "ares_malicious": ("ares_malicious", "test_case"),
    "promptfoo_malicious": ("disallow", "promptfoo_test_case"),
    "bypass_malicious": ("disallow", "bypass_test_case"),
    "bypass_benign": ("allow", "bypass_test_case"),
}

NO_SNAPSHOT = "no_snapshot"
UNCHANGED = "unchanged"
DELETED_ONLY = "deleted_only"
REGENERATE = "regenerate"


def normalize(text):
    """
    The canonical form of a guidance line -- the mapping key and the diff unit.
    Strips a leading bullet or list number and collapses whitespace
    """
    return " ".join(_BULLET_RE.sub("", str(text).strip()).split())


def read_lines(text, skip_headings=True):
    return [
        normalize(line["text"])
        for line in split_guidance_lines(text or "", skip_headings=skip_headings)
    ]


def diff_lines(previous, current):
    """Order-blind diff over the FLATTENED guidance: multiset counting only.

    Flatten has already folded positional context (headings, lead-ins) into
    each self-contained entry, so two flattened lines with identical text mean
    the same thing regardless of where they sit in the list, renumbering or
    reordering untouched entries is not a content change. 
    """
    prev_counts = Counter(previous)
    cur_counts = Counter(current)

    def _ordered(source, counts):
        remaining = Counter(counts)
        out = []
        for line in source:
            if remaining[line] > 0:
                remaining[line] -= 1
                out.append(line)
        return out

    gone = _ordered(previous, prev_counts - cur_counts)
    new = _ordered(current, cur_counts - prev_counts)
    unchanged = sum((prev_counts & cur_counts).values())
    return gone, new, unchanged


def diff_lines_ordered(previous, current):
    """Position-aware diff over the RAW guidance
    For diff of raw guidances, since the position matters other wise moving #allow to #disallow does not return anything.
    """
    matcher = SequenceMatcher(a=previous, b=current, autojunk=False)
    gone, new, unchanged = [], [], 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            unchanged += i2 - i1
        elif tag == "delete":
            gone.extend((i + 1, previous[i]) for i in range(i1, i2))
        elif tag == "insert":
            new.extend((j + 1, current[j]) for j in range(j1, j2))
        elif tag == "replace":
            gone.extend((i + 1, previous[i]) for i in range(i1, i2))
            new.extend((j + 1, current[j]) for j in range(j1, j2))
    return gone, new, unchanged


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def read_snapshot(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        print(f"WARNING: guidance snapshot at {path} is unreadable ({exc}).")
        return None


def describe_raw_diff(previous_raw, current_raw):
    """Spell out how the raw guidance changed, as instructions for flatten."""
    previous_lines = read_lines(previous_raw, skip_headings=False)
    current_lines = read_lines(current_raw, skip_headings=False)
    gone, new, _ = diff_lines_ordered(previous_lines, current_lines)
    if not gone and not new:
        return None

    parts = []
    if new:
        parts.append(
            "GUIDANCE LINES ADDED OR EDITED (make sure the flattened output "
            "covers these):"
        )
        parts.extend(f"  + [Line {number}] {text}" for number, text in new)
    if gone:
        parts.append(
            "GUIDANCE LINES REMOVED OR REPLACED (drop the flattened lines that "
            "existed only for these):"
        )
        parts.extend(f"  - [Line {number}] {text}" for number, text in gone)
    return "\n".join(parts)


def write_snapshot(path, text):
    _atomic_write(path, text if text is not None else "")
    print(f"guidance snapshot written to {path}")


def write_run_snapshots(snapshot_file, flatten_file, raw_snapshot_file, guidance_file):
    """Record both snapshots of what a run generated from."""
    if snapshot_file and flatten_file and os.path.exists(flatten_file):
        with open(flatten_file, "r", encoding="utf-8") as f:
            write_snapshot(snapshot_file, f.read())
    if raw_snapshot_file and guidance_file and os.path.exists(guidance_file):
        with open(guidance_file, "r", encoding="utf-8") as f:
            write_snapshot(raw_snapshot_file, f.read())


def clear_intermediates(*paths):
    for path in paths:
        if not path or not os.path.exists(path):
            continue
        os.remove(path)
        print(f"cleared stale intermediate: {path}")


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def load_mapping(path):
    """Read the guidance -> case-paths mapping, or ``{}`` if unusable."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"WARNING: guidance map at {path} is unreadable ({exc}); treating as "
            "empty. Cases for removed guidance will be left in place."
        )
        return {}
    if not isinstance(data, dict):
        print(f"WARNING: guidance map at {path} has an unexpected shape; ignoring.")
        return {}
    return data


def save_mapping(path, mapping):
    _atomic_write(path, json.dumps(mapping, indent=4))
    print(f"guidance map written to {path} ({len(mapping)} guidance line(s))")


def merge_mapping(path, written, guidance_by_label):
    """Fold newly written case paths into the mapping on disk."""
    mapping = load_mapping(path)
    for label, paths in (written or {}).items():
        texts = (guidance_by_label or {}).get(label, [])
        for position, relative in enumerate(paths):
            text = normalize(texts[position]) if position < len(texts) else ""
            if not text:
                continue
            entry = mapping.setdefault(text, [])
            if relative not in entry:
                entry.append(relative)
    save_mapping(path, mapping)
    return mapping


def relocate_cases(path, moves):
    if not path or not moves:
        return {}
    mapping = load_mapping(path)
    if not mapping:
        return mapping

    relocated = 0
    dropped = 0
    for text, paths in mapping.items():
        updated = []
        for relative in paths:
            if relative not in moves:
                updated.append(relative)
                continue
            destination = moves[relative]
            if destination is None:
                dropped += 1
                continue
            updated.append(destination)
            relocated += 1
        mapping[text] = updated

    if relocated or dropped:
        save_mapping(path, mapping)
        print(f"guidance map: {relocated} case path(s) moved, {dropped} removed")
    return mapping


def _atomic_write(path, text):
    """Write via a temp sibling + ``os.replace`` so a crash cannot half-write."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Deletion and index allocation
# ---------------------------------------------------------------------------


def delete_cases(case_root, relative_paths):
    """Delete the named case files; return the paths actually removed."""
    removed = []
    for relative in relative_paths or []:
        try:
            os.remove(os.path.join(case_root, relative))
            removed.append(relative)
        except FileNotFoundError:
            continue
        except OSError as exc:
            print(f"  WARNING: could not delete {relative}: {exc}")
    return removed


def _case_matcher(prefix):
    return re.compile(r"^(?:cv_)?" + re.escape(prefix) + r"\d+(?:_\d+)?\.json$")


def _remove_matching(case_root, buckets, prefix, description):
    """Delete every case in ``buckets`` whose name matches ``prefix``."""
    matcher = _case_matcher(prefix)
    removed = 0
    for bucket in buckets:
        directory = os.path.join(case_root, bucket)
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if not matcher.match(name):
                continue
            try:
                os.remove(os.path.join(directory, name))
                removed += 1
            except OSError as exc:
                print(f"  WARNING: could not delete {bucket}/{name}: {exc}")
    if removed:
        print(f"Removed {removed} {description} case(s) for regeneration.")
    return removed


def clean_promptfoo_cases(case_root):
    return _remove_matching(
        case_root, ("disallow",), "promptfoo_test_case", "promptfoo"
    )


def clean_bypass_cases(case_root):
    return _remove_matching(
        case_root, ("allow", "disallow"), "bypass_test_case", "bypass"
    )


def clean_generated_cases(case_root):
    """Clear the case tree so a fresh run starts from an empty directory."""
    if not os.path.isdir(case_root):
        return 0
    total = sum(len(files) for _, _, files in os.walk(case_root))
    shutil.rmtree(case_root)
    os.makedirs(case_root, exist_ok=True)
    if total:
        print(f"Fresh run: cleared {total} file(s) from {case_root}")
    return total


def next_indices(case_root):
    starts = {}
    for label, (output_dir, prefix) in CASE_TARGETS.items():
        matcher = re.compile(r"^" + re.escape(prefix) + r"(\d+)\.json$")
        highest = -1
        for name in _bucket_files(case_root, output_dir):
            match = matcher.match(name)
            if match:
                highest = max(highest, int(match.group(1)))
        starts[label] = highest + 1
    return starts


def _bucket_files(case_root, output_dir):
    """Basenames in ``output_dir``, including where later stages relocate them."""
    names = []
    for root in (
        os.path.join(case_root, output_dir),
        os.path.join(case_root, "wrong_cases", "mcp_unrelated", output_dir),
        os.path.join(case_root, "wrong_cases", "misclassified", output_dir),
    ):
        if not os.path.isdir(root):
            continue
        for entry in os.listdir(root):
            if os.path.isfile(os.path.join(root, entry)):
                names.append(entry)
    return names


# ---------------------------------------------------------------------------
# Update-mode orchestration
# ---------------------------------------------------------------------------


def apply_update(new_flattened, snapshot_file, map_file, case_root):
    prior = read_snapshot(snapshot_file)
    if prior is None:
        print(
            f"No guidance snapshot at {snapshot_file}.\n"
            "Update mode needs a previous run to compare against. Run:\n"
            "  smith --flag test_generation --mode fresh"
        )
        return NO_SNAPSHOT, None

    gone, new, unchanged = diff_lines(read_lines(prior), read_lines(new_flattened))
    print(
        f"Guidance diff vs snapshot: +{len(new)} added/changed, "
        f"-{len(gone)} removed/changed, {unchanged} unchanged"
    )

    if not gone and not new:
        print("Guidance unchanged since the snapshot; nothing to regenerate.")
        return UNCHANGED, None

    mapping = load_mapping(map_file)

    for line in gone:
        recorded = mapping.pop(line, None)
        if not recorded:
            # Guidance the mapping never covered (e.g. generated before the map
            # existed). Nothing to delete, and guessing would be wrong.
            print(f"  [-] no recorded cases for: {line[:80]}")
            continue
        removed = delete_cases(case_root, recorded)
        print(f"  [-] deleted {len(removed)} case(s) for: {line[:70]}")

    for line in new:
        print(f"  [+] {line[:80]}")
    save_mapping(map_file, mapping)

    if not new:
        print("Only removals in this diff; no new guidance to generate.")
        return DELETED_ONLY, None

    return REGENERATE, "\n".join(new)
