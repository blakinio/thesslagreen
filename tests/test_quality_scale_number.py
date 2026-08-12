# mypy: ignore-errors
"""Risk-focused branch coverage for the number platform."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from custom_components.thessla_green_modbus import number as number_module
from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity
from custom_components.thessla_green_modbus.number import ThesslaGreenNumber
from homeassistant.helpers.entity import EntityCategory


def _config(**extra) -> dict:
    return {"min": 0, "max": 100, "step": 1, **extra}


@pytest.mark.asyncio
async def test_setup_filters_capability_missing_and_force_creates(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        number_module.ENTITY_MAPPINGS,
        "number",
        {
            "blocked": _config(),
            "missing": _config(),
            "forced": _config(),
        },
    )
    mock_coordinator.device_client.get_register_map = Mock(
        return_value={"missing": 50, "forced": 51}
    )
    mock_coordinator.device_client.available_registers = {"holding_registers": {"missing"}}
    mock_coordinator.device_client.force_full_register_list = True
    monkeypatch.setattr(
        number_module,
        "capability_block_reason",
        Mock(side_effect=lambda name, _caps: "unsupported" if name == "blocked" else None),
    )
    add_entities = Mock()

    await number_module.async_setup_entry(Mock(), Mock(runtime_data=mock_coordinator), add_entities)

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert [entity.register_name for entity in entities] == ["missing", "forced"]


@pytest.mark.asyncio
async def test_setup_missing_address_and_no_entities(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        number_module.ENTITY_MAPPINGS,
        "number",
        {"missing": _config()},
    )
    mock_coordinator.device_client.get_register_map = Mock(return_value={})
    mock_coordinator.device_client.available_registers = {"holding_registers": {"missing"}}
    mock_coordinator.device_client.force_full_register_list = False
    monkeypatch.setattr(number_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()

    await number_module.async_setup_entry(Mock(), Mock(runtime_data=mock_coordinator), add_entities)

    add_entities.assert_not_called()


def test_attributes_optimistic_and_metadata(mock_coordinator, monkeypatch):
    mock_coordinator.device_client.get_register_map = Mock(
        return_value={"temperature_setpoint": 60}
    )
    entity = ThesslaGreenNumber(
        mock_coordinator,
        "temperature_setpoint",
        _config(
            unit="°C",
            step=2,
            entity_category="diagnostic",
            risk_level="high",
            risk_category="control",
            safety_warning="careful",
        ),
        "holding_registers",
    )
    assert entity._attr_entity_category is EntityCategory.CONFIG
    assert entity._attr_icon == "mdi:thermometer"

    entity._optimistic.set_pending("temperature_setpoint", 21.0)
    assert entity.native_value == 21.0
    mock_coordinator.data["temperature_setpoint"] = 21.0

    parent_update = Mock()
    monkeypatch.setattr(ThesslaGreenEntity, "_handle_coordinator_update", parent_update)
    entity._handle_coordinator_update()
    assert entity._optimistic.get_pending("temperature_setpoint") is None
    parent_update.assert_called_once_with()

    mock_coordinator.data["temperature_setpoint"] = "invalid"
    assert entity.native_value is None
    entity._attr_native_step = "invalid"
    assert entity._optimistic_tolerance() == 0.5

    stamp = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    mock_coordinator.device_client.statistics["last_successful_update"] = None
    mock_coordinator.last_update = stamp
    attrs = entity.extra_state_attributes
    assert attrs["register_name"] == "temperature_setpoint"
    assert attrs["register_address"] == "60"
    assert attrs["last_updated"] == stamp.isoformat()
    assert attrs["risk_level"] == "high"
    assert attrs["risk_category"] == "control"
    assert attrs["safety_warning"] == "careful"


def test_icon_variants(mock_coordinator):
    mock_coordinator.device_client.get_register_map = Mock(
        return_value={
            "flow_rate": 61,
            "boost_duration": 62,
            "light_intensity": 63,
            "balance_coef": 64,
            "plain_value": 65,
        }
    )

    flow = ThesslaGreenNumber(mock_coordinator, "flow_rate", _config(), None)
    duration = ThesslaGreenNumber(mock_coordinator, "boost_duration", _config(), None)
    intensity = ThesslaGreenNumber(mock_coordinator, "light_intensity", _config(), None)
    coef = ThesslaGreenNumber(mock_coordinator, "balance_coef", _config(), None)
    plain = ThesslaGreenNumber(mock_coordinator, "plain_value", _config(), None)

    assert flow._attr_icon == "mdi:fan"
    assert duration._attr_icon == "mdi:timer"
    assert intensity._attr_icon == "mdi:gauge"
    assert coef._attr_icon == "mdi:percent"
    assert plain._attr_icon == "mdi:numeric"


@pytest.mark.asyncio
async def test_set_value_updates_optimistic_and_propagates_value_error(mock_coordinator):
    mock_coordinator.device_client.get_register_map = Mock(return_value={"setpoint": 66})
    entity = ThesslaGreenNumber(
        mock_coordinator,
        "setpoint",
        _config(step=2),
        "holding_registers",
    )
    entity._write_register = AsyncMock(return_value=True)
    entity.hass = Mock()
    entity.async_write_ha_state = Mock()

    await entity.async_set_native_value(42.0)

    entity._write_register.assert_awaited_once_with("setpoint", 42.0, include_offset=True)
    assert entity._optimistic.get_pending("setpoint") == 42.0
    entity.async_write_ha_state.assert_called_once_with()

    entity._write_register = AsyncMock(side_effect=ValueError("bad value"))
    with pytest.raises(ValueError, match="bad value"):
        await entity.async_set_native_value(43.0)
