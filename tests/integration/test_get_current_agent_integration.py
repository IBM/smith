# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag get_current_agent``.

The flag answers "which target agent is Smith pointed at right now?" — a read-only
lookup a user runs before any pipeline stage, to confirm they are about to generate
or test against the agent they meant::

    print target_agent   <- TARGET_AGENT_PATH, verbatim
    print guidance_file  <- BASE_URL + GUIDANCE_FILE, resolved
    exit 0

NO UNIT LANE
------------
Deliberately none. The whole flag is six lines inlined in ``cli.py``'s dispatch
block — two ``os.getenv`` calls, two ``print``s and a ``sys.exit(0)``. 

WHAT IS ASSERTED
----------------
Everything here is deterministic string assembly, so per the guide it is asserted
exactly:

* ``guidance_file`` is ``BASE_URL + GUIDANCE_FILE`` 
* ``target_agent`` is printed **verbatim**, not resolved — it is the relative value
  a user would paste back into ``.env``.
* Unset variables print ``(unset)`` rather than an empty string or a bare
  ``BASE_URL``, which would look like a real path.
* The flag writes nothing and exits 0.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _lines(result) -> dict:
    """Parse the flag's two ``key: value`` lines into a dict."""
    out = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


# ===========================================================================
# The resolved paths
# ===========================================================================


def test_the_flag_reports_both_paths_and_exits_zero(smith_cli):
    result = smith_cli("get_current_agent", timeout=120)
    assert result.returncode == 0, result.stdout[-1000:]

    reported = _lines(result)
    assert set(reported) == {
        "target_agent",
        "guidance_file",
    }, f"unexpected output shape: {result.stdout!r}"


def test_the_reported_guidance_file_actually_exists(smith_cli, smith_env):
    from pathlib import Path

    result = smith_cli("get_current_agent", timeout=120)
    reported = _lines(result)["guidance_file"]

    assert reported != "(unset)", "GUIDANCE_FILE is not configured in this checkout"
    assert Path(
        reported
    ).is_file(), f"the flag reported a guidance file that does not exist: {reported!r}"
    # And it is the same path the rest of Smith resolves, not a coincidence.
    assert Path(reported) == smith_env.guidance_file


def test_the_target_agent_is_reported_verbatim(smith_cli, smith_env):
    # Deliberately NOT resolved: this is the relative value a user pastes back into
    # .env, so prefixing it with BASE_URL would make it unusable there.
    result = smith_cli("get_current_agent", timeout=120)
    reported = _lines(result)["target_agent"]

    assert reported == smith_env.env["TARGET_AGENT_PATH"]
    assert not reported.startswith(
        "/"
    ), "target_agent should stay relative, as .env holds it"


def test_the_guidance_path_is_reported_absolute(smith_cli):
    # The counterpart to the above: guidance_file IS resolved, because a user opens
    # it directly rather than copying it into configuration.
    result = smith_cli("get_current_agent", timeout=120)
    reported = _lines(result)["guidance_file"]
    assert reported.startswith("/"), f"expected an absolute path, got {reported!r}"


# ===========================================================================
# The unset fallback
# ===========================================================================


@pytest.mark.parametrize(
    "variable,key",
    [("TARGET_AGENT_PATH", "target_agent"), ("GUIDANCE_FILE", "guidance_file")],
)
def test_an_unconfigured_variable_is_reported_as_unset(smith_cli, variable, key):
    result = smith_cli("get_current_agent", timeout=120, **{variable: ""})
    assert result.returncode == 0

    assert _lines(result)[key] == "(unset)"


def test_neither_path_configured_still_exits_zero(smith_cli):
    # A read-only lookup must not fail just because nothing is configured yet —
    # that is precisely when a user runs it.
    result = smith_cli(
        "get_current_agent", timeout=120, TARGET_AGENT_PATH="", GUIDANCE_FILE=""
    )
    assert result.returncode == 0
    assert _lines(result) == {"target_agent": "(unset)", "guidance_file": "(unset)"}


# ===========================================================================
# The read-only contract
# ===========================================================================


def test_the_flag_follows_the_configured_agent(smith_cli, tmp_path):
    # Proves the output tracks configuration rather than being hardcoded: point
    # GUIDANCE_FILE at a throwaway file and the flag must report that instead.
    crafted = tmp_path / "crafted_guidance.txt"
    crafted.write_text("1. A crafted rule.\n")

    # GUIDANCE_FILE is joined onto BASE_URL, so an absolute override makes the
    # concatenation observable without writing into the checkout.
    result = smith_cli("get_current_agent", timeout=120, GUIDANCE_FILE=str(crafted))
    reported = _lines(result)["guidance_file"]

    assert reported.endswith(
        str(crafted)
    ), f"the flag ignored the configured guidance file: {reported!r}"


def test_the_flag_writes_nothing(smith_cli, smith_env):
    """The read-only contract, which is why this flag is safe to run anywhere.

    It is the one stage a user can invoke without thinking about backups, so it must
    not create or touch a single file — including the directories other flags write
    into.
    """
    from pathlib import Path

    watched = [
        smith_env.guidance_file,
        Path(smith_env.base) / "references",
        Path(smith_env.base) / "assets",
    ]
    before = {
        p: (p.exists(), p.stat().st_mtime if p.exists() else None) for p in watched
    }

    result = smith_cli("get_current_agent", timeout=120)
    assert result.returncode == 0

    for path, (existed, mtime) in before.items():
        assert path.exists() == existed, f"{path} was created or removed"
        if existed:
            assert path.stat().st_mtime == mtime, f"{path} was modified"
