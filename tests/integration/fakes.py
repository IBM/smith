# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Lightweight fakes for the external boundaries unit tests must not cross.

Unit tests run the **real** Smith functions — the real parsers, validators,
routers and file writers. Only the boundary is replaced: the LLM call, the
subprocess, the HTTP request, the embedding model. Replacing the function under
test with a mock would prove nothing, so nothing here does that.

Every Smith module that talks to an LLM does ``from openai import OpenAI`` at
module scope and constructs the client *inside* the function, so the seam is
always the module attribute::

    monkeypatch.setattr(cross_validate, "OpenAI", FakeOpenAI(...))

Design rules:

* **As small as the call site allows.** Each fake models only the attributes and
  methods the production code actually touches — nothing is a general-purpose
  simulation of the real library.
* **Unexpected calls fail.** A fake asked for a response it was not given raises
  ``AssertionError`` rather than returning a benign default, so a test cannot
  silently pass because a fake absorbed a wrong call.
* **No module replacement.** Nothing here touches ``sys.modules``.
"""

from __future__ import annotations

import json
import subprocess


# ===========================================================================
# OpenAI-style chat completions
#
# The only thing a test wants here is "hand back this response string". The
# nesting below exists solely because the production code reaches its answer
# through a construct-then-walk chain that must be satisfied exactly:
#
#     client = OpenAI(base_url=..., http_client=...)
#     client.chat.completions.create(...).choices[0].message.content
#
# So: `OpenAI(...)` must be constructible with those kwargs (they are accepted
# and ignored), `.chat.completions.create` must be callable, and the result must
# expose `.choices[0].message.content`. Nothing more is modelled.
# ===========================================================================


class _Wrap:
    """Builds the .choices[0].message.content chain the code walks."""

    def __init__(self, content: str):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]


class FakeOpenAI:
    """A stand-in for ``openai.OpenAI`` that replays canned responses.

    Patch it over the module attribute the code imported::

        fake = FakeOpenAI(responses=[{"pick": 1}])
        monkeypatch.setattr(classify_guidance, "OpenAI", fake.as_factory())

    ``responses`` entries are returned one per call and may be a ``str``, a
    ``dict``/``list`` (JSON-encoded first), or an ``Exception`` (raised). Pass
    ``error=`` to raise on every call. Running out of responses raises, so an
    unexpected extra call fails the test instead of passing silently.
    """

    def __init__(self, responses=None, error=None, **_ignored_client_kwargs):
        self._responses = list(responses) if responses else []
        self._error = error
        #: Every request, for assertions about what the code actually asked for.
        self.calls: list[dict] = []
        outer = self

        class _Completions:
            def create(self, **kwargs):
                return outer._respond(**kwargs)

        self.chat = type("_Chat", (), {"completions": _Completions()})()

    def as_factory(self):
        """The patch target: production code calls ``OpenAI(...)`` itself.

        Returns this same instance, so a test can inspect ``.calls`` afterwards.
        """
        return lambda *_a, **_kw: self

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def last_prompt(self) -> str:
        """The combined message text of the most recent request."""
        assert self.calls, "no LLM call was made"
        return "\n".join(
            m.get("content", "")
            for m in self.calls[-1].get("messages", [])
            if isinstance(m, dict)
        )

    def model_used(self):
        assert self.calls, "no LLM call was made"
        return self.calls[-1].get("model")

    def _respond(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        if not self._responses:
            raise AssertionError(
                f"FakeOpenAI got an unexpected call #{len(self.calls)} — no "
                "responses left. Add one, or assert the code should not have "
                "called the LLM again."
            )
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, (dict, list)):
            response = json.dumps(response)
        return _Wrap(response)


def fenced(payload) -> str:
    """Wrap a payload in a ```json fence, as real models often reply."""
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, indent=2)
    return f"```json\n{payload}\n```"


# ===========================================================================
# HTTP responses (requests / httpx style)
# ===========================================================================


class FakeHTTPResponse:
    """Implements the two methods Smith actually calls: ``raise_for_status`` and ``json``."""

    def __init__(self, payload=None, status_code: int = 200, text: str = ""):
        self._payload = payload
        self.status_code = status_code
        self.text = text or (json.dumps(payload) if payload is not None else "")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON payload")
        return self._payload


class FakePoster:
    """Stands in for ``requests.post``; records calls, replays queued responses.

    ``responses`` may hold ``FakeHTTPResponse`` objects or exceptions to raise, so
    a test can drive both the success and failure branches of a caller.
    """

    def __init__(self, responses=None):
        self._responses = list(responses) if responses else []
        self.calls: list[dict] = []

    def __call__(self, url, json=None, timeout=None, **kwargs):
        self.calls.append({"url": url, "json": json, "timeout": timeout, **kwargs})
        if not self._responses:
            raise AssertionError(
                f"FakePoster got an unexpected request #{len(self.calls)} to {url}"
            )
        return self._deliver(self._responses.pop(0))

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @staticmethod
    def _deliver(response):
        if isinstance(response, Exception):
            raise response
        return response


# ===========================================================================
# Subprocess boundaries (opa / regal / docker / promptfoo / ares)
# ===========================================================================


class FakeProcess:
    """A ``subprocess.run`` stand-in returning canned ``CompletedProcess`` results.

    ``results`` may hold ``CompletedProcess`` objects, plain ``(returncode, stdout,
    stderr)`` tuples, or exceptions (e.g. ``subprocess.TimeoutExpired``,
    ``FileNotFoundError``) to raise. Every invocation is recorded in ``calls`` so a
    test can assert *which* external command the code chose — and, importantly,
    that an early-exit path launched no tool at all.
    """

    def __init__(self, results=None, by_command=None, default=None):
        self._results = list(results) if results else []
        self._by_command = dict(by_command) if by_command else {}
        self._default = default
        self.calls: list[list] = []

    def __call__(self, args, **kwargs):
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        self.calls.append(argv)
        joined = " ".join(str(a) for a in argv)

        if self._by_command:
            for needle, result in self._by_command.items():
                if needle in joined:
                    return self._deliver(result, argv, kwargs)
        if self._results:
            return self._deliver(self._results.pop(0), argv, kwargs)
        if self._default is not None:
            return self._deliver(self._default, argv, kwargs)
        raise AssertionError(f"FakeProcess got an unexpected command: {joined}")

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def commands(self) -> list[str]:
        return [" ".join(str(a) for a in argv) for argv in self.calls]

    def ran(self, needle: str) -> bool:
        return any(needle in cmd for cmd in self.commands)

    def _deliver(self, result, argv, kwargs):
        if isinstance(result, Exception):
            raise result
        if isinstance(result, subprocess.CompletedProcess):
            return result
        if isinstance(result, tuple):
            code, out, err = (list(result) + ["", ""])[:3]
            return self._completed(argv, code, out, err, kwargs)
        if isinstance(result, int):
            return self._completed(argv, result, "", "", kwargs)
        raise TypeError(f"unsupported FakeProcess result: {result!r}")

    @staticmethod
    def _completed(argv, code, out, err, kwargs):
        # Honour text=False by handing back bytes, as the real call would.
        if kwargs.get("text") is False and isinstance(out, str):
            out, err = out.encode(), err.encode()
        return subprocess.CompletedProcess(argv, code, out, err)


def completed(returncode: int = 0, stdout: str = "", stderr: str = "", args=()):
    """A ready-made ``CompletedProcess``, for readability at call sites."""
    return subprocess.CompletedProcess(list(args), returncode, stdout, stderr)


# ===========================================================================
# Embedding model (sentence-transformers)
# ===========================================================================


class FakeEmbedder:
    """A ``SentenceTransformer`` stand-in whose ``encode()`` returns fixed vectors.

    Lets the real DBSCAN clustering and report-building run offline and
    deterministically, with no model download. Vectors are chosen per input text:

    * ``vectors={substring: [..]}`` — the first matching substring wins.
    * otherwise a deterministic vector derived from the text, so identical texts
      land together and different ones do not.

    Constructing this must not download anything; ``loaded`` records whether the
    model was ever asked to embed, which is how a test proves an empty-input path
    never touched the model.
    """

    def __init__(self, vectors=None, dim: int = 8):
        self._vectors = dict(vectors) if vectors else {}
        self.dim = dim
        self.encoded: list[list[str]] = []

    def __call__(self, *_args, **_kwargs):
        """Allow use as the patched ``SentenceTransformer`` symbol itself."""
        return self

    @property
    def loaded(self) -> bool:
        return bool(self.encoded)

    def encode(self, texts, **_kwargs):
        items = [texts] if isinstance(texts, str) else list(texts)
        self.encoded.append(items)
        return [self._vector_for(t) for t in items]

    def _vector_for(self, text: str):
        for needle, vector in self._vectors.items():
            if needle in text:
                return list(vector)
        # Deterministic fallback: a unit-ish vector seeded from the text, so the
        # same text always embeds identically and unrelated texts stay apart.
        seed = sum(ord(c) for c in text)
        return [((seed >> i) % 7) / 7.0 for i in range(self.dim)]


# ===========================================================================
# Async MCP session (tool discovery)
# ===========================================================================


class FakeTool:
    """An MCP tool object with the attributes ``tool_to_dict`` reads."""

    def __init__(self, name: str, description: str = "", input_schema=None):
        self.name = name
        self.description = description
        self.inputSchema = input_schema or {}  # noqa: N815 - mirrors the SDK


class FakeToolsResponse:
    def __init__(self, tools):
        self.tools = list(tools)


class FakeMCPSession:
    """An ``mcp.ClientSession`` stand-in: no transport, no subprocess."""

    def __init__(self, tools=()):
        self._tools = list(tools)
        self.initialized = False

    async def initialize(self):
        self.initialized = True

    async def list_tools(self):
        assert self.initialized, "list_tools() called before initialize()"
        return FakeToolsResponse(self._tools)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False
