#!/usr/bin/env python3
"""Validate register definitions in the bundled JSON file."""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING

import pydantic

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..custom_components.thessla_green_modbus.registers.schema import (
        RegisterDefinition,
    )

ROOT = Path(__file__).resolve().parents[1]


def _prepare_environment() -> None:
    """Add repository root and stub package to ``sys`` modules."""

    sys.path.insert(0, str(ROOT))
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    tg_pkg = types.ModuleType("custom_components.thessla_green_modbus")
    tg_pkg.__path__ = [str(ROOT / "custom_components" / "thessla_green_modbus")]
    sys.modules["custom_components.thessla_green_modbus"] = tg_pkg

    # Stub modules required for importing the registers loader without pulling
    # in the rest of the integration (which would otherwise create circular
    # imports during testing).
    modbus_helpers = types.ModuleType("custom_components.thessla_green_modbus.modbus_helpers")
    modbus_helpers.group_reads = lambda *_, **__: None  # type: ignore
    sys.modules.setdefault("custom_components.thessla_green_modbus.modbus_helpers", modbus_helpers)

    schedule_helpers = types.ModuleType("custom_components.thessla_green_modbus.schedule_helpers")
    schedule_helpers.bcd_to_time = lambda *_, **__: None  # type: ignore
    schedule_helpers.time_to_bcd = lambda *_, **__: None  # type: ignore
    sys.modules.setdefault(
        "custom_components.thessla_green_modbus.schedule_helpers", schedule_helpers
    )


def _coerce_registers(registers: list[dict]) -> list[dict]:
    """Normalise function and address fields in raw definitions.

    The schema accepts a wide range of function/address representations.  To
    mirror this behaviour when validating standalone JSON files we perform the
    same coercion here before handing off to the pydantic models.
    """

    from ..custom_components.thessla_green_modbus.registers.schema import (
        _normalise_function,
    )

    coerced: list[dict] = []
    for item in registers:
        data = dict(item)

        if "function" in data:
            data["function"] = f"{_normalise_function(data['function']):02d}"

        if "address_dec" in data:
            addr_dec = data["address_dec"]
            if isinstance(addr_dec, str):
                addr_dec = int(addr_dec, 0)
            data["address_dec"] = addr_dec

        if "address_hex" in data:
            addr_hex = data["address_hex"]
            if isinstance(addr_hex, str):
                addr_hex = int(addr_hex, 0)
            data["address_hex"] = hex(addr_hex)
        elif "address_dec" in data:
            data["address_hex"] = hex(data["address_dec"])

        coerced.append(data)

    return coerced


def validate(path: Path) -> list[RegisterDefinition]:
    """Validate ``path`` and return the parsed register definitions."""

    _prepare_environment()
    from ..custom_components.thessla_green_modbus.registers.schema import (
        _TYPE_LENGTHS,
        RegisterList,
        RegisterType,
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    registers = data.get("registers", data)

    if not isinstance(registers, list):
        raise TypeError("registers JSON must contain a list of register definitions")

    registers = _coerce_registers(registers)
    try:
        parsed_list = RegisterList.model_validate(registers)
    except pydantic.ValidationError as err:
        raise ValueError(err) from err

    seen_pairs: set[tuple[int, int]] = set()
    seen_names: set[str] = set()
    for reg in parsed_list.root:
        if not reg.description.strip() or not reg.description_en.strip():
            raise ValueError(f"{reg.name}: missing description fields")

        # Function/access combinations
        if reg.function in {1, 2} and reg.access != "R":
            raise ValueError(f"{reg.name}: functions 1 and 2 must have R access")

        # Enforce type/length relationships
        if reg.type is not None:
            typ = reg.type.value if isinstance(reg.type, RegisterType) else reg.type
            expected = _TYPE_LENGTHS.get(typ)
            if expected is None:
                if reg.length < 1:
                    raise ValueError(f"{reg.name}: string type requires length >= 1")
            elif reg.length != expected:
                raise ValueError(
                    f"{reg.name}: length {reg.length} != expected {expected} for {typ}"
                )

        # Enum map validation
        if reg.enum is not None:
            if not isinstance(reg.enum, dict):
                raise ValueError(f"{reg.name}: enum must be a mapping")
            for key, val in reg.enum.items():
                try:
                    int(key)
                except Exception:  # pragma: no cover - defensive
                    raise ValueError(f"{reg.name}: enum keys must be numeric") from None
                if not isinstance(val, str):
                    raise ValueError(f"{reg.name}: enum values must be strings")

        # Bit definition validation
        if reg.bits is not None:
            seen: set[int] = set()
            for bit in reg.bits:
                if not isinstance(bit, dict):
                    raise ValueError(f"{reg.name}: bits entries must be objects")
                idx = bit.get("index")
                name = bit.get("name")
                if not isinstance(idx, int) or isinstance(idx, bool):
                    raise ValueError(f"{reg.name}: bit index must be integer")
                if idx < 0 or idx > 15 or idx in seen:
                    raise ValueError(f"{reg.name}: invalid or duplicate bit index {idx}")
                seen.add(idx)
                if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]+", name):
                    raise ValueError(f"{reg.name}: bit name must be snake_case")

        # Hex/dec address consistency
        if int(reg.address_hex, 16) != reg.address_dec:
            raise ValueError(f"{reg.name}: address_hex does not match address_dec")

        # Uniqueness checks
        pair = (reg.function, reg.address_dec)
        if pair in seen_pairs:
            raise ValueError(f"{reg.name}: duplicate function/address pair {pair}")
        if reg.name in seen_names:
            raise ValueError(f"{reg.name}: duplicate register name {reg.name}")
        seen_pairs.add(pair)
        seen_names.add(reg.name)

    return parsed_list.root


def main(path: Path | None = None) -> int:
    """Validate registers file, exiting with ``1`` on error."""

    _prepare_environment()
    from ..custom_components.thessla_green_modbus.registers.loader import (
        _REGISTERS_PATH,
    )

    target = Path(path) if path is not None else _REGISTERS_PATH

    try:
        validate(Path(target))
    except Exception as err:  # pragma: no cover - error path
        print(err)
        raise SystemExit(1) from None
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
