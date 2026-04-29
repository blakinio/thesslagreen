"""Pure codec helpers for register encode/decode operations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


def decode_enum_value(raw: int, enum_map: Mapping[int | str, Any] | None) -> Any | None:
    """Decode ``raw`` using register enum map when possible."""
    if enum_map is None:
        return None
    if raw in enum_map:
        return enum_map[raw]
    key = str(raw)
    if key in enum_map:
        return enum_map[key]
    return None


def decode_bitmask_value(raw: int, enum_map: Mapping[int | str, Any] | None) -> list[Any]:
    """Decode bit flags into a list of labels sorted by numeric bit value."""
    if not enum_map:
        return []
    flags: list[Any] = []
    entries = sorted(((int(k), v) for k, v in enum_map.items()), key=lambda pair: pair[0])
    for bit, label in entries:
        if raw & bit:
            flags.append(label)
    return flags


def encode_enum_value(value: Any, enum_map: Mapping[int | str, Any] | None, name: str) -> int:
    """Encode value according to enum map or raise ``ValueError``."""
    if enum_map is None:
        return int(value)
    if isinstance(value, str):
        for key, label in enum_map.items():
            if label == value:
                return int(key)
        raise ValueError(f"Invalid enum value {value!r} for {name}")
    if value in enum_map or str(value) in enum_map:
        return int(value)
    raise ValueError(f"Invalid enum value {value!r} for {name}")


def apply_output_scaling(value: Any, multiplier: float | None, resolution: float | None) -> Any:
    """Apply multiplier/resolution scaling to decoded value."""
    if multiplier not in (None, 1):
        value *= multiplier
    if resolution not in (None, 1):
        steps = round(value / resolution)
        value = steps * resolution
    return value


def coerce_scaled_input(
    *,
    value: Any,
    raw_value: Any,
    minimum: float | None,
    maximum: float | None,
    multiplier: float | None,
    resolution: float | None,
    name: str,
) -> Any:
    """Validate and convert user-facing value to raw register-domain value."""
    try:
        num_val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return raw_value

    if minimum is not None and num_val < Decimal(str(minimum)):
        raise ValueError(f"{value} is below minimum {minimum} for {name}")
    if maximum is not None and num_val > Decimal(str(maximum)):
        raise ValueError(f"{value} is above maximum {maximum} for {name}")

    scaled = Decimal(str(raw_value))
    if resolution not in (None, 1):
        step = Decimal(str(resolution))
        scaled = (scaled / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
    if multiplier not in (None, 1):
        mult = Decimal(str(multiplier))
        scaled = (scaled / mult).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return scaled
