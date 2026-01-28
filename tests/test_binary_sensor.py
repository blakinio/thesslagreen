"""Tests for ThesslaGreenBinarySensor entity."""

import sys
import types
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))

binary_sensor_mod = cast(Any, types.ModuleType("homeassistant.components.binary_sensor"))


class BinarySensorEntity:  # pragma: no cover - simple stub
    pass


class BinarySensorDeviceClass:  # pragma: no cover - enum stubs
    RUNNING = "running"
    OPENING = "opening"
    POWER = "power"
    HEAT = "heat"
    CONNECTIVITY = "connectivity"
    PROBLEM = "problem"
    SAFETY = "safety"
    COLD = "cold"
    MOISTURE = "moisture"


binary_sensor_mod.BinarySensorEntity = BinarySensorEntity
binary_sensor_mod.BinarySensorDeviceClass = BinarySensorDeviceClass
sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_mod

entity_platform = cast(Any, types.ModuleType("homeassistant.helpers.entity_platform"))


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

network_mod = cast(Any, types.ModuleType("homeassistant.util.network"))


def is_host_valid(host: str) -> bool:  # pragma: no cover - simple stub
    return True


network_mod.is_host_valid = is_host_valid
sys.modules["homeassistant.util.network"] = network_mod

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.binary_sensor import (  # noqa: E402
    BINARY_SENSOR_DEFINITIONS,
    ThesslaGreenBinarySensor,
    async_setup_entry,
)
from custom_components.thessla_green_modbus.const import DOMAIN  # noqa: E402
from custom_components.thessla_green_modbus.registers.loader import (  # noqa: E402
    get_registers_by_function,
)

HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}


def test_binary_sensor_creation_and_state(mock_coordinator: MagicMock) -> None:
    """Test creation and state changes of binary sensor."""
    # Prepare coordinator data
    mock_coordinator.data["bypass"] = 0
    reg_type = BINARY_SENSOR_DEFINITIONS["bypass"]["register_type"]
    address = mock_coordinator._register_maps[reg_type]["bypass"]
    sensor = ThesslaGreenBinarySensor(
        mock_coordinator, "bypass", address, BINARY_SENSOR_DEFINITIONS["bypass"]
    )
    assert sensor.is_on is False  # nosec B101

    # Update coordinator data to trigger state change
    mock_coordinator.data["bypass"] = 1
    assert sensor.is_on is True  # nosec B101


def test_binary_sensor_icons(mock_coordinator: MagicMock) -> None:
    """Icon should switch to valid alternatives when sensor is off."""

    # Heating cable uses a heating icon when on
    mock_coordinator.data["heating_cable"] = 1
    reg_type = BINARY_SENSOR_DEFINITIONS["heating_cable"]["register_type"]
    address = mock_coordinator._register_maps[reg_type]["heating_cable"]
    heating = ThesslaGreenBinarySensor(
        mock_coordinator,
        "heating_cable",
        address,
        BINARY_SENSOR_DEFINITIONS["heating_cable"],
    )
    assert heating.icon == "mdi:heating-coil"  # nosec B101

    # When off, it should fall back to a valid icon
    mock_coordinator.data["heating_cable"] = 0
    assert heating.icon == "mdi:radiator-off"  # nosec B101

    # Bypass uses pipe leak icon when active
    mock_coordinator.data["bypass"] = 1
    reg_type = BINARY_SENSOR_DEFINITIONS["bypass"]["register_type"]
    address = mock_coordinator._register_maps[reg_type]["bypass"]
    bypass_sensor = ThesslaGreenBinarySensor(
        mock_coordinator, "bypass", address, BINARY_SENSOR_DEFINITIONS["bypass"]
    )
    assert bypass_sensor.icon == "mdi:pipe-leak"  # nosec B101

    # When inactive, generic pipe icon should be used
    mock_coordinator.data["bypass"] = 0
    assert bypass_sensor.icon == "mdi:pipe"  # nosec B101


def test_binary_sensor_icon_fallback(mock_coordinator: MagicMock) -> None:
    """Sensors without icons should return a sensible default."""
    mock_coordinator.data["bypass"] = 1
    sensor_def = BINARY_SENSOR_DEFINITIONS["bypass"].copy()
    sensor_def.pop("icon", None)
    reg_type = BINARY_SENSOR_DEFINITIONS["bypass"]["register_type"]
    address = mock_coordinator._register_maps[reg_type]["bypass"]
    sensor_without_icon = ThesslaGreenBinarySensor(mock_coordinator, "bypass", address, sensor_def)
    assert sensor_without_icon.icon == "mdi:fan-off"  # nosec B101


def test_dynamic_problem_registers_present() -> None:
    """Ensure alarm/error and S_/E_ registers are mapped."""
    expected = {"alarm", "error"} | {
        k for k in HOLDING_REGISTERS if k.startswith("s_") or k.startswith("e_")
    }
    for key in expected:
        assert key in BINARY_SENSOR_DEFINITIONS  # nosec B101


def test_problem_registers_range_mapped() -> None:
    """Registers 8192-8443 should map to binary sensors."""
    expected = {name for name, addr in HOLDING_REGISTERS.items() if 8192 <= addr <= 8443}
    for key in expected:
        assert key in BINARY_SENSOR_DEFINITIONS  # nosec B101


@pytest.mark.asyncio
async def test_async_setup_creates_all_binary_sensors(
    mock_coordinator: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Ensure entities are created for all available binary sensor registers."""
    hass: MagicMock = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    # Build available register sets from definitions
    available: dict[str, set[str]] = {
        "coil_registers": set(),
        "discrete_inputs": set(),
        "input_registers": set(),
        "holding_registers": set(),
    }
    for name, definition in BINARY_SENSOR_DEFINITIONS.items():
        available[definition["register_type"]].add(name)
    mock_coordinator.available_registers = available

    add_entities: MagicMock = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)

    entities = add_entities.call_args[0][0]
    assert len(entities) == len(BINARY_SENSOR_DEFINITIONS)  # nosec B101


@pytest.mark.asyncio
async def test_dynamic_register_entity_creation(
    mock_coordinator: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Dynamic S_/E_ registers should create entities when available."""
    hass: MagicMock = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    mock_coordinator.available_registers = {
        "holding_registers": {"alarm", "e_99"},
        "coil_registers": set(),
        "discrete_inputs": set(),
        "input_registers": set(),
    }
    add_entities: MagicMock = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)
    created = {entity._register_name for entity in add_entities.call_args[0][0]}
    assert {"alarm", "e_99"} <= created  # nosec B101


@pytest.mark.asyncio
async def test_force_full_register_list_adds_missing_binary_sensor(
    mock_coordinator: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Binary sensors are created from register map when forcing full list."""

    hass: MagicMock = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    mock_coordinator.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
        "calculated": set(),
    }
    mock_coordinator.force_full_register_list = True

    sensor_map = {
        "contamination_sensor": {
            "register_type": "discrete_inputs",
            "translation_key": "contamination_sensor",
        }
    }

    with patch.dict(BINARY_SENSOR_DEFINITIONS, sensor_map, clear=True):
        add_entities: MagicMock = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)
        created = {entity._register_name for entity in add_entities.call_args[0][0]}
        assert created == {"contamination_sensor"}  # nosec B101
