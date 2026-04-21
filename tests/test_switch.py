"""Tests for ThesslaGreenSwitch entity."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from tests.platform_stubs import install_switch_stubs

install_switch_stubs()

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus import switch
from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.switch import ThesslaGreenSwitch

# Ensure required test mapping is present when dynamic generation is unavailable
ENTITY_MAPPINGS.setdefault("switch", {})
ENTITY_MAPPINGS["switch"].setdefault(
    "bypass",
    {
        "register": "bypass",
        "register_type": "coil_registers",
        "translation_key": "bypass",
        "icon": "mdi:pipe-leak",
    },
)


def test_switch_creation_and_state(mock_coordinator):
    """Test creation and state changes of coil switch."""
    mock_coordinator.data["bypass"] = 1
    address = 9
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator, "bypass", address, ENTITY_MAPPINGS["switch"]["bypass"]
    )
    assert switch_entity.is_on is True  # nosec B101

    mock_coordinator.data["bypass"] = 0
    assert switch_entity.is_on is False  # nosec B101


def test_switch_turn_on_off(mock_coordinator):
    mock_coordinator.data["bypass"] = 0
    address = 9
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator, "bypass", address, ENTITY_MAPPINGS["switch"]["bypass"]
    )
    asyncio.run(switch_entity.async_turn_on())
    mock_coordinator.async_write_register.assert_awaited_with("bypass", 1, refresh=False, offset=0)
    mock_coordinator.async_request_refresh.assert_awaited_once()
    mock_coordinator.async_write_register.reset_mock()
    mock_coordinator.async_request_refresh.reset_mock()

    mock_coordinator.data["bypass"] = 1
    asyncio.run(switch_entity.async_turn_off())
    mock_coordinator.async_write_register.assert_awaited_with("bypass", 0, refresh=False, offset=0)
    mock_coordinator.async_request_refresh.assert_awaited_once()


def test_switch_turn_on_modbus_failure(mock_coordinator):
    """Ensure Modbus errors are surfaced when turning on the switch."""
    address = 9
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator, "bypass", address, ENTITY_MAPPINGS["switch"]["bypass"]
    )
    mock_coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("fail"))
    with pytest.raises(ConnectionException):
        asyncio.run(switch_entity.async_turn_on())


def test_switch_turn_on_write_failure(mock_coordinator):
    """A failed write should raise and avoid refresh."""

    address = 9
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator, "bypass", address, ENTITY_MAPPINGS["switch"]["bypass"]
    )
    mock_coordinator.async_write_register = AsyncMock(return_value=False)

    with pytest.raises(RuntimeError):
        asyncio.run(switch_entity.async_turn_on())

    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_switch_definitions_single_source():
    """Ensure switch definitions come from central ENTITY_MAPPINGS."""
    assert not hasattr(switch, "SWITCH_ENTITIES")
    assert "bypass" in ENTITY_MAPPINGS["switch"]


def test_switch_is_on_register_not_in_data(mock_coordinator):
    """is_on returns None when register_name is not in coordinator.data (line 130)."""
    mock_coordinator.data = {}  # empty — register not present
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator,
        "bypass",
        9,
        ENTITY_MAPPINGS["switch"]["bypass"],
    )
    assert switch_entity.is_on is None  # nosec B101


def test_switch_is_on_none_raw_value(mock_coordinator):
    """is_on returns None when raw_value is None (line 136)."""
    mock_coordinator.data["bypass"] = None
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator,
        "bypass",
        9,
        ENTITY_MAPPINGS["switch"]["bypass"],
    )
    assert switch_entity.is_on is None  # nosec B101


def test_switch_is_on_with_bit(mock_coordinator):
    """is_on uses bit mask when bit is set (line 139)."""
    config = {
        "register": "bypass",
        "register_type": "holding_registers",
        "translation_key": "bypass_bit",
        "bit": 4,
    }
    mock_coordinator.data["bypass"] = 0b0011  # bit 4 (value 4) not set → False
    switch_entity = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, config)
    assert switch_entity.is_on is False  # nosec B101

    mock_coordinator.data["bypass"] = 0b0100  # bit 4 (value 4) set → True
    assert switch_entity.is_on is True  # nosec B101


def test_switch_turn_off_with_bit(mock_coordinator):
    """async_turn_off with bit clears the bit from current value (lines 163-164)."""
    config = {
        "register": "bypass",
        "register_type": "holding_registers",
        "translation_key": "bypass_bit",
        "bit": 4,
    }
    mock_coordinator.data["bypass"] = 0b0110  # bit 4 not set, bits 1&2 set
    switch_entity = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, config)
    asyncio.run(switch_entity.async_turn_off())
    # current=0b0110, ~bit=~4 → 0b0110 & ~0b0100 = 0b0010
    mock_coordinator.async_write_register.assert_awaited_with(
        "bypass", 0b0010, refresh=False, offset=0
    )


def test_switch_turn_off_exception_raises(mock_coordinator):
    """async_turn_off re-raises Modbus exceptions (lines 170-172)."""
    from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException

    mock_coordinator.async_write_register = AsyncMock(
        side_effect=ConnectionException("fail")
    )
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator,
        "bypass",
        9,
        ENTITY_MAPPINGS["switch"]["bypass"],
    )
    mock_coordinator.data["bypass"] = 0
    with pytest.raises(ConnectionException):
        asyncio.run(switch_entity.async_turn_off())


def test_switch_icon_fallback(hass, mock_config_entry, mock_coordinator):
    """Switch setups without an explicit icon use the default icon."""
    config = {
        "register": "mock_register",
        "register_type": "coil_registers",
        "translation_key": "mock_switch_no_icon",
    }
    mock_coordinator.data["mock_register"] = 0
    mock_coordinator.available_registers = {"coil_registers": {"mock_register"}}
    mock_coordinator.force_full_register_list = False
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    mock_config_entry.runtime_data = mock_coordinator

    added = []

    def async_add_entities(entities, update=False):  # pragma: no cover - test helper
        added.extend(entities)

    with patch.dict(ENTITY_MAPPINGS["switch"], {"mock_switch_no_icon": config}), \
         patch("custom_components.thessla_green_modbus.switch.coil_registers",
               return_value={"mock_register": 42}):
        asyncio.run(switch.async_setup_entry(hass, mock_config_entry, async_add_entities))

    assert len(added) == 1
    assert added[0]._attr_icon == "mdi:toggle-switch"
