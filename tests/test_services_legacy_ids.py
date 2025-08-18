from datetime import time
from types import SimpleNamespace

import pytest

import custom_components.thessla_green_modbus.services as services


class Services:
    """Minimal service registry for tests."""

    def __init__(self) -> None:
        self.handlers = {}

    def async_register(self, domain, service, handler, schema):  # pragma: no cover
        self.handlers[service] = handler


SERVICE_CALL_DATA = {
    "set_special_mode": {
        "entity_id": "number.rekuperator_speed",
        "mode": "thessla_green_modbus.special_mode_boost",
    },
    "set_airflow_schedule": {
        "entity_id": "number.rekuperator_speed",
        "day": "thessla_green_modbus.day_monday",
        "period": "thessla_green_modbus.period_1",
        "start_time": time(0, 0),
        "end_time": time(1, 0),
        "airflow_rate": 50,
    },
    "set_bypass_parameters": {
        "entity_id": "number.rekuperator_speed",
        "mode": "thessla_green_modbus.bypass_mode_auto",
    },
    "set_gwc_parameters": {
        "entity_id": "number.rekuperator_speed",
        "mode": "thessla_green_modbus.gwc_mode_off",
    },
    "set_air_quality_thresholds": {
        "entity_id": "number.rekuperator_speed",
        "co2_low": 500,
    },
    "set_temperature_curve": {
        "entity_id": "number.rekuperator_speed",
        "slope": 1.0,
        "offset": 0.0,
    },
    "reset_filters": {
        "entity_id": "number.rekuperator_speed",
        "filter_type": "thessla_green_modbus.filter_type_presostat",
    },
    "reset_settings": {
        "entity_id": "number.rekuperator_speed",
        "reset_type": "thessla_green_modbus.reset_type_user_settings",
    },
    "start_pressure_test": {
        "entity_id": "number.rekuperator_speed",
    },
    "set_modbus_parameters": {
        "entity_id": "number.rekuperator_speed",
        "port": "thessla_green_modbus.modbus_port_air_b",
    },
    "set_device_name": {
        "entity_id": "number.rekuperator_speed",
        "device_name": "TG",
    },
    "refresh_device_data": {
        "entity_id": "number.rekuperator_speed",
    },
}


@pytest.mark.asyncio
@pytest.mark.parametrize("service,data", SERVICE_CALL_DATA.items())
async def test_services_accept_legacy_entity_ids(monkeypatch, service, data):
    """Legacy entity IDs should be translated before entity extraction."""

    hass = SimpleNamespace()
    hass.services = Services()

    captured: list[list[str]] = []

    def fake_extract(hass, call):
        captured.append(call.data["entity_id"])
        return call.data["entity_id"]

    monkeypatch.setattr(services, "async_extract_entity_ids", fake_extract)
    monkeypatch.setattr(services, "_get_coordinator_from_entity_id", lambda h, e: None)

    await services.async_setup_services(hass)
    handler = hass.services.handlers[service]
    call = SimpleNamespace(data=data, service=service, domain=services.DOMAIN)

    await handler(call)

    assert captured[0] == ["fan.rekuperator_fan"]
