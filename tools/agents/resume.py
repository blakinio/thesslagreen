#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import checkpoint

DEFAULT_REQUIRED_READS = ["AGENTS.md", "docs/agents/CONTEXT_HANDOFF.md"]
ROUTING_KEYS = ("required_reads", "search_first", "optional_reads")


def _strip_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _task_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def task_id(path: Path) -> str:
    match = re.search(r"(?m)^task_id:\s*[\"']?([^\"'\n]+)", _task_text(path))
    return match.group(1).strip() if match else path.stem


def read_routing(path: Path) -> dict[str, list[str]]:
    text = _task_text(path)
    routing: dict[str, list[str]] = {key: [] for key in ROUTING_KEYS}
    if not text.startswith("---\n"):
        routing["required_reads"] = list(DEFAULT_REQUIRED_READS)
        return routing
    end = text.find("\n---", 4)
    if end < 0:
        routing["required_reads"] = list(DEFAULT_REQUIRED_READS)
        return routing
    current: str | None = None
    for raw in text[4:end].splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0 and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            current = key if key in routing else None
            if current is not None:
                value = value.strip()
                if value and value != "[]":
                    routing[current].append(_strip_scalar(value))
            continue
        if current is not None and indent >= 2 and stripped.startswith("- "):
            routing[current].append(_strip_scalar(stripped[2:]))
    required = [*DEFAULT_REQUIRED_READS, *routing["required_reads"]]
    routing["required_reads"] = list(dict.fromkeys(required))
    return routing


def build_bundle(path: Path) -> dict[str, object]:
    data = checkpoint.parse_checkpoint(path)
    routing = read_routing(path)
    if data is None:
        return {
            "task_id": task_id(path),
            "checkpoint": str(path),
            **routing,
            "warning": "CHECKPOINT_MISSING",
            "next_action": (
                "Reconstruct and write a valid Context checkpoint from current Git, PR, CI and "
                "task evidence before substantive implementation."
            ),
        }
    errors = checkpoint.validate_checkpoint(data, path)
    if errors:
        raise ValueError("; ".join(errors))
    keys = (
        "head",
        "branch",
        "pr",
        "status",
        "context_routes",
        "proven",
        "derived",
        "unknown",
        "conflicts",
        "first_failure",
        "changed_paths",
        "validation",
        "blockers",
        "next_action",
    )
    return {
        "task_id": task_id(path),
        "checkpoint": str(path),
        **routing,
        **{key: data.get(key) for key in keys},
    }


def _items(data: dict[str, object], key: str) -> list[object]:
    value = data.get(key, [])
    return value if isinstance(value, list) else []


def render_prompt(data: dict[str, object]) -> str:
    lines = [
        f"Continue task {data['task_id']} from repository state.",
        "Do not rely on previous chat history.",
        f"CHECKPOINT: {data['checkpoint']}",
    ]
    if data.get("warning"):
        lines.extend(
            [
                f"WARNING: {data['warning']}",
                f"NEXT_ACTION: {data['next_action']}",
                "Verify live repository state before substantive implementation.",
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            f"HEAD: {data.get('head', 'UNKNOWN')}",
            f"BRANCH: {data.get('branch', 'UNKNOWN')}",
            f"PR: {data.get('pr', 'none')}",
            f"STATUS: {data.get('status', 'UNKNOWN')}",
            "CONTEXT_ROUTES:",
        ]
    )
    lines.extend(f"- {item}" for item in _items(data, "context_routes"))
    lines.append("REQUIRED_READS:")
    lines.extend(f"- {item}" for item in _items(data, "required_reads"))
    lines.append("SEARCH_FIRST:")
    lines.extend(f"- {item}" for item in _items(data, "search_first"))
    lines.append("OPTIONAL_READS_ONLY_IF_BLOCKED:")
    lines.extend(f"- {item}" for item in _items(data, "optional_reads"))
    for label, key in (
        ("PROVEN", "proven"),
        ("DERIVED", "derived"),
        ("UNKNOWN", "unknown"),
        ("CONFLICTS", "conflicts"),
        ("CHANGED_PATHS", "changed_paths"),
        ("BLOCKERS", "blockers"),
    ):
        lines.append(f"{label}:")
        lines.extend(f"- {item}" for item in _items(data, key))
    failure = data.get("first_failure", {})
    if isinstance(failure, dict):
        lines.extend(
            [
                f"FIRST_FAILURE_MARKER: {failure.get('marker', 'none')}",
                f"FIRST_FAILURE_EVIDENCE: {failure.get('evidence', 'none')}",
            ]
        )
    lines.append("VALIDATION:")
    lines.extend(
        f"- {item.get('command', '')}: {item.get('result', '')}; "
        f"evidence={item.get('evidence', '')}"
        for item in _items(data, "validation")
        if isinstance(item, dict)
    )
    lines.extend(
        [
            f"NEXT_ACTION: {data.get('next_action', 'UNKNOWN')}",
            "",
            "OPERATING_RULES:",
            "- Read every REQUIRED_READS path before executing NEXT_ACTION.",
            "- Search SEARCH_FIRST paths before opening large files or indexes in full.",
            "- Open OPTIONAL_READS_ONLY_IF_BLOCKED only when a concrete blocker requires them.",
            "- Treat Git, checkpoint and live PR/CI as source of truth.",
            "- Verify only live state that can invalidate NEXT_ACTION.",
            "- Do not repeat the full preflight when checkpoint and live state agree.",
            "- Do not rediscover PROVEN facts unless live evidence changed.",
            "- Preserve UNKNOWN and CONFLICT; never guess.",
            "- Do not paste full logs, diffs or old chat history.",
            "- Execute NEXT_ACTION autonomously when safe.",
            "- Update the checkpoint and leave exactly one next_action before handing off.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a compact continuation prompt from a task checkpoint"
    )
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = build_bundle(args.task.resolve())
    print(json.dumps(data, indent=2) if args.json else render_prompt(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
