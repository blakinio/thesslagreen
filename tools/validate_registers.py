#!/usr/bin/env python3
"""Validate register definitions in the bundled JSON file."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)


def _prepare_environment() -> None:
    """Add repository root and stub package to ``sys`` modules."""

    sys.path.insert(0, str(ROOT))
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    tg_pkg = types.ModuleType("custom_components.thessla_green_modbus")
    tg_pkg.__path__ = [str(ROOT / "custom_components" / "thessla_green_modbus")]
    sys.modules["custom_components.thessla_green_modbus"] = tg_pkg


def _is_int_like(value: object) -> bool:
    """Return ``True`` if ``value`` looks like an integer."""

    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        try:
            int(value, 0)
            return True
        except ValueError:
            return False
    return False


def validate(path: Path) -> list[RegisterDefinition]:
    """Validate ``path`` and return the parsed register definitions."""
    _prepare_environment()
    from custom_components.thessla_green_modbus.registers.schema import (
        RegisterDefinition,
        RegisterList,
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    registers = data.get("registers", data)

    parsed_list = RegisterList.model_validate(registers)
    parsed: list[RegisterDefinition] = parsed_list.root

    for raw, reg in zip(registers, parsed):
        enum = raw.get("enum")
        if enum is not None:
            if not isinstance(enum, dict) or not enum:
                raise ValueError("enum must be a non-empty mapping")

            keys_numeric = all(_is_int_like(k) for k in enum.keys())
            vals_numeric = all(_is_int_like(v) for v in enum.values())
            if keys_numeric and vals_numeric:
                raise ValueError("enum map cannot have both numeric keys and values")
            if not keys_numeric and not vals_numeric:
                raise ValueError("enum map must map ints to strings or strings to ints")
            if keys_numeric and not all(isinstance(v, str) for v in enum.values()):
                raise ValueError("enum values must be strings when keys are numeric")
            if vals_numeric and not all(isinstance(k, str) for k in enum.keys()):
                raise ValueError("enum keys must be strings when values are numeric")

    return parsed


def main(path: Path = JSON_PATH) -> int:
    """Validate registers file, returning ``1`` on error."""

    try:
        validate(path)
    except Exception as err:  # pragma: no cover - error path
        print(err)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

