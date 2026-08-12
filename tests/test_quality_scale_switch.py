# mypy: ignore-errors
"""Close switch-platform branch gaps without changing runtime behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.helpers.entity import EntityCategory

from custom_components.thessla_green_modbus import switch as switch_module
from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity
from custom_components.thessla_green_modbus.switch import ThesslaGreenSwitch


def _cfg(
    register: str,
    register_type: str = "holding_registers",
    **extra,
) -> dict:
    return {
        "register": register,
        "register_type": register_type,
        "translation_key": register,
        **extra,
    }


@pytest.mark.asyncio
async def test_switch_setup_covers_capability_force_full_missing_address_and_empty(
    monkeypatch, mock_coordinator
):
    mappings = {
        "blocked": _cfg("blocked_reg"),
        "forced_holding": _cfg("forced_holding"),
        "forced_coil": _cfg("forced_coil", "coil_registers"),
        "missing_address": _cfg("missing_address"),
        "unavailable": _cfg("unavailable"),
    }
    monkeypatch.setitem(switch_module.ENTITY_MAPPINGS, "switch", mappings)
    monkeypatch.setattr(
        switch_module,
        "holding_registers",
        Mock(return_value={"forced_holding": 101}),
    )
    monkeypatch.setattr(
        switch_module,
        "coil_registers",
        Mock(return_value={"forced_coil": 7}),
    )
    monkeypatch.setattr(
        switch_module,
        "capability_block_reason",
        Mock(side_effect=lambda name, _caps: "blocked" if name == "blocked_reg" else None),
    )
    mock_coordinator.device_client.force_full_register_list = True
    mock_coordinator.device_client.available_registers = {
        "holding_registers": {"missing_address"},
        "coil_registers": set(),
    }
    add_entities = Mock()

    await switch_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert {entity.register_name for entity in entities} == {
        "forced_holding",
        "forced_coil",
    }


@pytest.mark.asyncio
async def test_switch_setup_no_available_entities_does_not_add(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        switch_module.ENTITY_MAPPINGS,
        "switch",
        {"unavailable": _cfg("unavailable")},
    )
    monkeypatch.setattr(switch_module, "holding_registers", Mock(return_value={}))
    monkeypatch.setattr(switch_module, "coil_registers", Mock(return_value={}))
    monkeypatch.setattr(switch_module, "capability_block_reason", Mock(return_value=None))
    mock_coordinator.device_client.available_registers = {
        "holding_registers": set(),
        "coil_registers": set(),
    }
    mock_coordinator.device_client.force_full_register_list = False
    add_entities = Mock()

    await switch_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )

    add_entities.assert_not_called()


def test_switch_category_available_and_special_mode_state(mock_coordinator):
    config = _cfg(
        "special_mode",
        category="diagnostic",
        bit=3,
        risk_level="high",
        risk_category="control",
        safety_warning="test warning",
    )
    mock_coordinator.data["special_mode"] = 3
    entity = ThesslaGreenSwitch(mock_coordinator, "special_mode_three", 55, config)
    entity._coordinator_connected = Mock(return_value=True)

    assert entity._attr_entity_category is EntityCategory.DIAGNOSTIC
    assert entity.is_on is True
    mock_coordinator.data["special_mode"] = 2
    assert entity.is_on is False
    assert entity.available is True


def test_switch_optimistic_pending_wins_and_clears_when_confirmed(monkeypatch, mock_coordinator):
    entity = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, _cfg("bypass", "coil_registers"))
    mock_coordinator.data["bypass"] = 0
    entity._optimistic.set_pending("bypass", 1)

    assert entity.is_on is True

    parent_update = Mock()
    monkeypatch.setattr(ThesslaGreenEntity, "_handle_coordinator_update", parent_update)
    mock_coordinator.data["bypass"] = 1
    entity._handle_coordinator_update()

    assert entity._optimistic.get_pending("bypass") is None
    parent_update.assert_called_once_with()


def test_switch_optimistic_not_cleared_when_confirmed_value_missing(mock_coordinator):
    entity = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, _cfg("bypass", "coil_registers"))
    mock_coordinator.data.pop("bypass", None)
    entity._optimistic.set_pending("bypass", 1)

    entity._clear_optimistic_if_confirmed()

    assert entity._optimistic.get_pending("bypass") == 1


def test_switch_set_optimistic_pushes_state_when_added_to_hass(mock_coordinator):
    entity = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, _cfg("bypass", "coil_registers"))
    entity.hass = Mock()
    entity.async_write_ha_state = Mock()

    entity._set_optimistic(1)

    assert entity._optimistic.get_pending("bypass") == 1
    entity.async_write_ha_state.assert_called_once_with()


@pytest.mark.asyncio
async def test_switch_write_register_respects_entity_and_explicit_offsets(mock_coordinator, monkeypatch):
    config = _cfg("mode", offset=4)
    entity = ThesslaGreenSwitch(mock_coordinator, "mode", 100, config)
    parent_write = AsyncMock()
    monkeypatch.setattr(ThesslaGreenEntity, "_write_register", parent_write)

    await entity._write_register("mode", "2", refresh=False)
    parent_write.assert_awaited_once_with(
        "mode", 2, offset=4, refresh=False, include_offset=True
    )

    parent_write.reset_mock()
    await entity._write_register("mode", 3, offset=9, include_offset=False)
    parent_write.assert_awaited_once_with(
        "mode", 3, offset=9, refresh=True, include_offset=False
    )


def test_switch_extra_attributes_special_mode_include_raw_time_and_risk(mock_coordinator):
    stamp = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    config = _cfg(
        "special_mode",
        bit=2,
        risk_level="high",
        risk_category="control",
        safety_warning="careful",
    )
    mock_coordinator.data["special_mode"] = 2
    mock_coordinator.device_client.statistics["last_successful_update"] = stamp
    entity = ThesslaGreenSwitch(mock_coordinator, "special_mode_two", 55, config)

    attrs = entity.extra_state_attributes

    assert attrs["register_name"] == "special_mode"
    assert attrs["register_address"] == "55"
    assert attrs["register_type"] == "holding_registers"
    assert attrs["raw_value"] == 2
    assert attrs["last_updated"] == stamp.isoformat()
    assert attrs["control_type"] == "special_mode"
    assert attrs["bit"] == 2
    assert attrs["risk_level"] == "high"
    assert attrs["risk_category"] == "control"
    assert attrs["safety_warning"] == "careful"


def test_switch_extra_attributes_power_mode_and_operating_mode(mock_coordinator):
    stamp = datetime(2026, 8, 12, 10, 1, tzinfo=UTC)
    mock_coordinator.device_client.statistics["last_successful_update"] = None
    mock_coordinator.last_update = stamp

    power = ThesslaGreenSwitch(
        mock_coordinator,
        "power",
        1,
        _cfg("on_off_panel_mode"),
    )
    operating = ThesslaGreenSwitch(
        mock_coordinator,
        "mode_switch",
        2,
        _cfg("ventilation_mode"),
    )
    mock_coordinator.data["on_off_panel_mode"] = None
    mock_coordinator.data.pop("ventilation_mode", None)

    power_attrs = power.extra_state_attributes
    operating_attrs = operating.extra_state_attributes

    assert power_attrs["control_type"] == "system_power"
    assert "raw_value" not in power_attrs
    assert power_attrs["last_updated"] == stamp.isoformat()
    assert operating_attrs["control_type"] == "operating_mode"
    assert "raw_value" not in operating_attrs
