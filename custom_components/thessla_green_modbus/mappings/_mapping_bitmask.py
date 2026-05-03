"""Helpers for deriving binary mappings from bitmask register definitions."""

from __future__ import annotations

from typing import Any

from ..utils import _to_snake_case


def iter_bitmask_binary_entries(reg: Any) -> list[tuple[str, dict[str, Any]]]:
    """Build binary mapping entries derived from a bitmask register definition."""
    func_map = {
        1: "coil_registers",
        2: "discrete_inputs",
        3: "holding_registers",
        4: "input_registers",
    }
    register_type = func_map.get(reg.function)
    if not register_type:
        return []

    bits = reg.bits or []
    entries: list[tuple[str, dict[str, Any]]] = []
    unnamed_bit = False
    for idx, bit_def in enumerate(bits):
        bit_name = bit_def.get("name") if isinstance(bit_def, dict) else (str(bit_def) if bit_def is not None else None)
        if bit_name:
            key = f"{reg.name}_{_to_snake_case(bit_name)}"
            entries.append(
                (
                    key,
                    {
                        "translation_key": key,
                        "register_type": register_type,
                        "register": reg.name,
                        "bit": 1 << idx,
                    },
                )
            )
        else:
            unnamed_bit = True

    if not bits or unnamed_bit:
        entries.append(
            (
                reg.name,
                {"translation_key": reg.name, "register_type": register_type, "bitmask": True},
            )
        )
    return entries
