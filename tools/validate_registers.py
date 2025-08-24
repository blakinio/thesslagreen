#!/usr/bin/env python3
"""Validate register definitions in the bundled JSON file."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers.schema import (
    RegisterDefinition,
    RegisterList,
)


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)


def validate(path: Path) -> list[RegisterDefinition]:
    """Validate ``path`` and return the parsed register definitions."""

    data = json.loads(path.read_text(encoding="utf-8"))
    registers = data.get("registers", data)
    return RegisterList.model_validate(registers).root


def main(path: Path = JSON_PATH) -> None:
    """Validate registers file, exiting with status 1 on error."""

    try:
        validate(path)
    except Exception as err:  # pragma: no cover - error path
        print(err)
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

