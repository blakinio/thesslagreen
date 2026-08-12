# mypy: ignore-errors
"""Full branch coverage for the writable time platform."""

from __future__ import annotations

from datetime import time as dt_time
from unittest.mock import AsyncMock, Mock

import pytest
from custom_components.thessla_green_modbus import time as time_module
from custom_components.thessla_green_modbus.time import ThesslaGreenTime
from homeassistant.exceptions import HomeAssistantError
from pymodbus.exceptions import ModbusException


def _definition() -> dict[str, str]:
    return {
        "register_type": "holding_registers",
        "translation_key": "schedule_start",
        "icon": "mdi:clock-start",
    }


@pytest.mark.asyncio
async def test_time_setup_skips_capability_blocked_entity(monkeypatch, mock_coordinator):
    monkeypatch.setitem(time_module.ENTITY_MAPPINGS, "time", {"blocked_time": _definition()})
    mock_coordinator.device_client.get_register_map = Mock(return_value={"blocked_time": 10})
    mock_coordinator.device_client.available_registers = {"holding_registers": {"blocked_time"}}
    monkeypatch.setattr(
        time_module,
        "capability_block_reason",
        Mock(return_value="weekly_schedule_disabled"),
    )
    add_entities = Mock()
    config_entry = Mock(runtime_data=mock_coordinator)

    await time_module.async_setup_entry(Mock(), config_entry, add_entities)

    add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_time_setup_skips_available_entity_without_address(monkeypatch, mock_coordinator):
    monkeypatch.setitem(time_module.ENTITY_MAPPINGS, "time", {"missing_time": _definition()})
    mock_coordinator.device_client.get_register_map = Mock(return_value={})
    mock_coordinator.device_client.available_registers = {"holding_registers": {"missing_time"}}
    monkeypatch.setattr(time_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()
    config_entry = Mock(runtime_data=mock_coordinator)

    await time_module.async_setup_entry(Mock(), config_entry, add_entities)

    add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_time_setup_creates_force_full_entity(monkeypatch, mock_coordinator):
    monkeypatch.setitem(time_module.ENTITY_MAPPINGS, "time", {"forced_time": _definition()})
    mock_coordinator.device_client.get_register_map = Mock(return_value={"forced_time": 11})
    mock_coordinator.device_client.available_registers = {"holding_registers": set()}
    mock_coordinator.device_client.force_full_register_list = True
    monkeypatch.setattr(time_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()
    config_entry = Mock(runtime_data=mock_coordinator)

    await time_module.async_setup_entry(Mock(), config_entry, add_entities)

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert len(entities) == 1
    assert entities[0]._register_name == "forced_time"


def test_time_native_value_decodes_supported_and_fallback_values(mock_coordinator):
    entity = ThesslaGreenTime(mock_coordinator, "schedule_start", 12, _definition())

    cases = (
        (None, dt_time(0, 0)),
        ("07:45", dt_time(7, 45)),
        ("bad:value", dt_time(0, 0)),
        (75, dt_time(1, 15)),
        (24 * 60, dt_time(0, 0)),
        (object(), dt_time(0, 0)),
    )
    for raw, expected in cases:
        mock_coordinator.data["schedule_start"] = raw
        assert entity.native_value == expected


def test_time_available_delegates_to_coordinator_connection(mock_coordinator):
    entity = ThesslaGreenTime(mock_coordinator, "schedule_start", 12, _definition())
    entity._coordinator_connected = Mock(return_value=False)

    assert entity.available is False
    entity._coordinator_connected.assert_called_once_with()


@pytest.mark.asyncio
async def test_time_set_value_writes_hhmm_string(mock_coordinator):
    entity = ThesslaGreenTime(mock_coordinator, "schedule_start", 12, _definition())
    entity._write_register = AsyncMock(return_value=True)

    await entity.async_set_value(dt_time(6, 5))

    entity._write_register.assert_awaited_once_with("schedule_start", "06:05")


@pytest.mark.asyncio
async def test_time_set_value_surfaces_device_failure(mock_coordinator):
    entity = ThesslaGreenTime(mock_coordinator, "schedule_start", 12, _definition())
    entity._write_register = AsyncMock(side_effect=ModbusException("device rejected write"))

    with pytest.raises(HomeAssistantError, match="Failed to set schedule_start to 06:05"):
        await entity.async_set_value(dt_time(6, 5))
