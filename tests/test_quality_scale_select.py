# mypy: ignore-errors
"""Risk-focused branch coverage for the select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from custom_components.thessla_green_modbus import select as select_module
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from pymodbus.exceptions import ModbusException


def _definition(**extra) -> dict:
    return {
        "register_type": "holding_registers",
        "translation_key": "mode_select",
        "states": {"off": 0, "on": 1},
        **extra,
    }


@pytest.mark.asyncio
async def test_setup_filters_capability_missing_and_force_creates(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        select_module.ENTITY_MAPPINGS,
        "select",
        {
            "blocked": _definition(),
            "missing": _definition(),
            "forced": _definition(),
        },
    )
    mock_coordinator.device_client.get_register_map = Mock(
        return_value={"missing": 20, "forced": 21}
    )
    mock_coordinator.device_client.available_registers = {"holding_registers": {"missing"}}
    mock_coordinator.device_client.force_full_register_list = True
    monkeypatch.setattr(
        select_module,
        "capability_block_reason",
        Mock(side_effect=lambda name, _caps: "unsupported" if name == "blocked" else None),
    )
    add_entities = Mock()

    await select_module.async_setup_entry(Mock(), Mock(runtime_data=mock_coordinator), add_entities)

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert [entity._register_name for entity in entities] == ["missing", "forced"]


@pytest.mark.asyncio
async def test_setup_missing_address_creates_nothing(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        select_module.ENTITY_MAPPINGS,
        "select",
        {"missing": _definition()},
    )
    mock_coordinator.device_client.get_register_map = Mock(return_value={})
    mock_coordinator.device_client.available_registers = {"holding_registers": {"missing"}}
    monkeypatch.setattr(select_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()

    await select_module.async_setup_entry(Mock(), Mock(runtime_data=mock_coordinator), add_entities)

    add_entities.assert_not_called()


def test_current_option_optimistic_dict_and_special_availability(mock_coordinator):
    entity = ThesslaGreenSelect(mock_coordinator, "mode_select", 30, _definition())
    mock_coordinator.data["mode_select"] = 0
    entity._optimistic.set_pending("mode_select", 1)
    assert entity.current_option == "on"

    entity._optimistic.set_pending("mode_select", 99)
    assert entity.current_option == "off"

    entity._optimistic.clear("mode_select")
    mock_coordinator.data["mode_select"] = {"airflow_pct": 1}
    assert entity.current_option == "on"
    mock_coordinator.data["mode_select"] = {}
    assert entity.current_option is None

    special_name = select_module.BCD_TIME_PREFIXES[0] + "quality_test"
    special = ThesslaGreenSelect(mock_coordinator, special_name, 31, _definition())
    special._coordinator_connected = Mock(return_value=False)
    assert special._optimistic_enabled is False
    assert special.available is False


def test_clear_optimistic_handles_disabled_dict_and_confirmed(mock_coordinator):
    entity = ThesslaGreenSelect(mock_coordinator, "mode_select", 30, _definition())
    entity._optimistic.set_pending("mode_select", 1)
    mock_coordinator.data["mode_select"] = {"airflow_pct": 1}
    entity._clear_optimistic_if_confirmed()
    assert entity._optimistic.get_pending("mode_select") == 1

    mock_coordinator.data["mode_select"] = 1
    entity._clear_optimistic_if_confirmed()
    assert entity._optimistic.get_pending("mode_select") is None

    special_name = select_module.SETTING_SCHEDULE_PREFIXES[0] + "quality_test"
    disabled = ThesslaGreenSelect(mock_coordinator, special_name, 31, _definition())
    disabled._optimistic.set_pending(special_name, 1)
    mock_coordinator.data[special_name] = 1
    disabled._clear_optimistic_if_confirmed()
    assert disabled._optimistic.get_pending(special_name) == 1


def test_risk_metadata_and_entity_category(mock_coordinator):
    entity = ThesslaGreenSelect(
        mock_coordinator,
        "mode_select",
        30,
        _definition(
            entity_category="diagnostic",
            risk_level="high",
            risk_category="control",
            safety_warning="careful",
        ),
    )

    assert entity._attr_entity_category is EntityCategory.CONFIG
    assert entity.extra_state_attributes == {
        "risk_level": "high",
        "risk_category": "control",
        "safety_warning": "careful",
    }


@pytest.mark.asyncio
async def test_option_errors_and_successful_optimistic_write(mock_coordinator):
    entity = ThesslaGreenSelect(mock_coordinator, "mode_select", 30, _definition())

    with pytest.raises(HomeAssistantError, match="Invalid option"):
        await entity.async_select_option("invalid")

    entity._write_register = AsyncMock(side_effect=RuntimeError("write busy"))
    with pytest.raises(HomeAssistantError, match="Failed to set mode_select to on"):
        await entity.async_select_option("on")

    entity._write_register = AsyncMock(side_effect=ModbusException("Modbus Error: device rejected"))
    with pytest.raises(HomeAssistantError, match="device rejected"):
        await entity.async_select_option("on")

    entity._write_register = AsyncMock(return_value=True)
    entity.hass = Mock()
    entity.async_write_ha_state = Mock()
    await entity.async_select_option("on")

    assert entity._optimistic.get_pending("mode_select") == 1
    entity.async_write_ha_state.assert_called_once_with()
