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
        length = reg.length
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
            seen_indices: set[int] = set()
            for bit in bits:
                if not isinstance(bit, dict):
                    raise ValueError("bit entries must be objects")
                if "index" not in bit or "name" not in bit:
                    raise ValueError("bit entries must have index and name")

                idx = bit["index"]
                name = bit["name"]

                if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx <= 15:
                    raise ValueError("bit index must be 0-15")
                if idx in seen_indices:
                    raise ValueError("bit indices must be unique")
                seen_indices.add(idx)

                if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]+", name):
                    raise ValueError("bit name must be snake_case")

            bitmask_val = (reg.extra or {}).get("bitmask")
            mask_int: int | None = None
            if isinstance(bitmask_val, str):
                try:
                    mask_int = int(bitmask_val, 0)
                except ValueError:
                    mask_int = None
            elif isinstance(bitmask_val, int) and not isinstance(bitmask_val, bool):
                mask_int = bitmask_val
            if mask_int is not None and max(seen_indices, default=-1) >= mask_int.bit_length():
                raise ValueError("bits exceed bitmask width")

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

