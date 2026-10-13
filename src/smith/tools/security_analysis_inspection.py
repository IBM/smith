# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Deterministic, bounded implementation inspection for security-analysis Phase A."""

from __future__ import annotations

import ast
import json
import re
from collections import deque
from pathlib import Path
from typing import Any

from smith.tools.guidance_reconciliation import ReconciliationError

MAX_IMPLEMENTATION_FILES = 20
MAX_REFERENCE_HOPS = 2

SKIPPED_PARTS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "site-packages",
    "smith_outputs",
    "test_cases",
    "tests",
    "test",
    "vendor",
    "venv",
}
GENERATED_PARTS = {"guidelines-security-analysis"}
SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".ts",
    ".tsx",
}
TEXT_SUFFIXES = SOURCE_SUFFIXES | {
    ".html",
    ".json",
    ".rego",
    ".svelte",
    ".toml",
    ".vue",
    ".yaml",
    ".yml",
}

ROLE_PATTERNS = {
    "tool registration or transport": re.compile(
        r"(?:@[\w.]*tool\b|register_?tool|FastMCP|MCPServer|list_tools|"
        r"tools/(?:call|list)|inputSchema|input_schema)",
        re.IGNORECASE,
    ),
    "prompt construction": re.compile(
        r"(?:system_?prompt|user_?prompt|chat\.completions|messages\s*=|"
        r"generate_content|invoke\s*\()",
        re.IGNORECASE,
    ),
    "runtime context": re.compile(
        r"(?:extensions[.\"']+subject|user_?profile|request_?context|"
        r"session_?id|authorization|jwt|claims)",
        re.IGNORECASE,
    ),
    "policy interception": re.compile(
        r"(?:\bopa\b|\brego\b|policy_?check|policy_?decision|authorize|"
        r"enforcement|intercept)",
        re.IGNORECASE,
    ),
    "external service": re.compile(
        r"(?:https?://|httpx\.|requests\.|fetch\s*\(|axios\.|"
        r"urlopen\s*\(|create_connection|connect\s*\()",
        re.IGNORECASE,
    ),
}


def _is_skipped(relative: Path) -> bool:
    parts = set(relative.parts)
    stem = relative.stem.casefold()
    generated_name = relative.name in {
        "policy_generated.rego",
        "promptfooconfig.yaml",
        "promptfooconfig.yml",
        "system_vars.json",
        "tool_definitions.json",
    }
    return (
        bool(parts & (SKIPPED_PARTS | GENERATED_PARTS))
        or stem.startswith("test_")
        or stem.endswith("_test")
        or "_test_" in stem
        or stem == "conftest"
        or generated_name
    )


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        if path.stat().st_size > 2_000_000:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _schema_type(details: dict[str, Any]) -> str:
    raw_type = details.get("type")
    if isinstance(raw_type, list):
        raw_type = next((item for item in raw_type if item != "null"), "any")
    if raw_type is None and isinstance(details.get("anyOf"), list):
        raw_type = next(
            (
                item.get("type")
                for item in details["anyOf"]
                if isinstance(item, dict) and item.get("type") != "null"
            ),
            "any",
        )
    return str(raw_type or "any")


