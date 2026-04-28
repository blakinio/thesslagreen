"""Tests for ThesslaGreenText entity."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.mappings import (
    ENTITY_MAPPINGS,
    TEXT_ENTITY_MAPPINGS,
)
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.registers.loader import (
    get_registers_by_function,
)
from custom_components.thessla_green_modbus.text import ThesslaGreenText

HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_text_entity_mappings_contains_device_name():
    """device_name must be in TEXT_ENTITY_MAPPINGS."""
    assert "device_name" in TEXT_ENTITY_MAPPINGS
    assert TEXT_ENTITY_MAPPINGS["device_name"]["translation_key"] == "device_name"
    assert TEXT_ENTITY_MAPPINGS["device_name"]["register_type"] == "holding_registers"


def test_entity_mappings_exposes_text_section():
    """ENTITY_MAPPINGS must contain a 'text' key pointing to TEXT_ENTITY_MAPPINGS."""
    assert "text" in ENTITY_MAPPINGS
    assert "device_name" in ENTITY_MAPPINGS["text"]


def test_device_name_register_exists():
    """device_name must be a known holding register with address 8144."""
    assert "device_name" in HOLDING_REGISTERS
    assert HOLDING_REGISTERS["device_name"] == 8144


def _make_coordinator(data: dict | None = None) -> MagicMock:
    coord = MagicMock()
    coord.data = data or {}
    coord.last_update_success = True
    coord.offline_state = False
    coord.slave_id = 1
    coord.force_full_register_list = False
    coord.available_registers = {"holding_registers": set()}
    coord.async_write_register = AsyncMock(return_value=True)
    coord.async_request_refresh = AsyncMock()
    coord.get_register_map = lambda rtype: (
        HOLDING_REGISTERS if rtype == "holding_registers" else {}
    )
    coord.get_device_info = lambda: {}
    return coord


def test_text_native_value_string(mock_coordinator):
    """native_value returns the string from coordinator data."""
    mock_coordinator.data["device_name"] = "MyDevice"
    entity = ThesslaGreenText(
        mock_coordinator,
        "device_name",
        HOLDING_REGISTERS["device_name"],
        TEXT_ENTITY_MAPPINGS["device_name"],
    )
    assert entity.native_value == "MyDevice"


def test_text_native_value_none(mock_coordinator):
    """native_value returns None when register data is absent."""
    mock_coordinator.data.pop("device_name", None)
    entity = ThesslaGreenText(
        mock_coordinator,
        "device_name",
        HOLDING_REGISTERS["device_name"],
        TEXT_ENTITY_MAPPINGS["device_name"],
    )
    assert entity.native_value is None


def test_text_native_value_coerces_non_string(mock_coordinator):
    """native_value coerces non-string values to str."""
    mock_coordinator.data["device_name"] = 12345
    entity = ThesslaGreenText(
        mock_coordinator,
        "device_name",
        HOLDING_REGISTERS["device_name"],
        TEXT_ENTITY_MAPPINGS["device_name"],
    )
    assert entity.native_value == "12345"


def test_text_set_value(mock_coordinator):
    """async_set_value writes the string to the register and refreshes."""
    mock_coordinator.data["device_name"] = "OldName"
    entity = ThesslaGreenText(
        mock_coordinator,
        "device_name",
        HOLDING_REGISTERS["device_name"],
        TEXT_ENTITY_MAPPINGS["device_name"],
    )
    asyncio.run(entity.async_set_value("NewName"))
    mock_coordinator.async_write_register.assert_awaited_with(
        "device_name", "NewName", refresh=False
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()


def test_text_set_value_write_failure(mock_coordinator):
    """async_set_value logs an error when write returns False."""
    mock_coordinator.async_write_register = AsyncMock(return_value=False)
    entity = ThesslaGreenText(
        mock_coordinator,
        "device_name",
        HOLDING_REGISTERS["device_name"],
        TEXT_ENTITY_MAPPINGS["device_name"],
    )
    asyncio.run(entity.async_set_value("BadName"))
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_text_set_value_modbus_error(mock_coordinator):
    """async_set_value swallows ModbusException and does not refresh."""
    from custom_components.thessla_green_modbus.modbus_exceptions import ModbusException

    mock_coordinator.async_write_register = AsyncMock(side_effect=ModbusException("fail"))
    entity = ThesslaGreenText(
        mock_coordinator,
        "device_name",
        HOLDING_REGISTERS["device_name"],
        TEXT_ENTITY_MAPPINGS["device_name"],
    )
    asyncio.run(entity.async_set_value("Crash"))
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_text_set_value_connection_error(mock_coordinator):
    """async_set_value swallows ConnectionException and does not refresh."""
    mock_coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("conn fail"))
    entity = ThesslaGreenText(
        mock_coordinator,
        "device_name",
        HOLDING_REGISTERS["device_name"],
        TEXT_ENTITY_MAPPINGS["device_name"],
    )
    asyncio.run(entity.async_set_value("Crash"))
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_text_max_length_from_definition(mock_coordinator):
    """Entity respects max_length from the mapping definition."""
    entity = ThesslaGreenText(
        mock_coordinator,
        "device_name",
        HOLDING_REGISTERS["device_name"],
        TEXT_ENTITY_MAPPINGS["device_name"],
    )
    assert entity._attr_native_max == TEXT_ENTITY_MAPPINGS["device_name"]["max_length"]


@pytest.mark.asyncio
async def test_async_setup_entry_creates_entity(mock_coordinator, mock_config_entry):
    """async_setup_entry creates a text entity when device_name is available."""
    from custom_components.thessla_green_modbus.text import async_setup_entry

    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    mock_config_entry.runtime_data = mock_coordinator

    mock_coordinator.available_registers["holding_registers"].add("device_name")

    add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)
    entities = add_entities.call_args[0][0]
    names = [e._register_name for e in entities]
    assert "device_name" in names


@pytest.mark.asyncio
async def test_async_setup_entry_skips_when_not_available(mock_coordinator, mock_config_entry):
    """async_setup_entry creates no entities when device_name is not detected."""
    from custom_components.thessla_green_modbus.text import async_setup_entry

    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    mock_config_entry.runtime_data = mock_coordinator

    mock_coordinator.available_registers["holding_registers"].discard("device_name")
    mock_coordinator.force_full_register_list = False

    add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)
    add_entities.assert_not_called()
