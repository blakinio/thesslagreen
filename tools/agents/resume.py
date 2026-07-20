#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import checkpoint


def task_id(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^task_id:\s*[\"']?([^\"'\n]+)", text)
    return match.group(1).strip() if match else path.stem


def build_bundle(path: Path) -> dict[str, object]:
    data = checkpoint.parse_checkpoint(path)
    if data is None:
        return {
            "task_id": task_id(path),
            "checkpoint": str(path),
            "warning": "CHECKPOINT_MISSING",
            "next_action": (
                "Reconstruct and write a valid Context checkpoint from current "
                "Git, PR, CI and task evidence before substantive implementation."
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
        **{key: data.get(key) for key in keys},
    }


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
        ]
    )

    for label, key in (
        ("PROVEN", "proven"),
        ("DERIVED", "derived"),
        ("UNKNOWN", "unknown"),
        ("CONFLICTS", "conflicts"),
        ("CHANGED_PATHS", "changed_paths"),
        ("BLOCKERS", "blockers"),
    ):
        lines.append(f"{label}:")
        lines.extend(f"- {item}" for item in data.get(key, []))

    first_failure = data.get("first_failure", {})
    if isinstance(first_failure, dict):
        lines.extend(
            [
                f"FIRST_FAILURE_MARKER: {first_failure.get('marker', 'none')}",
                f"FIRST_FAILURE_EVIDENCE: {first_failure.get('evidence', 'none')}",
            ]
        )

    lines.append("VALIDATION:")
    lines.extend(
        f"- {item.get('command', '')}: {item.get('result', '')}; "
        f"evidence={item.get('evidence', '')}"
        for item in data.get("validation", [])
        if isinstance(item, dict)
    )

    lines.extend(
        [
            f"NEXT_ACTION: {data.get('next_action', 'UNKNOWN')}",
            "",
            "OPERATING_RULES:",
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
