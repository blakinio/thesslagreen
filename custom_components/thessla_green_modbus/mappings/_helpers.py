"""Helper functions for mapping generation."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..registers.loader import RegisterDef

from .._compat import PERCENTAGE
from ..utils import _to_snake_case

try:  # pragma: no cover - optional during isolated tests
    from ..registers.loader import get_all_registers
except (ImportError, AttributeError):  # pragma: no cover - defensive

    def get_all_registers(json_path: Path | str | None = None) -> list[RegisterDef]:
        return []


_LOGGER = logging.getLogger(__name__)
_REGISTER_INFO_CACHE: dict[str, dict[str, Any]] | None = None


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


def _get_register_info(name: str) -> dict[str, Any] | None:
    """Return register metadata, handling numeric suffixes.

    Looks up ``_REGISTER_INFO_CACHE`` through the parent ``mappings`` package
    module so that test monkeypatching on ``em._REGISTER_INFO_CACHE`` is
    respected at call time.
    """
    global _REGISTER_INFO_CACHE

    # Prefer the cache stored on the parent module so monkeypatch works.
    _parent = sys.modules.get(__package__)
    cache: dict[str, Any] | None = (
        getattr(_parent, "_REGISTER_INFO_CACHE", None) if _parent is not None else _REGISTER_INFO_CACHE
    )

    if cache is None:
        _fn = (
            getattr(_parent, "get_all_registers", None) if _parent is not None else None
        ) or get_all_registers
        cache = {}
        for reg in _fn():
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
        _REGISTER_INFO_CACHE = cache
        if _parent is not None:
            _parent._REGISTER_INFO_CACHE = cache  # type: ignore[attr-defined]

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


def _number_translation_keys() -> set[str]:
    """Return register names that have a Number translation entry in en.json.

    Used as a whitelist: only registers present here will produce a Number
    entity, preventing unnamed "Rekuperator" fallback entries for reserved or
    undocumented registers (e.g. ``reserved_8145``–``reserved_8151``).
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


def _load_translation_keys() -> dict[str, set[str]]:
    """Return available translation keys for supported entity types."""

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
    "_REGISTER_INFO_CACHE",
    "_get_register_info",
    "_infer_icon",
    "_load_translation_keys",
    "_number_translation_keys",
    "_parse_states",
    "get_all_registers",
]
