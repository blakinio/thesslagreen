# mypy: ignore-errors
"""Risk-focused branch coverage for the binary sensor platform."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from custom_components.thessla_green_modbus import binary_sensor as binary_module
from custom_components.thessla_green_modbus.binary_sensor import ThesslaGreenBinarySensor
from homeassistant.helpers.entity import EntityCategory


def _definition(
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


@pytest.mark.asyncio
async def test_setup_filters_stale_blocked_missing_and_force_creates(monkeypatch, mock_coordinator):
    monkeypatch.setattr(
        binary_module,
        "BINARY_SENSOR_DEFINITIONS",
        {
            "stale": _definition("problem_1"),
            "blocked": _definition("blocked_alarm"),
            "missing": _definition("missing_alarm"),
            "forced": _definition("forced_alarm"),
            "unavailable": _definition("unavailable_alarm"),
        },
    )
    mock_coordinator.device_client.get_register_map = Mock(
        return_value={
            "missing_alarm": 10,
            "forced_alarm": 11,
            "unavailable_alarm": 12,
        }
    )
    mock_coordinator.device_client.available_registers = {"holding_registers": {"missing_alarm"}}
    mock_coordinator.device_client.force_full_register_list = True
    monkeypatch.setattr(
        binary_module,
        "capability_block_reason",
        Mock(side_effect=lambda name, _caps: "unsupported" if name == "blocked_alarm" else None),
    )
    add_entities = Mock()

    await binary_module.async_setup_entry(Mock(), Mock(runtime_data=mock_coordinator), add_entities)

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert [entity._register_name for entity in entities] == [
        "missing_alarm",
        "forced_alarm",
        "unavailable_alarm",
    ]


@pytest.mark.asyncio
async def test_setup_handles_missing_address_and_no_entities(monkeypatch, mock_coordinator):
    monkeypatch.setattr(
        binary_module,
        "BINARY_SENSOR_DEFINITIONS",
        {"missing": _definition("missing_alarm")},
    )
    mock_coordinator.device_client.get_register_map = Mock(return_value={})
    mock_coordinator.device_client.available_registers = {"holding_registers": {"missing_alarm"}}
    mock_coordinator.device_client.force_full_register_list = False
    monkeypatch.setattr(binary_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()

    await binary_module.async_setup_entry(Mock(), Mock(runtime_data=mock_coordinator), add_entities)

    add_entities.assert_not_called()


def test_diagnostic_metadata_suggested_id_and_availability(mock_coordinator):
    entity = ThesslaGreenBinarySensor(
        mock_coordinator,
        "e_alarm",
        7,
        _definition(
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


def test_regular_availability_and_unknown_register_type(mock_coordinator):
    entity = ThesslaGreenBinarySensor(
        mock_coordinator,
        "custom_state",
        8,
        _definition("custom_state", register_type="unknown"),
    )
    entity._coordinator_connected = Mock(return_value=True)
    mock_coordinator.data["custom_state"] = 1

    assert entity.available is True
    assert entity.is_on is False

    entity._sensor_def["inverted"] = True
    assert entity.is_on is True


def test_attributes_cover_scan_bitmask_and_alarm_severity(mock_coordinator):
    entity = ThesslaGreenBinarySensor(
        mock_coordinator,
        "alarm_status",
        9,
        _definition("alarm_status", bitmask=True),
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


def test_icons_cover_dynamic_and_alarm_fallbacks(mock_coordinator):
    fan = ThesslaGreenBinarySensor(
        mock_coordinator,
        "power_supply_fans",
        1,
        _definition("power_supply_fans", "coil_registers", icon="mdi:fan"),
    )
    heater = ThesslaGreenBinarySensor(
        mock_coordinator,
        "heating_cable",
        2,
        _definition("heating_cable", "coil_registers", icon="mdi:heating-coil"),
    )
    pipe = ThesslaGreenBinarySensor(
        mock_coordinator,
        "gwc",
        3,
        _definition("gwc", "coil_registers", icon="mdi:pipe-valve"),
    )
    alarm = ThesslaGreenBinarySensor(
        mock_coordinator,
        "alarm",
        4,
        _definition("alarm"),
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
        _definition("generic"),
    )
    assert generic.icon == "mdi:fan-off"
