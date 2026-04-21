"""Entity mapping definitions for the ThesslaGreen Modbus integration.

Most entity descriptions are generated from the bundled register
metadata and can be extended or overridden by the dictionaries defined in
this module. This keeps the mapping definitions in sync with the register
specification while still allowing manual tweaks (for example to change
icons or alter the entity domain).

The module also provides helper utilities for deriving entity metadata
from register definitions and manual overrides.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from homeassistant.core import HomeAssistant

from ..const import (
    coil_registers,
    discrete_input_registers,
    holding_registers,
)

# ---------------------------------------------------------------------------
# Submodule imports — each submodule owns its code; __init__ is the controller
# ---------------------------------------------------------------------------
from ._helpers import (
    _REGISTER_INFO_CACHE,
    _get_register_info,
    _infer_icon,
    _load_translation_keys,
    _number_translation_keys,
    _parse_states,
    get_all_registers,
)
from ._loaders import (
    _build_entity_mappings,
    _extend_entity_mappings_from_registers,
    _load_discrete_mappings,
    _load_number_mappings,
)
from ._static_discrete import (
    BINARY_SENSOR_ENTITY_MAPPINGS,
    SELECT_ENTITY_MAPPINGS,
    SWITCH_ENTITY_MAPPINGS,
)
from ._static_numbers import NUMBER_ENTITY_MAPPINGS, NUMBER_OVERRIDES
from ._static_sensors import SENSOR_ENTITY_MAPPINGS
from .special_modes import SPECIAL_MODE_ICONS

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "BINARY_SENSOR_ENTITY_MAPPINGS",
    "ENTITY_MAPPINGS",
    "NUMBER_ENTITY_MAPPINGS",
    "NUMBER_OVERRIDES",
    "SELECT_ENTITY_MAPPINGS",
    "SENSOR_ENTITY_MAPPINGS",
    "SPECIAL_MODE_ICONS",
    "SWITCH_ENTITY_MAPPINGS",
    "TEXT_ENTITY_MAPPINGS",
    "TIME_ENTITY_MAPPINGS",
    "_REGISTER_INFO_CACHE",
    "_build_entity_mappings",
    "_extend_entity_mappings_from_registers",
    "_get_register_info",
    "_infer_icon",
    "_load_discrete_mappings",
    "_load_number_mappings",
    "_load_translation_keys",
    "_number_translation_keys",
    "_parse_states",
    "async_setup_entity_mappings",
    "coil_registers",
    "discrete_input_registers",
    "get_all_registers",
    "holding_registers",
]


# Time entity mappings for writable BCD HHMM registers
TIME_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}

# Text entities — ASCII string registers exposed as HA text controls
TEXT_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    "device_name": {
        "translation_key": "device_name",
        "icon": "mdi:rename",
        "register_type": "holding_registers",
        "max_length": 16,
    },
}

# Aggregated entity mappings for all platforms
ENTITY_MAPPINGS: dict[str, dict[str, dict[str, Any]]] = {}


def _run_build_entity_mappings() -> None:
    """Build entity mappings; delegates to _loaders._build_entity_mappings."""
    _build_entity_mappings()


async def async_setup_entity_mappings(hass: HomeAssistant | None = None) -> None:
    """Asynchronously build entity mappings."""

    if hass is not None:
        await hass.async_add_executor_job(_run_build_entity_mappings)
    else:
        _run_build_entity_mappings()

_run_build_entity_mappings()
