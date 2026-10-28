"""The second byte of a schedule must be readable and explicitly clearable."""

from types import SimpleNamespace

import pytest
from custom_components.thessla_green_modbus.core.schedule_values import complete_schedule_value
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.registers.loader import get_register_definition
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect
from custom_components.thessla_green_modbus.services.schema import (
    SET_AIRFLOW_SCHEDULE_SCHEMA,
    SET_AIRING_SCHEDULE_SCHEMA,
)
from homeassistant.exceptions import ServiceValidationError

from tests.test_services_handlers_schedule import _Coordinator, _make_hass, _setup_and_get


@pytest.mark.parametrize(
    "day", ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
)
@pytest.mark.parametrize("prefix", ["", "thessla_green_modbus.day_"])
@pytest.mark.parametrize("airing", [False, True])
def test_public_service_schemas_accept_plain_and_selector_weekdays(day, prefix, airing):
    schema = SET_AIRING_SCHEDULE_SCHEMA if airing else SET_AIRFLOW_SCHEDULE_SCHEMA
    data = {"entity_id": ["climate.unit"], "day": prefix + day}
    if not airing:
        data["period"] = 1
    assert schema(data)["day"] == prefix + day


def test_explicit_clear_replaces_existing_temperature_and_retains_airflow():
    value = complete_schedule_value(
        {"airflow_pct": 50, "temp_c": None, "temp_unset": True},
        {"airflow_pct": 50, "temp_c": 22.5},
    )
    assert get_register_definition("setting_summer_mon_1").encode(value) == 50 << 8


@pytest.mark.parametrize(
    "value", [{"temp_unset": True}, {"airflow_pct": 50, "temp_c": 20, "temp_unset": True}]
)
def test_ambiguous_clear_is_rejected(value):
    with pytest.raises(ValueError):
        complete_schedule_value(value, {"airflow_pct": 50, "temp_c": 22})


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["set_airflow_schedule", "set_intensity"])
async def test_service_clears_temperature_without_inventing_a_target(monkeypatch, service):
    coordinator = _Coordinator()
    handler = await _setup_and_get(_make_hass(), service, coordinator, monkeypatch)
    await handler(
        SimpleNamespace(
            data={
                "entity_id": ["climate.unit"],
                "day": "monday",
                "period": 1,
                "start_time": SimpleNamespace(hour=1, minute=0),
                "airflow_rate": 50,
                "clear_temperature": True,
            }
        )
    )
    setting_call = coordinator.async_write_register.call_args_list[0]
    assert setting_call.args == (
        "setting_summer_mon_1",
        {"airflow_pct": 50, "temp_c": None, "temp_unset": True},
    )


@pytest.mark.asyncio
async def test_conflicting_temperature_rejected_before_any_device_write(monkeypatch):
    coordinator = _Coordinator()
    handler = await _setup_and_get(_make_hass(), "set_airflow_schedule", coordinator, monkeypatch)
    with pytest.raises(ServiceValidationError):
        await handler(
            SimpleNamespace(
                data={
                    "entity_id": ["climate.unit"],
                    "day": "monday",
                    "period": 1,
                    "temperature": 22,
                    "clear_temperature": True,
                }
            )
        )
    coordinator.async_write_register.assert_not_awaited()


@pytest.mark.parametrize("temperature", [None, 22.5])
def test_schedule_select_exposes_both_fields(mock_coordinator, temperature):
    name = "setting_summer_mon_1"
    mock_coordinator.data[name] = {"airflow_pct": 50, "temp_c": temperature}
    entity = ThesslaGreenSelect(mock_coordinator, name, 72, ENTITY_MAPPINGS["select"][name])
    assert entity.extra_state_attributes == {
        "airflow_percentage": 50,
        "temperature_c": temperature,
        "temperature_unset": temperature is None,
    }
