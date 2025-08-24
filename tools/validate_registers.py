#!/usr/bin/env python3
"""Validate register definitions in the bundled JSON file."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
import types

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


def validate(path: Path) -> list[RegisterDefinition]:
    """Validate ``path`` and return the parsed register definitions."""
    _prepare_environment()
    from custom_components.thessla_green_modbus.registers.schema import (
        RegisterDefinition,
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    registers = data.get("registers", data)

    parsed: list[RegisterDefinition] = []
    seen_pairs: set[tuple[int, int]] = set()
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
                "u16": 1,
                "i16": 1,
                "bitmask": 1,
                "u32": 2,
                "i32": 2,
                "f32": 2,
                "u64": 4,
                "i64": 4,
                "f64": 4,
            }.get(typ)
            if expected_len is not None and length != expected_len:
                raise ValueError("length does not match type")

        if reg.function in {1, 2} and reg.access not in {"R", "R/-"}:
            raise ValueError("read-only functions must have R access")

        if item.get("bits") is not None:
            if not ((reg.extra or {}).get("bitmask")):
                raise ValueError("bits provided without extra.bitmask")
            bits = item["bits"]
            if len(bits) > 16:
                raise ValueError("bits exceed 16 entries")
            for idx, bit in enumerate(bits):
                name = bit.get("name") if isinstance(bit, dict) else str(bit)
                if name and not re.fullmatch(r"[a-z0-9_]+", name):
                    raise ValueError("bit names must be snake_case")
                if idx > 15:
                    raise ValueError("bit index out of range")
        if reg.bits is not None:
            for idx, bit in enumerate(reg.bits):
                if bit.get("index", idx) != idx:
                    raise ValueError("bits must be in implicit index order")

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