def _tool_definitions(path: Path) -> tuple[dict[str, dict[str, dict[str, Any]]], dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        tools = payload["tools"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ReconciliationError(
            f"tool definitions are unusable: {path}: {exc}"
        ) from exc
    if not isinstance(tools, list):
        raise ReconciliationError(f"tool definitions have no tools list: {path}")

    declared: dict[str, dict[str, dict[str, Any]]] = {}
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise ReconciliationError(
                f"tool definitions contain an invalid tool: {path}"
            )
        schema = tool.get("input_schema") or {}
        properties = schema.get("properties") if isinstance(schema, dict) else None
        required = schema.get("required", []) if isinstance(schema, dict) else []
        if not isinstance(properties, dict):
            properties = {
                parameter["name"]: {"type": parameter.get("type", "any")}
                for parameter in tool.get("parameters", [])
                if isinstance(parameter, dict)
                and isinstance(parameter.get("name"), str)
            }
            required = [
                parameter["name"]
                for parameter in tool.get("parameters", [])
                if isinstance(parameter, dict)
                and isinstance(parameter.get("name"), str)
                and parameter.get("required") is True
            ]
        declared[tool["name"]] = {
            name: {
                "type": _schema_type(details),
                "required": name in required,
            }
            for name, details in properties.items()
            if isinstance(details, dict)
        }
    return declared, payload


def _annotation_type(annotation: ast.expr | None) -> str:
    if annotation is None:
        return "unknown"
    text = ast.unparse(annotation)
    without_none = re.sub(r"\s*\|\s*None\b|\bNone\s*\|\s*", "", text)
    base = without_none.split("[", 1)[0].split(".")[-1].casefold()
    return {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "tuple": "array",
        "set": "array",
        "dict": "object",
        "mapping": "object",
    }.get(base, "unknown")


def _decorator_is_tool(decorator: ast.expr) -> bool:
    expression = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(expression, ast.Attribute):
        return expression.attr.casefold() in {"tool", "register_tool"}
    return isinstance(expression, ast.Name) and expression.id.casefold() in {
        "tool",
        "register_tool",
    }


def _decorated_tool_name(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    for decorator in node.decorator_list:
        if not _decorator_is_tool(decorator) or not isinstance(decorator, ast.Call):
            continue
        for keyword in decorator.keywords:
            if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, str):
                    return keyword.value.value
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            if isinstance(decorator.args[0].value, str):
                return decorator.args[0].value
    return node.name


def _function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, dict[str, Any]]:
    positional = list(node.args.posonlyargs) + list(node.args.args)
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(
        node.args.defaults
    )
    signature = {
        argument.arg: {
            "type": _annotation_type(argument.annotation),
            "required": default is None,
        }
        for argument, default in zip(positional, defaults)
        if argument.arg not in {"self", "cls"}
    }
    for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        signature[argument.arg] = {
            "type": _annotation_type(argument.annotation),
            "required": default is None,
        }
    return signature


def _schema_signature(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict):
        return {}
    return {
        name: {
            "type": _schema_type(details),
            "required": name in required,
        }
        for name, details in properties.items()
        if isinstance(details, dict)
    }


def _registry_tools(tree: ast.AST) -> dict[str, dict[str, dict[str, Any]]]:
    tools: dict[str, dict[str, dict[str, Any]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            _decorator_is_tool(decorator) for decorator in node.decorator_list
        ):
            tools[_decorated_tool_name(node)] = _function_signature(node)
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        try:
            literal = ast.literal_eval(value)
        except (ValueError, TypeError):
            continue
        if not isinstance(literal, list):
            continue
        for item in literal:
            if not isinstance(item, dict):
                continue
            function = item.get("function", item)
            if not isinstance(function, dict) or not isinstance(
                function.get("name"), str
            ):
                continue
            schema = function.get("parameters") or function.get("input_schema") or {}
            if isinstance(schema, dict):
                tools[function["name"]] = _schema_signature(schema)
    return tools


def _python_references(path: Path, text: str, target: Path) -> set[Path]:
    if path.suffix != ".py":
        return set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    references: set[Path] = set()
    for node in ast.walk(tree):
        modules: list[tuple[str, int]] = []
        if isinstance(node, ast.Import):
            modules = [(alias.name, 0) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [(node.module, node.level)]
        for module, level in modules:
            base = path.parent
            for _ in range(max(level - 1, 0)):
                base = base.parent
            module_path = Path(*module.split("."))
            candidates = (
                base / module_path.with_suffix(".py"),
                base / module_path / "__init__.py",
            )
            for candidate in candidates:
                try:
                    candidate.relative_to(target)
                except ValueError:
                    continue
                if candidate.is_file():
                    references.add(candidate)
    return references


def _relative_references(path: Path, text: str, target: Path) -> set[Path]:
    references = _python_references(path, text, target)
    for raw in re.findall(
        r"(?:from\s+|require\s*\(|import\s+)[\"'](\.{1,2}/[^\"']+)", text
    ):
        base = path.parent / raw
        for candidate in (
            base,
            *(base.with_suffix(suffix) for suffix in SOURCE_SUFFIXES),
        ):
            try:
                resolved = candidate.resolve().relative_to(target.resolve())
            except ValueError:
                continue
            full_path = target / resolved
            if full_path.is_file():
                references.add(full_path)
                break
    return references


def _source_hint(payload: dict, inventory: list[Path], target: Path) -> Path | None:
    source = str(payload.get("source", ""))
    for path in inventory:
        relative = path.relative_to(target).as_posix()
        if relative in source or path.name in source:
            return path
    return None


def _signature_comparison(
    declared: dict[str, dict[str, dict[str, Any]]],
    selected: list[Path],
    authoritative_source: Path | None,
    target: Path,
) -> dict[str, Any]:
    registered: dict[str, dict[str, dict[str, Any]]] = {}
    sources: dict[str, str] = {}
    parse_files = [authoritative_source] if authoritative_source else selected
    for path in parse_files:
        if path is None or path.suffix != ".py":
            continue
        text = _read_text(path)
        if text is None:
            continue
        try:
            found = _registry_tools(ast.parse(text))
        except SyntaxError:
            continue
        for name, signature in found.items():
            registered[name] = signature
            sources[name] = path.relative_to(target).as_posix()

    comparison = {
        "status": "UNKNOWN",
        "authoritative_source": (
            authoritative_source.relative_to(target).as_posix()
            if authoritative_source
            else None
        ),
        "declared_tools": sorted(declared),
        "registered_tools": sorted(registered),
        "missing": [],
        "extra": [],
        "incompatible": [],
        "unknown": [],
        "sources": sources,
    }
    if not registered:
        comparison["unknown"] = sorted(declared)
        return comparison

    declared_names = set(declared)
    registered_names = set(registered)
    comparison["missing"] = sorted(declared_names - registered_names)
    comparison["extra"] = sorted(registered_names - declared_names)
    for name in sorted(declared_names & registered_names):
        expected = declared[name]
        actual = registered[name]
        if set(expected) != set(actual):
            comparison["incompatible"].append(
                {
                    "tool": name,
                    "expected_parameters": sorted(expected),
                    "registered_parameters": sorted(actual),
                }
            )
            continue
        differences = []
        for parameter in sorted(expected):
            expected_parameter = expected[parameter]
            actual_parameter = actual[parameter]
            if expected_parameter["required"] != actual_parameter["required"]:
                differences.append(
                    f"{parameter}: required={actual_parameter['required']} "
                    f"(expected {expected_parameter['required']})"
                )
            actual_type = actual_parameter["type"]
            expected_type = expected_parameter["type"]
            if (
                actual_type not in {"unknown", "any"}
                and expected_type
                not in {
                    "unknown",
                    "any",
                }
                and actual_type != expected_type
            ):
                differences.append(
                    f"{parameter}: type={actual_type} (expected {expected_type})"
                )
        if differences:
            comparison["incompatible"].append(
                {"tool": name, "differences": differences}
            )

    proven_complete = authoritative_source is not None
    if comparison["incompatible"] or (
        proven_complete and (comparison["missing"] or comparison["extra"])
    ):
        comparison["status"] = "FAIL"
    elif comparison["missing"] or comparison["extra"]:
        comparison["status"] = "UNKNOWN"
        comparison["unknown"] = sorted(
            set(comparison["missing"]) | set(comparison["extra"])
        )
    else:
        comparison["status"] = "PASS"
    return comparison


def inspect_architecture(
    target: Path,
    tool_definitions_path: Path,
    output_path: Path,
    *,
    max_files: int = MAX_IMPLEMENTATION_FILES,
    max_hops: int = MAX_REFERENCE_HOPS,
) -> str:
    """Select bounded implementation evidence and compare static tool signatures."""
    if max_files < 1 or max_hops < 0:
        raise ReconciliationError("inspection limits must be positive")
    if not target.is_dir():
        raise ReconciliationError(f"target agent path is missing: {target}")
    declared, definitions_payload = _tool_definitions(tool_definitions_path)

    inventory: list[Path] = []
    texts: dict[Path, str] = {}
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(target)
        if _is_skipped(relative):
            continue
        text = _read_text(path)
        if text is None:
            continue
        inventory.append(path)
        texts[path] = text

    authoritative_source = _source_hint(definitions_payload, inventory, target)
    findings: dict[Path, dict[str, Any]] = {}
    tool_patterns = {
        name: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
        for name in declared
    }
    for path in inventory:
        text = texts[path]
        matched_tools = sorted(
            name for name, pattern in tool_patterns.items() if pattern.search(text)
        )
        roles = sorted(
            name for name, pattern in ROLE_PATTERNS.items() if pattern.search(text)
        )
        if not matched_tools and not roles and path != authoritative_source:
            continue
        findings[path] = {
            "path": path.relative_to(target).as_posix(),
            "hop": 0,
            "matched_tools": matched_tools,
            "roles": roles,
            "authoritative_tool_source": path == authoritative_source,
        }

    ordered_seeds = sorted(
        findings,
        key=lambda path: (
            not findings[path]["authoritative_tool_source"],
            -len(findings[path]["matched_tools"]),
            -len(findings[path]["roles"]),
            findings[path]["path"],
        ),
    )
    selected: list[Path] = []
    selected_set: set[Path] = set()
    unresolved: set[str] = set()
    for seed in ordered_seeds:
        queue = deque([(seed, 0)])
        while queue:
            path, hop = queue.popleft()
            if path in selected_set:
                continue
            if len(selected) >= max_files:
                unresolved.add(path.relative_to(target).as_posix())
                continue
            selected.append(path)
            selected_set.add(path)
            unresolved.discard(path.relative_to(target).as_posix())
            if hop >= max_hops:
                unresolved.update(
                    reference.relative_to(target).as_posix()
                    for reference in _relative_references(
                        path, texts.get(path, ""), target
                    )
                    if reference not in selected_set
                    and not _is_skipped(reference.relative_to(target))
                )
                continue
            for reference in sorted(
                _relative_references(path, texts.get(path, ""), target)
            ):
                if _is_skipped(reference.relative_to(target)):
                    continue
                if reference not in texts:
                    text = _read_text(reference)
                    if text is None:
                        continue
                    texts[reference] = text
                findings.setdefault(
                    reference,
                    {
                        "path": reference.relative_to(target).as_posix(),
                        "hop": hop + 1,
                        "matched_tools": [],
                        "roles": [
                            f"referenced by {path.relative_to(target).as_posix()}"
                        ],
                        "authoritative_tool_source": reference == authoritative_source,
                    },
                )
                findings[reference]["hop"] = min(findings[reference]["hop"], hop + 1)
                queue.append((reference, hop + 1))

    comparison = _signature_comparison(declared, selected, authoritative_source, target)
    report = {
        "schema": "security-analysis-inspection-v1",
        "target": str(target),
        "tool_definitions": str(tool_definitions_path),
        "limits": {"max_files": max_files, "max_reference_hops": max_hops},
        "inventory": {
            "text_files_scanned": len(inventory),
            "relevant_files_found": len(findings),
        },
        "selected_files": [findings[path] for path in selected],
        "unresolved_relevant_paths": sorted(unresolved),
        "tool_signature_comparison": comparison,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    summary = (
        f"Security analysis inspection {comparison['status']}: "
        f"{len(selected)}/{max_files} implementation files selected; "
        f"report: {output_path}"
    )
    if comparison["status"] == "FAIL":
        raise ReconciliationError(summary)
    return summary
