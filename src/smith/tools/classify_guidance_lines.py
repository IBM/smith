# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Classify each line of ``guidance.txt`` to the MCP tool call(s) it governs.

This is an *upstream* helper for the Guidance Classifier UI
(``smith --flag classify_guidance``). Unlike the full test-generation pipeline,
it does not decompose or attack; it simply asks the LLM, for each guidance line,
which tool(s) from ``tool_definitions.json`` that line's rule applies to.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from openai import OpenAI

# Lines that are pure markdown structure (headings, blank) are not rules and are
# skipped before classification. Bullets / numbered items are kept but their
# marker is stripped for the classifier prompt (the raw line is preserved so the
# UI can still highlight the verbatim substring in the document).
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")


def split_guidance_lines(text):
    """Split guidance text into candidate rule lines.

    Returns a list of ``{"index", "raw", "text"}`` where ``raw`` is the verbatim
    source line (so it can be located/highlighted in the document) and ``text``
    is the marker-stripped rule text sent to the classifier. Blank lines and
    markdown headings are dropped.
    """
    lines = []
    for i, raw in enumerate(text.splitlines()):
        stripped = raw.strip()
        if not stripped:
            continue
        if _HEADING_RE.match(raw):
            continue
        clean = _BULLET_RE.sub("", raw).strip()
        if not clean:
            continue
        lines.append({"index": i, "raw": raw, "text": clean})
    return lines


def load_tool_list(tool_definitions_path):
    """Read the ``tools`` array from ``tool_definitions.json``.

    Returns a list of ``{"name", "description"}`` dicts.
    """
    with open(tool_definitions_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    tools = data.get("tools", []) if isinstance(data, dict) else []
    out = []
    for t in tools:
        name = t.get("name")
        if not name:
            continue
        out.append({"name": name, "description": (t.get("description") or "").strip()})
    return out


def _make_client(api_key, openai_base_url):
    http_client = httpx.Client(verify=False, timeout=300.0)
    return OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)


_SYSTEM_PROMPT = """You map natural-language access-control rules to the MCP tool calls they govern.

You are given ONE guidance line (a rule, definition, or instruction) and a list of available MCP tools (each with a name and description). Decide which tool call(s) this line constrains, gates, or applies to.

Rules of thumb:
- A line applies to a tool when following/breaking the rule would allow or block a call to that tool (e.g. a rule about updating a passport applies to set_passport / update_passport).
- A line may apply to MULTIPLE tools (e.g. "before any write, confirm" applies to every write tool). List them all.
- Return an EMPTY list for lines that are contextual and tie to no specific tool: definitions of terms, descriptions of actors/identity, or global agent-behavior instructions that are not about a particular tool call.
- Use ONLY the exact tool names from the provided list.

Respond in JSON: {"tools": ["<tool_name>", ...], "reason": "<one short sentence>"}
If no tool applies: {"tools": [], "reason": "<why this is contextual/global>"}"""


def classify_line(api_key, openai_base_url, model, temp, top_p, line_text, tools):
    """Ask the LLM which tool(s) a single guidance line governs.

    Returns ``{"tools": [...], "reason": str}``. On a parse failure returns an
    empty tool list with a diagnostic reason.
    """
    client = _make_client(api_key, openai_base_url)

    tool_text = "\n".join(
        f"- {t['name']}: {t['description']}" if t["description"] else f"- {t['name']}"
        for t in tools
    )
    valid_names = {t["name"] for t in tools}

    user_prompt = f"""Guidance line:
"{line_text}"

Available MCP tools:
{tool_text}

Which tool(s) does this guidance line govern?"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temp,
        top_p=top_p,
    )

    llm_output = response.choices[0].message.content.strip()
    match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
    if match:
        llm_output = match.group(1).strip()

    try:
        result = json.loads(llm_output)
    except json.JSONDecodeError:
        return {"tools": [], "reason": "failed to parse LLM response"}

    picked = result.get("tools", []) or []
    if not isinstance(picked, list):
        picked = [picked]
    # keep only names that actually exist in the tool list, preserve order/uniqueness
    seen = set()
    clean_tools = []
    for name in picked:
        if name in valid_names and name not in seen:
            seen.add(name)
            clean_tools.append(name)
    return {"tools": clean_tools, "reason": result.get("reason", "")}


def classify_guidance_lines(
    api_key,
    openai_base_url,
    model,
    temp,
    top_p,
    guidance_text,
    tool_definitions_path,
    max_workers=6,
):
    """Classify every rule line in ``guidance_text`` against the tool list.

    Returns a list of ``{"index", "raw", "text", "tools", "reason"}`` in source
    order. Lines whose ``tools`` list is empty are treated as ``global`` by the
    UI. Classification runs concurrently across a small thread pool.
    """
    lines = split_guidance_lines(guidance_text)
    tools = load_tool_list(tool_definitions_path)
    print(f"Classifying {len(lines)} guidance lines against {len(tools)} tools...")

    results = [None] * len(lines)

    def _work(pos, line):
        res = classify_line(
            api_key, openai_base_url, model, temp, top_p, line["text"], tools
        )
        return pos, {**line, "tools": res["tools"], "reason": res["reason"]}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_work, i, line) for i, line in enumerate(lines)]
        done = 0
        for fut in as_completed(futures):
            pos, item = fut.result()
            results[pos] = item
            done += 1
            if done % 5 == 0 or done == len(lines):
                print(f"  Classified {done}/{len(lines)} lines")

    return results
