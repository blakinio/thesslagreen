#!/usr/bin/env python3
"""Validate register definitions in the bundled JSON file."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Provide a stub package to avoid importing Home Assistant dependencies
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
tg_pkg = types.ModuleType("custom_components.thessla_green_modbus")
tg_pkg.__path__ = [str(ROOT / "custom_components" / "thessla_green_modbus")]
sys.modules["custom_components.thessla_green_modbus"] = tg_pkg

from custom_components.thessla_green_modbus.registers.schema import (
    RegisterDefinition,
)
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

    parsed: list[RegisterDefinition] = []
    seen_pairs: set[tuple[str, int]] = set()
    seen_names: set[str] = set()
    for item in registers:
        reg = RegisterDefinition.model_validate(item)

        pair = (reg.function, reg.address_dec)
        if pair in seen_pairs:
            raise ValueError(f"duplicate register pair: {pair}")
        if reg.name in seen_names:
            raise ValueError(f"duplicate register name: {reg.name}")
        seen_pairs.add(pair)
        seen_names.add(reg.name)

        typ = (reg.extra or {}).get("type")
        length = item.get("length", item.get("count", 1))
        if typ == "string":
            if length < 1:
                raise ValueError("string type requires length >= 1")
        else:
            expected_len = {
                "uint32": 2,
                "int32": 2,
                "float32": 2,
                "uint64": 4,
                "int64": 4,
                "float64": 4,
            }.get(typ)
            if expected_len is not None and length != expected_len:
                raise ValueError("length does not match type")

        if reg.function in {"01", "02"} and reg.access not in {"R", "R/-"}:
            raise ValueError("read-only functions must have R access")

        if item.get("bits") is not None and not ((reg.extra or {}).get("bitmask")):
            raise ValueError("bits provided without extra.bitmask")

        parsed.append(reg)

    return parsed


def main(path: Path = JSON_PATH) -> None:
    """Validate registers file, exiting with status 1 on error."""

    try:
        validate(path)
    except Exception as err:  # pragma: no cover - error path
        print(err)
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

