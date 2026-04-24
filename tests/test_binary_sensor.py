"""Tests for ThesslaGreenBinarySensor entity."""

from unittest.mock import MagicMock, patch

import pytest

from tests.platform_stubs import install_binary_sensor_stubs

install_binary_sensor_stubs()

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.binary_sensor import (
    BINARY_SENSOR_DEFINITIONS,
    LEGACY_PROBLEM_KEY_PATTERN,
    ThesslaGreenBinarySensor,
    async_setup_entry,
)
from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.registers.loader import (
    get_registers_by_function,
)

HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}


def test_legacy_problem_key_pattern_matches_expected_values() -> None:
    """Guard against accidental creation of stale problem_* entities."""

    assert LEGACY_PROBLEM_KEY_PATTERN.fullmatch("problem")  # nosec B101
    assert LEGACY_PROBLEM_KEY_PATTERN.fullmatch("problem_29")  # nosec B101
    assert not LEGACY_PROBLEM_KEY_PATTERN.fullmatch("s_29")  # nosec B101


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


def test_fire_alarm_binary_sensor_inverted(mock_coordinator: MagicMock) -> None:
    """Fire alarm uses NC logic: True from device means no alarm (circuit closed)."""
    reg_type = BINARY_SENSOR_DEFINITIONS["fire_alarm"]["register_type"]
    address = mock_coordinator._register_maps[reg_type]["fire_alarm"]
    sensor = ThesslaGreenBinarySensor(
        mock_coordinator, "fire_alarm", address, BINARY_SENSOR_DEFINITIONS["fire_alarm"]
    )

    # Device reads True (NC closed = normal, no alarm) → HA should show False (safe)
    mock_coordinator.data["fire_alarm"] = True
    assert sensor.is_on is False  # nosec B101

    # Device reads False (NC open = alarm triggered) → HA should show True (unsafe)
    mock_coordinator.data["fire_alarm"] = False
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
    mock_config_entry.runtime_data = mock_coordinator

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
    with patch(
        "custom_components.thessla_green_modbus.binary_sensor.capability_block_reason",
        return_value=None,
    ):
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
    mock_config_entry.runtime_data = mock_coordinator

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
    mock_config_entry.runtime_data = mock_coordinator

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


# ---------------------------------------------------------------------------
# is_on edge cases (lines 137, 148-157)
# ---------------------------------------------------------------------------


def _make_sensor(mock_coordinator, name: str, sensor_def: dict) -> "ThesslaGreenBinarySensor":
    """Helper to create a sensor with a given definition."""
    reg_type = sensor_def["register_type"]
    address = mock_coordinator._register_maps.get(reg_type, {}).get(name, 0)
    return ThesslaGreenBinarySensor(mock_coordinator, name, address, sensor_def)


def test_binary_sensor_is_on_none_value(mock_coordinator: MagicMock) -> None:
    """is_on returns None when coordinator data value is None (line 137)."""
    mock_coordinator.data["bypass"] = None
    sensor_def = BINARY_SENSOR_DEFINITIONS["bypass"].copy()
    address = mock_coordinator._register_maps[sensor_def["register_type"]]["bypass"]
    sensor = ThesslaGreenBinarySensor(mock_coordinator, "bypass", address, sensor_def)
    assert sensor.is_on is None  # nosec B101


def test_binary_sensor_is_on_input_registers_with_bit(mock_coordinator: MagicMock) -> None:
    """is_on with input_registers and bit mask (lines 148-150)."""
    sensor_def = {
        "register_type": "input_registers",
        "translation_key": "test_sensor",
        "bit": 2,
    }
    mock_coordinator.data["test_ir"] = 0b110  # bit 2 (value 2) is set → True
    sensor = ThesslaGreenBinarySensor(mock_coordinator, "test_ir", 0, sensor_def)
    assert sensor.is_on is True  # nosec B101

    mock_coordinator.data["test_ir"] = 0b001  # bit 2 not set → False
    assert sensor.is_on is False  # nosec B101


def test_binary_sensor_is_on_input_registers_no_bit(mock_coordinator: MagicMock) -> None:
    """is_on with input_registers and no bit mask (line 150)."""
    sensor_def = {
        "register_type": "input_registers",
        "translation_key": "test_sensor",
    }
    mock_coordinator.data["test_ir2"] = 5
    sensor = ThesslaGreenBinarySensor(mock_coordinator, "test_ir2", 0, sensor_def)
    assert sensor.is_on is True  # nosec B101


def test_binary_sensor_is_on_holding_registers_with_bit(mock_coordinator: MagicMock) -> None:
    """is_on with holding_registers and bit mask (lines 152-154)."""
    sensor_def = {
        "register_type": "holding_registers",
        "translation_key": "test_sensor",
        "bit": 8,
    }
    mock_coordinator.data["test_hr"] = 0b1000  # bit 8 (value 8) set → True
    sensor = ThesslaGreenBinarySensor(mock_coordinator, "test_hr", 0, sensor_def)
    assert sensor.is_on is True  # nosec B101

    mock_coordinator.data["test_hr"] = 0b0001  # bit 8 not set → False
    assert sensor.is_on is False  # nosec B101


def test_binary_sensor_is_on_else_case(mock_coordinator: MagicMock) -> None:
    """is_on with unknown register_type returns False (lines 156-157)."""
    sensor_def = {
        "register_type": "unknown_type",
        "translation_key": "test_sensor",
    }
    mock_coordinator.data["test_unknown"] = 1
    sensor = ThesslaGreenBinarySensor(mock_coordinator, "test_unknown", 0, sensor_def)
    assert sensor.is_on is False  # nosec B101
