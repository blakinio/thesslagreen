"""Register JSON parsing helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

from .parse_file_helpers import async_read_registers_json, read_registers_json
from .register_def import RegisterDef
from .schema import RegisterList, _normalise_function, _normalise_name

_LOGGER = logging.getLogger(__name__)
_SPECIAL_MODES_PATH = Path(__file__).resolve().parents[1] / "options" / "special_modes.json"
_SPECIAL_MODES_ENUM: dict[int, str] = {}
try:  # pragma: no cover
    _SPECIAL_MODES_ENUM = {
        idx: key.split("_")[-1]
        for idx, key in enumerate(json.loads(_SPECIAL_MODES_PATH.read_text()))
    }
except (OSError, json.JSONDecodeError, ValueError) as err:  # pragma: no cover
    _LOGGER.debug("Failed to load special modes: %s", err)
    _SPECIAL_MODES_ENUM = {}
except (AttributeError, TypeError) as err:  # pragma: no cover
    _LOGGER.exception("Unexpected error loading special modes: %s", err)
    _SPECIAL_MODES_ENUM = {}


def parse_registers(raw: Any) -> list[RegisterDef]:
    """Parse raw register definition data into RegisterDef objects."""
    items = raw.get("registers", raw) if isinstance(raw, dict) else raw
    if hasattr(RegisterList, "model_validate"):
        parsed_items = RegisterList.model_validate(items).registers
    else:  # pragma: no cover
        parsed_items = RegisterList.parse_obj(items).registers
    return [register_from_parsed(parsed) for parsed in parsed_items]


def normalise_enum_map(
    name: str, enum_map: dict[int | str, Any] | None
) -> dict[int | str, Any] | None:
    if name == "special_mode":
        return cast(dict[int | str, Any], _SPECIAL_MODES_ENUM)
    if not enum_map:
        return enum_map
    if all(isinstance(k, int | float) or str(k).isdigit() for k in enum_map):
        return cast(dict[int | str, Any], {int(k): v for k, v in enum_map.items()})
    if all(isinstance(v, int | float) or str(v).isdigit() for v in enum_map.values()):
        return cast(dict[int | str, Any], {int(v): k for k, v in enum_map.items()})
    return enum_map


def coerce_scaling_fields(parsed: Any) -> tuple[float, float]:
    """Return safe multiplier/resolution values for RegisterDef construction."""
    multiplier = 1 if parsed.multiplier is None else float(parsed.multiplier)
    resolution = 1 if parsed.resolution is None else float(parsed.resolution)
    return multiplier, resolution


def register_from_parsed(parsed: Any) -> RegisterDef:
    """Build RegisterDef from parsed schema entry."""
    function = _normalise_function(parsed.function)
    address = int(parsed.address_dec)
    name = _normalise_name(parsed.name)
    enum_map = normalise_enum_map(
        name,
        cast(dict[int | str, Any] | None, parsed.enum),
    )
    multiplier, resolution = coerce_scaling_fields(parsed)
    return RegisterDef(
        function=function,
        address=address,
        name=name,
        access=str(parsed.access),
        description=parsed.description,
        description_en=parsed.description_en,
        unit=parsed.unit,
        multiplier=multiplier,
        resolution=resolution,
        min=parsed.min,
        max=parsed.max,
        default=parsed.default,
        enum=enum_map,
        notes=parsed.notes,
        information=parsed.information,
        extra=parsed.extra,
        length=int(parsed.length),
        bcd=bool(parsed.bcd),
        bits=parsed.bits,
    )


def load_registers_from_file(path: Path) -> list[RegisterDef]:
    """Load and parse register definitions from file path."""
    return parse_registers(read_registers_json(path))


async def async_load_registers_from_file(hass: Any | None, path: Path) -> list[RegisterDef]:
    """Load and parse register definitions asynchronously."""
    return parse_registers(await async_read_registers_json(hass, path))

