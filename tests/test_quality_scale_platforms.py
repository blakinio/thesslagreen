# mypy: ignore-errors
"""Risk-focused branch coverage for entity platforms below the quality target."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from custom_components.thessla_green_modbus import binary_sensor as binary_module
from custom_components.thessla_green_modbus import number as number_module
from custom_components.thessla_green_modbus import select as select_module
from custom_components.thessla_green_modbus import text as text_module
from custom_components.thessla_green_modbus.binary_sensor import ThesslaGreenBinarySensor
from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity
from custom_components.thessla_green_modbus.number import ThesslaGreenNumber
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect
from custom_components.thessla_green_modbus.text import ThesslaGreenText
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from pymodbus.exceptions import ModbusException


def _binary_def(
    register: str,
    register_type: str = "holding_registers",
    **extra,
) -> dict:
    return {
        "register": register,
        "register_type": register_type,
        "translation_key": extra.pop("translation_key", register),
        **extra,
    }


def _select_def(**extra) -> dict:
    return {
        "register_type": "holding_registers",
        "translation_key": "mode_select",
        "states": {"off": 0, "on": 1},
        **extra,
    }


def _text_def(**extra) -> dict:
    return {
        "register_type": "holding_registers",
        "translation_key": "device_label",
        **extra,
    }


def _number_cfg(**extra) -> dict:
    return {"min": 0, "max": 100, "step": 1, **extra}


@pytest.mark.asyncio
async def test_binary_setup_filters_stale_blocked_missing_and_force_creates(
    monkeypatch, mock_coordinator
):
    monkeypatch.setattr(
        binary_module,
        "BINARY_SENSOR_DEFINITIONS",
        {
            "stale": _binary_def("problem_1"),
            "blocked": _binary_def("blocked_alarm"),
            "missing": _binary_def("missing_alarm"),
            "forced": _binary_def("forced_alarm"),
            "unavailable": _binary_def("unavailable_alarm"),
        },
    )
    register_map = {
        "missing_alarm": 10,
        "forced_alarm": 11,
        "unavailable_alarm": 12,
    }
    mock_coordinator.device_client.get_register_map = Mock(return_value=register_map)
    mock_coordinator.device_client.available_registers = {
        "holding_registers": {"missing_alarm"}
    }
    mock_coordinator.device_client.force_full_register_list = True
    monkeypatch.setattr(
        binary_module,
        "capability_block_reason",
        Mock(side_effect=lambda name, _caps: "unsupported" if name == "blocked_alarm" else None),
    )
    add_entities = Mock()

    await binary_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert [entity._register_name for entity in entities] == ["missing_alarm", "forced_alarm", "unavailable_alarm"]


@pytest.mark.asyncio
async def test_binary_setup_handles_missing_address_and_no_entities(monkeypatch, mock_coordinator):
    monkeypatch.setattr(
        binary_module,
        "BINARY_SENSOR_DEFINITIONS",
        {"missing": _binary_def("missing_alarm")},
    )
    mock_coordinator.device_client.get_register_map = Mock(return_value={})
    mock_coordinator.device_client.available_registers = {
        "holding_registers": {"missing_alarm"}
    }
    mock_coordinator.device_client.force_full_register_list = False
    monkeypatch.setattr(binary_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()

    await binary_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )

    add_entities.assert_not_called()


def test_binary_diagnostic_metadata_suggested_id_and_availability(mock_coordinator):
    entity = ThesslaGreenBinarySensor(
        mock_coordinator,
        "e_alarm",
        7,
        _binary_def(
            "e_alarm",
            entity_category="diagnostic",
            translation_key="alarm_bit_two",
            bit=2,
        ),
    )

    assert entity._attr_entity_category is EntityCategory.DIAGNOSTIC
    assert entity._attr_entity_registry_enabled_default is False
    assert entity.suggested_object_id == "alarm_bit_two"

    mock_coordinator.last_update_success = True
    mock_coordinator.device_client.offline_state = False
    assert entity.available is True
    mock_coordinator.device_client.offline_state = True
    assert entity.available is False


def test_binary_regular_availability_and_unknown_register_type(mock_coordinator):
    entity = ThesslaGreenBinarySensor(
        mock_coordinator,
        "custom_state",
        8,
        _binary_def("custom_state", register_type="unknown"),
    )
    entity._coordinator_connected = Mock(return_value=True)
    mock_coordinator.data["custom_state"] = 1

    assert entity.available is True
    assert entity.is_on is False

    entity._sensor_def["inverted"] = True
    assert entity.is_on is True


def test_binary_attributes_cover_scan_bitmask_and_alarm_severity(mock_coordinator):
    entity = ThesslaGreenBinarySensor(
        mock_coordinator,
        "alarm_status",
        9,
        _binary_def("alarm_status", bitmask=True),
    )
    mock_coordinator.device_client.device_scan_result = {"source": "scan"}
    mock_coordinator.data["alarm_status"] = 3

    attrs = entity.extra_state_attributes

    assert attrs["register_name"] == "alarm_status"
    assert attrs["register_type"] == "holding_registers"
    assert attrs["raw_value"] == 3
    assert attrs["bitmask"] == 3
    assert attrs["severity"] == "warning"

    mock_coordinator.data["alarm_status"] = 0
    assert entity.extra_state_attributes["severity"] == "normal"


def test_binary_icons_cover_dynamic_and_alarm_fallbacks(mock_coordinator):
    fan = ThesslaGreenBinarySensor(
        mock_coordinator,
        "power_supply_fans",
        1,
        _binary_def("power_supply_fans", "coil_registers", icon="mdi:fan"),
    )
    heater = ThesslaGreenBinarySensor(
        mock_coordinator,
        "heating_cable",
        2,
        _binary_def("heating_cable", "coil_registers", icon="mdi:heating-coil"),
    )
    pipe = ThesslaGreenBinarySensor(
        mock_coordinator,
        "gwc",
        3,
        _binary_def("gwc", "coil_registers", icon="mdi:pipe-valve"),
    )
    alarm = ThesslaGreenBinarySensor(
        mock_coordinator,
        "alarm",
        4,
        _binary_def("alarm"),
    )

    mock_coordinator.data.update(
        {"power_supply_fans": 0, "heating_cable": 0, "gwc": 0, "alarm": None}
    )
    assert fan.icon == "mdi:fan-off"
    assert heater.icon == "mdi:radiator-off"
    assert pipe.icon == "mdi:pipe"
    assert alarm.icon == "mdi:help-circle"

    mock_coordinator.data["alarm"] = 1
    assert alarm.icon == "mdi:alert-circle"
    mock_coordinator.data["alarm"] = 0
    assert alarm.icon == "mdi:check-circle"

    generic = ThesslaGreenBinarySensor(
        mock_coordinator,
        "generic",
        5,
        _binary_def("generic"),
    )
    assert generic.icon == "mdi:fan-off"


@pytest.mark.asyncio
async def test_select_setup_filters_capability_missing_and_force_creates(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        select_module.ENTITY_MAPPINGS,
        "select",
        {
            "blocked": _select_def(),
            "missing": _select_def(),
            "forced": _select_def(),
        },
    )
    mock_coordinator.device_client.get_register_map = Mock(
        return_value={"missing": 20, "forced": 21}
    )
    mock_coordinator.device_client.available_registers = {
        "holding_registers": {"missing"}
    }
    mock_coordinator.device_client.force_full_register_list = True
    monkeypatch.setattr(
        select_module,
        "capability_block_reason",
        Mock(side_effect=lambda name, _caps: "unsupported" if name == "blocked" else None),
    )
    add_entities = Mock()

    await select_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert [entity._register_name for entity in entities] == ["missing", "forced"]


@pytest.mark.asyncio
async def test_select_setup_missing_address_creates_nothing(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        select_module.ENTITY_MAPPINGS,
        "select",
        {"missing": _select_def()},
    )
    mock_coordinator.device_client.get_register_map = Mock(return_value={})
    mock_coordinator.device_client.available_registers = {
        "holding_registers": {"missing"}
    }
    monkeypatch.setattr(select_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()

    await select_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )

    add_entities.assert_not_called()


def test_select_current_option_optimistic_dict_and_special_availability(mock_coordinator):
    entity = ThesslaGreenSelect(mock_coordinator, "mode_select", 30, _select_def())
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
    special = ThesslaGreenSelect(mock_coordinator, special_name, 31, _select_def())
    special._coordinator_connected = Mock(return_value=False)
    assert special._optimistic_enabled is False
    assert special.available is False


def test_select_clear_optimistic_handles_disabled_dict_and_confirmed(mock_coordinator):
    entity = ThesslaGreenSelect(mock_coordinator, "mode_select", 30, _select_def())
    entity._optimistic.set_pending("mode_select", 1)
    mock_coordinator.data["mode_select"] = {"airflow_pct": 1}
    entity._clear_optimistic_if_confirmed()
    assert entity._optimistic.get_pending("mode_select") == 1

    mock_coordinator.data["mode_select"] = 1
    entity._clear_optimistic_if_confirmed()
    assert entity._optimistic.get_pending("mode_select") is None

    special_name = select_module.SETTING_SCHEDULE_PREFIXES[0] + "quality_test"
    disabled = ThesslaGreenSelect(mock_coordinator, special_name, 31, _select_def())
    disabled._optimistic.set_pending(special_name, 1)
    mock_coordinator.data[special_name] = 1
    disabled._clear_optimistic_if_confirmed()
    assert disabled._optimistic.get_pending(special_name) == 1


def test_select_risk_metadata_and_entity_category(mock_coordinator):
    entity = ThesslaGreenSelect(
        mock_coordinator,
        "mode_select",
        30,
        _select_def(
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
async def test_select_option_errors_and_successful_optimistic_write(mock_coordinator):
    entity = ThesslaGreenSelect(mock_coordinator, "mode_select", 30, _select_def())

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


@pytest.mark.asyncio
async def test_text_setup_filters_capability_missing_and_force_creates(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        text_module.ENTITY_MAPPINGS,
        "text",
        {
            "blocked": _text_def(),
            "missing": _text_def(),
            "forced": _text_def(),
        },
    )
    mock_coordinator.device_client.get_register_map = Mock(
        return_value={"missing": 40, "forced": 41}
    )
    mock_coordinator.device_client.available_registers = {
        "holding_registers": {"missing"}
    }
    mock_coordinator.device_client.force_full_register_list = True
    monkeypatch.setattr(
        text_module,
        "capability_block_reason",
        Mock(side_effect=lambda name, _caps: "unsupported" if name == "blocked" else None),
    )
    add_entities = Mock()

    await text_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert [entity._register_name for entity in entities] == ["missing", "forced"]


@pytest.mark.asyncio
async def test_text_setup_missing_address_and_entity_metadata(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        text_module.ENTITY_MAPPINGS,
        "text",
        {"missing": _text_def()},
    )
    mock_coordinator.device_client.get_register_map = Mock(return_value={})
    mock_coordinator.device_client.available_registers = {
        "holding_registers": {"missing"}
    }
    monkeypatch.setattr(text_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()

    await text_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )
    add_entities.assert_not_called()

    entity = ThesslaGreenText(
        mock_coordinator,
        "device_label",
        42,
        _text_def(
            entity_category="diagnostic",
            max_length=24,
            risk_level="advanced",
            risk_category="identity",
            safety_warning="rename device",
        ),
    )
    entity._coordinator_connected = Mock(return_value=True)
    assert entity.available is True
    assert entity._attr_entity_category is EntityCategory.CONFIG
    assert entity._attr_native_max == 24
    assert entity.extra_state_attributes == {
        "risk_level": "advanced",
        "risk_category": "identity",
        "safety_warning": "rename device",
    }


@pytest.mark.asyncio
async def test_text_write_success_and_runtime_failure(mock_coordinator):
    entity = ThesslaGreenText(mock_coordinator, "device_label", 42, _text_def())
    entity._write_register = AsyncMock(return_value=True)
    await entity.async_set_value("AirPack")
    entity._write_register.assert_awaited_once_with("device_label", "AirPack")

    entity._write_register = AsyncMock(side_effect=RuntimeError("write busy"))
    with pytest.raises(HomeAssistantError, match="Failed to set device_label"):
        await entity.async_set_value("AirPack")


@pytest.mark.asyncio
async def test_number_setup_filters_capability_missing_and_force_creates(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        number_module.ENTITY_MAPPINGS,
        "number",
        {
            "blocked": _number_cfg(),
            "missing": _number_cfg(),
            "forced": _number_cfg(),
        },
    )
    holding_map = {"missing": 50, "forced": 51}
    mock_coordinator.device_client.get_register_map = Mock(return_value=holding_map)
    mock_coordinator.device_client.available_registers = {
        "holding_registers": {"missing"}
    }
    mock_coordinator.device_client.force_full_register_list = True
    monkeypatch.setattr(
        number_module,
        "capability_block_reason",
        Mock(side_effect=lambda name, _caps: "unsupported" if name == "blocked" else None),
    )
    add_entities = Mock()

    await number_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert [entity.register_name for entity in entities] == ["missing", "forced"]


@pytest.mark.asyncio
async def test_number_setup_missing_address_and_no_entities(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        number_module.ENTITY_MAPPINGS,
        "number",
        {"missing": _number_cfg()},
    )
    mock_coordinator.device_client.get_register_map = Mock(return_value={})
    mock_coordinator.device_client.available_registers = {
        "holding_registers": {"missing"}
    }
    mock_coordinator.device_client.force_full_register_list = False
    monkeypatch.setattr(number_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()

    await number_module.async_setup_entry(
        Mock(), Mock(runtime_data=mock_coordinator), add_entities
    )

    add_entities.assert_not_called()


def test_number_attributes_optimistic_and_metadata(mock_coordinator, monkeypatch):
    mock_coordinator.device_client.get_register_map = Mock(
        return_value={"temperature_setpoint": 60}
    )
    entity = ThesslaGreenNumber(
        mock_coordinator,
        "temperature_setpoint",
        _number_cfg(
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


def test_number_icon_and_mode_variants(mock_coordinator):
    register_map = {
        "flow_rate": 61,
        "boost_duration": 62,
        "light_intensity": 63,
        "balance_coef": 64,
        "plain_value": 65,
    }
    mock_coordinator.device_client.get_register_map = Mock(return_value=register_map)

    flow = ThesslaGreenNumber(mock_coordinator, "flow_rate", _number_cfg(), None)
    duration = ThesslaGreenNumber(mock_coordinator, "boost_duration", _number_cfg(), None)
    intensity = ThesslaGreenNumber(mock_coordinator, "light_intensity", _number_cfg(), None)
    coef = ThesslaGreenNumber(mock_coordinator, "balance_coef", _number_cfg(), None)
    plain = ThesslaGreenNumber(mock_coordinator, "plain_value", _number_cfg(), None)

    assert flow._attr_icon == "mdi:fan"
    assert duration._attr_icon == "mdi:timer"
    assert intensity._attr_icon == "mdi:gauge"
    assert coef._attr_icon == "mdi:percent"
    assert plain._attr_icon == "mdi:numeric"


@pytest.mark.asyncio
async def test_number_set_value_updates_optimistic_and_propagates_value_error(mock_coordinator):
    mock_coordinator.device_client.get_register_map = Mock(return_value={"setpoint": 66})
    entity = ThesslaGreenNumber(
        mock_coordinator,
        "setpoint",
        _number_cfg(step=2),
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
