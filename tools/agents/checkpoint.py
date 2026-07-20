#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CHECKPOINT_HEADING = "## Context checkpoint"
LIST_KEYS = {
    "context_routes",
    "owned_paths",
    "proven",
    "derived",
    "unknown",
    "conflicts",
    "rejected_hypotheses",
    "changed_paths",
    "blockers",
}
PLACEHOLDER_NEXT_ACTIONS = {
    "",
    "none",
    "unknown",
    "pending",
    "n/a",
    "tbd",
    "todo",
    "later",
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_contract() -> dict[str, object]:
    path = repository_root() / "docs/agents/GOVERNANCE_CONTRACT.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    contract = raw["shared_checkpoint_contract"]
    if not isinstance(contract, dict):
        raise ValueError(f"{path}: invalid shared checkpoint contract")
    return contract


def scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_checkpoint(path: Path) -> dict[str, object] | None:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^## Context checkpoint\s*$", text))
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"{path}: expected exactly one {CHECKPOINT_HEADING} section")

    remainder = text[matches[0].end() :]
    next_heading = re.search(r"(?m)^##\s+", remainder)
    section = remainder[: next_heading.start()] if next_heading else remainder
    fence = re.search(r"```(?:yaml|yml)\s*\n", section, re.IGNORECASE)
    if not fence:
        raise ValueError(f"{path}: checkpoint has no fenced YAML block")

    block_end = section.find("```", fence.end())
    if block_end < 0:
        raise ValueError(f"{path}: checkpoint fence is not closed")

    data: dict[str, object] = {}
    current_key: str | None = None
    current_validation: dict[str, str] | None = None

    for line_number, raw in enumerate(section[fence.end() : block_end].splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()

        if indent == 0:
            if ":" not in line:
                raise ValueError(f"{path}:{line_number}: invalid checkpoint line")
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in data:
                raise ValueError(f"{path}:{line_number}: duplicate key {key}")

            current_key = key
            current_validation = None
            if key in LIST_KEYS or key == "validation":
                if value not in {"", "[]"}:
                    raise ValueError(f"{path}:{line_number}: {key} must be a YAML list")
                data[key] = []
            elif key == "first_failure":
                if value:
                    raise ValueError(f"{path}:{line_number}: first_failure must be a mapping")
                data[key] = {}
            else:
                data[key] = scalar(value)
            continue

        if current_key in LIST_KEYS:
            if indent != 2 or not line.startswith("- "):
                raise ValueError(f"{path}:{line_number}: invalid list item under {current_key}")
            values = data[current_key]
            assert isinstance(values, list)
            values.append(scalar(line[2:]))
            continue

        if current_key == "first_failure":
            if indent != 2 or ":" not in line:
                raise ValueError(f"{path}:{line_number}: invalid first_failure item")
            key, value = line.split(":", 1)
            mapping = data[current_key]
            assert isinstance(mapping, dict)
            mapping[key.strip()] = scalar(value)
            continue

        if current_key == "validation":
            items = data[current_key]
            assert isinstance(items, list)
            if indent == 2 and line.startswith("- "):
                item = line[2:].strip()
                if ":" not in item:
                    raise ValueError(f"{path}:{line_number}: invalid validation item")
                key, value = item.split(":", 1)
                current_validation = {key.strip(): scalar(value)}
                items.append(current_validation)
                continue
            if indent == 4 and current_validation is not None and ":" in line:
                key, value = line.split(":", 1)
                current_validation[key.strip()] = scalar(value)
                continue
            raise ValueError(f"{path}:{line_number}: invalid validation item")

        raise ValueError(f"{path}:{line_number}: scalar field cannot have nested values")

    return data


def normalized_fact(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_checkpoint(data: dict[str, object], path: Path) -> list[str]:
    contract = load_contract()
    errors: list[str] = []

    required_fields = contract.get("required_fields", [])
    assert isinstance(required_fields, list)
    errors.extend(
        f"{path}: missing checkpoint field {key}" for key in required_fields if key not in data
    )

    if str(data.get("checkpoint_version", "")) != str(contract.get("version")):
        errors.append(f"{path}: wrong checkpoint_version")

    statuses = contract.get("allowed_statuses", [])
    assert isinstance(statuses, list)
    if data.get("status") not in statuses:
        errors.append(f"{path}: unsupported status")

    next_action = str(data.get("next_action", "")).strip().casefold()
    if next_action in PLACEHOLDER_NEXT_ACTIONS:
        errors.append(f"{path}: next_action must be concrete")

    first_failure = data.get("first_failure")
    if not isinstance(first_failure, dict) or not all(
        str(first_failure.get(key, "")).strip() for key in ("marker", "evidence")
    ):
        errors.append(f"{path}: invalid first_failure")

    validation = data.get("validation")
    allowed_results = contract.get("allowed_validation_results", [])
    assert isinstance(allowed_results, list)
    if not isinstance(validation, list):
        errors.append(f"{path}: validation must be a list")
    else:
        for index, item in enumerate(validation, start=1):
            if not isinstance(item, dict) or not all(
                str(item.get(key, "")).strip() for key in ("command", "result", "evidence")
            ):
                errors.append(f"{path}: invalid validation item {index}")
                continue
            if item["result"] not in allowed_results:
                errors.append(f"{path}: unsupported validation result")

    limits = contract.get("compactness_limits", {})
    assert isinstance(limits, dict)
    for key, limit in limits.items():
        value = data.get(key, [])
        if not isinstance(value, list):
            errors.append(f"{path}: {key} must be a list")
        elif len(value) > int(limit):
            errors.append(f"{path}: {key} has {len(value)} items; compactness limit is {limit}")

    evidence_map = contract.get("evidence_state_fields", {})
    assert isinstance(evidence_map, dict)
    evidence_fields = list(evidence_map.values())
    evidence_sets = {
        key: {normalized_fact(str(item)) for item in data.get(key, []) if str(item).strip()}
        for key in evidence_fields
    }
    for index, left in enumerate(evidence_fields):
        for right in evidence_fields[index + 1 :]:
            overlap = evidence_sets[left] & evidence_sets[right]
            errors.extend(
                f"{path}: evidence fact appears in both {left} and {right}: {fact}"
                for fact in sorted(overlap)
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate compact agent task checkpoints")
    parser.add_argument("task", nargs="?", type=Path)
    parser.add_argument("--tasks", type=Path)
    parser.add_argument("--require-checkpoint", action="store_true")
    args = parser.parse_args()

    if bool(args.task) == bool(args.tasks):
        parser.error("provide exactly one task or --tasks directory")

    paths = [args.task] if args.task else sorted(args.tasks.glob("*.md"))
    errors: list[str] = []
    for path in paths:
        try:
            data = parse_checkpoint(path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if data is None:
            if args.require_checkpoint:
                errors.append(f"{path}: missing {CHECKPOINT_HEADING}")
        else:
            errors.extend(validate_checkpoint(data, path))

    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1

    print(f"Validated {len(paths)} checkpoint task(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
