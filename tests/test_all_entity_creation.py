"""Comprehensive smoke test: verify all 7 platforms create at least one entity.

This test calls ``async_setup_entry`` for every platform with a coordinator
whose ``available_registers`` / ``force_full_register_list`` are configured so
that the maximum number of entities can be instantiated.

Design:
- Adds missing HA component stubs that conftest does not provide (fan, switch,
  number, select, and the missing BinarySensorEntity on binary_sensor).
- Patches ``capability_block_reason`` to always return ``None`` (allow).
- Patches ``translation.async_get_translations`` (sensor platform).
- Sets ``force_full_register_list = True`` for register-driven platforms.
- Adds ``basic_control = True`` to capabilities for the climate platform.
- Ensures ``air_flow_rate_manual`` is in holding_registers for the fan.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Complete missing HA component stubs that conftest does not set up
# ---------------------------------------------------------------------------

def _ensure_attr(mod, name, value):
    """Set attribute on a module only if it is not already present."""
    if not hasattr(mod, name):
        setattr(mod, name, value)


# -- binary_sensor: BinarySensorEntity is absent in conftest stub ------------
_bs_mod = sys.modules.setdefault(
    "homeassistant.components.binary_sensor",
    types.ModuleType("homeassistant.components.binary_sensor"),
)


class _BinarySensorEntity:  # pragma: no cover - stub
    pass


class _BinarySensorDeviceClass:  # pragma: no cover - stub
    PROBLEM = "problem"
    RUNNING = "running"


_ensure_attr(_bs_mod, "BinarySensorEntity", _BinarySensorEntity)
_ensure_attr(_bs_mod, "BinarySensorDeviceClass", _BinarySensorDeviceClass)

# -- fan ---------------------------------------------------------------------
_fan_mod = sys.modules.setdefault(
    "homeassistant.components.fan",
    types.ModuleType("homeassistant.components.fan"),
)


class _FanEntity:  # pragma: no cover - stub
    pass


class _FanEntityFeature:  # pragma: no cover - stub
    SET_SPEED = 1
    PRESET_MODE = 8


_ensure_attr(_fan_mod, "FanEntity", _FanEntity)
_ensure_attr(_fan_mod, "FanEntityFeature", _FanEntityFeature)

# -- switch ------------------------------------------------------------------
_sw_mod = sys.modules.setdefault(
    "homeassistant.components.switch",
    types.ModuleType("homeassistant.components.switch"),
)


class _SwitchEntity:  # pragma: no cover - stub
    pass


_ensure_attr(_sw_mod, "SwitchEntity", _SwitchEntity)

# -- number ------------------------------------------------------------------
_num_mod = sys.modules.setdefault(
    "homeassistant.components.number",
    types.ModuleType("homeassistant.components.number"),
)


class _NumberEntity:  # pragma: no cover - stub
    pass


class _NumberMode:  # pragma: no cover - stub
    BOX = "box"
    SLIDER = "slider"


_ensure_attr(_num_mod, "NumberEntity", _NumberEntity)
_ensure_attr(_num_mod, "NumberMode", _NumberMode)

# -- select ------------------------------------------------------------------
_sel_mod = sys.modules.setdefault(
    "homeassistant.components.select",
    types.ModuleType("homeassistant.components.select"),
)


class _SelectEntity:  # pragma: no cover - stub
    pass


_ensure_attr(_sel_mod, "SelectEntity", _SelectEntity)

# -- components.time (TimeEntity used by time.py) ----------------------------
_time_mod = sys.modules.setdefault(
    "homeassistant.components.time",
    types.ModuleType("homeassistant.components.time"),
)


class _TimeEntity:  # pragma: no cover - stub
    pass


_ensure_attr(_time_mod, "TimeEntity", _TimeEntity)

# -- helpers.entity (EntityCategory used by number.py) ----------------------
_he_mod = sys.modules.setdefault(
    "homeassistant.helpers.entity",
    types.ModuleType("homeassistant.helpers.entity"),
)


class _EntityCategory:  # pragma: no cover - stub
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


_ensure_attr(_he_mod, "EntityCategory", _EntityCategory)

# -- UnitOfTime / UnitOfVolumeFlowRate / PERCENTAGE on ha_const (number.py) -
# Conftest defines UnitOfTime but without MINUTES — patch the existing class.
_ha_const = sys.modules.get("homeassistant.const")
if _ha_const is not None:
    _unit_time = getattr(_ha_const, "UnitOfTime", None)
    if _unit_time is None:
        class _UnitOfTime:  # pragma: no cover - stub
            MINUTES = "min"
            HOURS = "h"
            DAYS = "d"
            SECONDS = "s"
        _ha_const.UnitOfTime = _UnitOfTime
    else:
        for _attr, _val in [("MINUTES", "min"), ("HOURS", "h"), ("DAYS", "d"), ("SECONDS", "s")]:
            if not hasattr(_unit_time, _attr):
                setattr(_unit_time, _attr, _val)

    _unit_vol = getattr(_ha_const, "UnitOfVolumeFlowRate", None)
    if _unit_vol is None:
        class _UnitOfVolumeFlowRate:  # pragma: no cover - stub
            CUBIC_METERS_PER_HOUR = "m³/h"
        _ha_const.UnitOfVolumeFlowRate = _UnitOfVolumeFlowRate
    else:
        _ensure_attr(_unit_vol, "CUBIC_METERS_PER_HOUR", "m³/h")

    _ensure_attr(_ha_const, "PERCENTAGE", "%")

# ---------------------------------------------------------------------------
# Now it is safe to import the integration domain constant
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.const import DOMAIN  # noqa: E402


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _collect_entities(async_add_mock: MagicMock) -> list:
    """Extract the entity list from the first call to async_add_entities."""
    if not async_add_mock.called:
        return []
    return list(async_add_mock.call_args[0][0])


def _make_full_capabilities() -> SimpleNamespace:
    """Return capabilities SimpleNamespace with all flags required by platforms."""
    return SimpleNamespace(
        constant_flow=True,
        gwc_system=True,
        bypass_system=True,
        heating_system=True,
        cooling_system=True,
        weekly_schedule=True,
        sensor_outside_temperature=True,
        sensor_supply_temperature=True,
        sensor_exhaust_temperature=True,
        sensor_fpx_temperature=True,
        sensor_duct_supply_temperature=True,
        sensor_gwc_temperature=True,
        sensor_ambient_temperature=True,
        sensor_heating_temperature=True,
        basic_control=True,  # required by climate
    )


# ---------------------------------------------------------------------------
# Shared patch context
# ---------------------------------------------------------------------------

def _all_patches():
    """Return a list of patch objects covering all 5 capability-filtered platforms."""
    _cap = "custom_components.thessla_green_modbus.{mod}.capability_block_reason"
    return [
        patch(
            "custom_components.thessla_green_modbus.sensor.translation.async_get_translations",
            new=AsyncMock(return_value={}),
        ),
        patch(_cap.format(mod="sensor"), return_value=None),
        patch(_cap.format(mod="binary_sensor"), return_value=None),
        patch(_cap.format(mod="switch"), return_value=None),
        patch(_cap.format(mod="number"), return_value=None),
        patch(_cap.format(mod="select"), return_value=None),
    ]


# ---------------------------------------------------------------------------
# Test 1 – each platform creates ≥ 1 entity and entities are well-formed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_platforms_create_at_least_one_entity(
    mock_coordinator: MagicMock,
    mock_config_entry: MagicMock,
) -> None:
    """Each of the 7 platforms must create ≥ 1 entity."""

    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    mock_coordinator.force_full_register_list = True
    mock_coordinator.capabilities = _make_full_capabilities()

    holding = set(mock_coordinator.available_registers.get("holding_registers", set()))
    holding.add("air_flow_rate_manual")
    mock_coordinator.available_registers = dict(
        mock_coordinator.available_registers, holding_registers=holding
    )

    from custom_components.thessla_green_modbus import (  # noqa: PLC0415
        binary_sensor,
        climate,
        fan,
        number,
        select,
        sensor,
        switch,
    )

    platforms = [
        ("sensor", sensor),
        ("binary_sensor", binary_sensor),
        ("climate", climate),
        ("fan", fan),
        ("select", select),
        ("number", number),
        ("switch", switch),
    ]

    results: dict[str, list] = {}

    patches = _all_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        for platform_name, platform_module in platforms:
            add_entities = MagicMock()
            await platform_module.async_setup_entry(hass, mock_config_entry, add_entities)
            results[platform_name] = _collect_entities(add_entities)

    # ---- entity count ----
    for platform_name, entities in results.items():
        assert len(entities) > 0, (  # nosec B101
            f"Platform '{platform_name}' created 0 entities — "
            "check available_registers and entity_mappings"
        )

    # ---- entity properties ----
    for platform_name, entities in results.items():
        for entity in entities:
            assert entity._attr_has_entity_name is True, (  # nosec B101
                f"[{platform_name}] entity {entity!r} missing _attr_has_entity_name=True"
            )
            uid = entity.unique_id
            assert uid is not None, (  # nosec B101
                f"[{platform_name}] entity {entity!r} has unique_id=None"
            )
            assert isinstance(uid, str) and len(uid) > 0, (  # nosec B101
                f"[{platform_name}] unique_id must be a non-empty string, got {uid!r}"
            )


# ---------------------------------------------------------------------------
# Test 2 – entity count snapshot: verify counts match definitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_entity_counts_per_platform(
    mock_coordinator: MagicMock,
    mock_config_entry: MagicMock,
) -> None:
    """Entity counts per platform must match the static register definitions."""
    from custom_components.thessla_green_modbus.entity_mappings import (  # noqa: PLC0415
        BINARY_SENSOR_ENTITY_MAPPINGS,
        ENTITY_MAPPINGS,
    )

    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    mock_coordinator.force_full_register_list = True
    mock_coordinator.capabilities = _make_full_capabilities()

    holding = set(mock_coordinator.available_registers.get("holding_registers", set()))
    holding.add("air_flow_rate_manual")
    mock_coordinator.available_registers = dict(
        mock_coordinator.available_registers, holding_registers=holding
    )

    from custom_components.thessla_green_modbus import (  # noqa: PLC0415
        binary_sensor,
        climate,
        fan,
        number,
        select,
        sensor,
        switch,
        time as time_platform,
    )

    platforms = [
        ("sensor", sensor),
        ("binary_sensor", binary_sensor),
        ("climate", climate),
        ("fan", fan),
        ("select", select),
        ("number", number),
        ("switch", switch),
        ("time", time_platform),
    ]

    counts: dict[str, int] = {}
    patches = _all_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        for platform_name, platform_module in platforms:
            add_entities = MagicMock()
            await platform_module.async_setup_entry(hass, mock_config_entry, add_entities)
            counts[platform_name] = len(_collect_entities(add_entities))

    # All platforms must contribute entities
    for platform_name, count in counts.items():
        assert count > 0, f"Platform '{platform_name}': expected >0 entities, got 0"  # nosec B101

    # Singleton platforms
    assert counts["climate"] == 1, (  # nosec B101
        f"Expected exactly 1 climate entity, got {counts['climate']}"
    )
    assert counts["fan"] == 1, (  # nosec B101
        f"Expected exactly 1 fan entity, got {counts['fan']}"
    )

    # binary_sensor: must equal the number of definitions
    expected_bs = len(BINARY_SENSOR_ENTITY_MAPPINGS)
    assert counts["binary_sensor"] == expected_bs, (  # nosec B101
        f"binary_sensor: got {counts['binary_sensor']}, definitions={expected_bs}"
    )

    # sensor: definitions + ThesslaGreenErrorCodesSensor (always added)
    sensor_defs = len(ENTITY_MAPPINGS.get("sensor", {}))
    assert counts["sensor"] >= sensor_defs + 1, (  # nosec B101
        f"sensor: {counts['sensor']} < definitions({sensor_defs})+1"
    )

    # Minimum thresholds — each value is ~80% of the expected count.
    # Dropping below these means a regression (e.g. lazy-init dict left empty,
    # stale mappings removed en-masse, or a new capability gate introduced).
    MIN_COUNTS = {
        "sensor": 45,
        "binary_sensor": 70,
        "select": 70,
        "number": 45,
        "switch": 15,
        "time": 56,
    }
    for platform_name, minimum in MIN_COUNTS.items():
        assert counts[platform_name] >= minimum, (  # nosec B101
            f"Platform '{platform_name}': got {counts[platform_name]}, minimum={minimum} "
            "(regresja — sprawdź entity_mappings i _build_entity_mappings)"
        )

    # print counts for visibility in -v output
    print("\nEntity counts per platform:")
    for platform_name, count in counts.items():
        print(f"  {platform_name:15s}: {count}")
