"""Tests for ThesslaGreenSelect entity."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.platform_stubs import install_select_stubs

install_select_stubs()

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus import select
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
)
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect


def test_select_creation_and_state(mock_coordinator):
    """Test creation and state changes of select entity."""
    mock_coordinator.data["mode"] = 0
    address = 4208
    select_entity = ThesslaGreenSelect(
        mock_coordinator, "mode", address, ENTITY_MAPPINGS["select"]["mode"]
    )
    assert select_entity.current_option == "auto"

    mock_coordinator.data["mode"] = 1
    assert select_entity.current_option == "manual"


def test_select_option_change(mock_coordinator):
    mock_coordinator.data["mode"] = 0
    address = 4208
    select_entity = ThesslaGreenSelect(
        mock_coordinator, "mode", address, ENTITY_MAPPINGS["select"]["mode"]
    )
    asyncio.run(select_entity.async_select_option("manual"))
    mock_coordinator.async_write_register.assert_awaited_with("mode", 1, refresh=False)
    mock_coordinator.async_request_refresh.assert_awaited_once()


def test_select_invalid_option(mock_coordinator):
    """Invalid options should raise and not trigger Modbus writes."""

    mock_coordinator.data["mode"] = 0
    address = 4208
    select_entity = ThesslaGreenSelect(
        mock_coordinator, "mode", address, ENTITY_MAPPINGS["select"]["mode"]
    )
    mock_coordinator.async_write_register = AsyncMock()

    with pytest.raises(Exception, match="Invalid option for mode: unsupported"):
        asyncio.run(select_entity.async_select_option("unsupported"))

    mock_coordinator.async_write_register.assert_not_awaited()
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_select_modbus_error_logs_and_returns(mock_coordinator):
    """Modbus failures should raise Home Assistant error semantics."""

    mock_coordinator.data["mode"] = 0
    address = 4208
    select_entity = ThesslaGreenSelect(
        mock_coordinator, "mode", address, ENTITY_MAPPINGS["select"]["mode"]
    )
    mock_coordinator.async_write_register = AsyncMock(
        side_effect=ConnectionException("write failed")
    )
    select_entity.hass = MagicMock()

    with pytest.raises(Exception, match="Error setting mode to manual: write failed"):
        asyncio.run(select_entity.async_select_option("manual"))

    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_select_definitions_single_source():
    """Ensure select definitions come from central ENTITY_MAPPINGS."""
    assert not hasattr(select, "SELECT_DEFINITIONS")
    assert "mode" in ENTITY_MAPPINGS["select"]


def test_schedule_time_select_current_option(mock_coordinator):
    """Schedule select entities decode stored 'HH:MM' strings as current option."""
    from custom_components.thessla_green_modbus.schedule_helpers import TIME_SELECT_STATES

    defn = {
        "translation_key": "schedule_summer_mon_1",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
        "states": TIME_SELECT_STATES,
    }
    mock_coordinator.data["schedule_summer_mon_1"] = "04:00"
    entity = ThesslaGreenSelect(mock_coordinator, "schedule_summer_mon_1", 16, defn)
    assert entity.current_option == "04:00"
    assert "04:00" in entity._attr_options
    assert "23:30" in entity._attr_options


def test_schedule_time_select_write(mock_coordinator):
    """Selecting a time slot writes the decoded HH:MM string to the register."""
    from custom_components.thessla_green_modbus.schedule_helpers import TIME_SELECT_STATES

    defn = {
        "translation_key": "schedule_summer_mon_1",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
        "states": TIME_SELECT_STATES,
    }
    mock_coordinator.data["schedule_summer_mon_1"] = "04:00"
    entity = ThesslaGreenSelect(mock_coordinator, "schedule_summer_mon_1", 16, defn)
    asyncio.run(entity.async_select_option("06:30"))
    mock_coordinator.async_write_register.assert_awaited_with(
        "schedule_summer_mon_1", "06:30", refresh=False
    )


def test_schedule_time_select_unknown_for_disabled_slot(mock_coordinator):
    """A disabled slot (raw int 65535) that is not in options returns None."""
    from custom_components.thessla_green_modbus.schedule_helpers import TIME_SELECT_STATES

    defn = {
        "translation_key": "schedule_summer_mon_1",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
        "states": TIME_SELECT_STATES,
    }
    mock_coordinator.data["schedule_summer_mon_1"] = 65535
    entity = ThesslaGreenSelect(mock_coordinator, "schedule_summer_mon_1", 16, defn)
    assert entity.current_option is None


def test_schedule_registers_in_entity_mappings_time():
    """Real schedule registers resolved from JSON should land in ENTITY_MAPPINGS time."""
    time_keys = ENTITY_MAPPINGS.get("time", {})
    assert (
        "schedule_summer_mon_1" in time_keys
    ), "schedule_summer_mon_1 should be a time entity (RW BCD time register)"
    assert "schedule_summer_mon_1" not in ENTITY_MAPPINGS.get(
        "sensor", {}
    ), "schedule_summer_mon_1 must not also be a sensor"
    assert "schedule_summer_mon_1" not in ENTITY_MAPPINGS.get(
        "select", {}
    ), "schedule_summer_mon_1 must not also be a select"
