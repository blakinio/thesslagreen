"""Helper functions for mapping generation."""

from __future__ import annotations

import functools
import json
import logging
import sys
from pathlib import Path
from typing import Any

from homeassistant.const import PERCENTAGE

from ..registers.loader import get_all_registers
from ..utils import _to_snake_case

_LOGGER = logging.getLogger(__name__)


def _infer_icon(name: str, unit: str | None) -> str:
    """Return a default icon based on register name and unit."""
    if unit == "°C" or "temperature" in name:
        return "mdi:thermometer"
    if unit in {"m³/h", "m3/h"} or "flow" in name or "fan" in name:
        return "mdi:fan"
    if unit == PERCENTAGE or "percentage" in name:
        return "mdi:percent-outline"
    if unit in {"s", "min", "h", "d"} or "time" in name:
        return "mdi:timer"
    if unit == "V":
        return "mdi:sine-wave"
    return "mdi:numeric"


@functools.cache
def _load_register_info() -> dict[str, dict[str, Any]]:
    """Build and return the full register-info mapping.

    Reads get_all_registers through the parent mappings module so that
    test monkeypatching on ``em.get_all_registers`` is respected at call time.
    """
    _parent = sys.modules.get(__package__)
    fn = (
        getattr(_parent, "get_all_registers", None) if _parent is not None else None
    ) or get_all_registers
    cache: dict[str, dict[str, Any]] = {}
    for reg in fn():
        if not reg.name:
            continue
        scale = reg.multiplier or 1
        step = reg.resolution or scale
        cache[reg.name] = {
            "access": reg.access,
            "min": reg.min,
            "max": reg.max,
            "unit": reg.unit,
            "information": reg.information,
            "scale": scale,
            "step": step,
        }
    return cache


def _get_register_info(name: str) -> dict[str, Any] | None:
    """Return register metadata, handling numeric suffixes."""
    cache = _load_register_info()
    info = cache.get(name)
    if info is None and (suffix := name.rsplit("_", 1)) and len(suffix) > 1 and suffix[1].isdigit():
        info = cache.get(suffix[0])
    return info


def _parse_states(value: str | None) -> dict[str, int] | None:
    """Parse ``"0 - off; 1 - on"`` style state strings into a mapping."""
    if not value or "-" not in value:
        return None
    states: dict[str, int] = {}
    for part in value.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            num_str, label = part.split("-", 1)
            number = int(num_str.strip())
        except ValueError:
            continue
        states[_to_snake_case(label.strip())] = number
    return states or None


@functools.cache
def _number_translation_keys() -> set[str]:
    """Return register names that have a Number translation entry in en.json.

    Used as a whitelist: only registers present here will produce a Number
    entity, preventing unnamed "Rekuperator" fallback entries for reserved or
    undocumented registers (e.g. ``reserved_8145``–``reserved_8151``).

    Result is cached after the first call so the file is read at most once per
    process.  Call ``_number_translation_keys.cache_clear()`` in tests that need
    a fresh read.
    """
    try:
        _translations_dir = Path(__file__).resolve().parents[1] / "translations"
        with (_translations_dir / "en.json").open(encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("entity", {}).get("number", {}).keys())
    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as err:  # pragma: no cover - fallback when translations missing
        _LOGGER.debug("Failed to load number translation keys: %s", err)
        return set()
    except (AttributeError, TypeError) as err:  # pragma: no cover - unexpected
        _LOGGER.exception("Unexpected error loading number translation keys: %s", err)
        return set()


@functools.cache
def _load_translation_keys() -> dict[str, set[str]]:
    """Return available translation keys for supported entity types.

    Result is cached after the first call so the file is read at most once per
    process.  Call ``_load_translation_keys.cache_clear()`` in tests that need
    a fresh read.
    """
    try:
        _translations_dir = Path(__file__).resolve().parents[1] / "translations"
        with (_translations_dir / "en.json").open(encoding="utf-8") as f:
            data = json.load(f)
        entity = data.get("entity", {})
        return {
            "binary_sensor": set(entity.get("binary_sensor", {}).keys()),
            "switch": set(entity.get("switch", {}).keys()),
            "select": set(entity.get("select", {}).keys()),
        }
    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as err:  # pragma: no cover - fallback when translations missing
        _LOGGER.debug("Failed to load translation keys: %s", err)
        return {"binary_sensor": set(), "switch": set(), "select": set()}
    except (AttributeError, TypeError) as err:  # pragma: no cover - unexpected
        _LOGGER.exception("Unexpected error loading translation keys: %s", err)
        return {"binary_sensor": set(), "switch": set(), "select": set()}


__all__ = [
    "_get_register_info",
    "_infer_icon",
    "_load_register_info",
    "_load_translation_keys",
    "_number_translation_keys",
    "_parse_states",
    "get_all_registers",
]
