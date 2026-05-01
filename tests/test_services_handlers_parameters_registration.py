from __future__ import annotations

import logging
from types import SimpleNamespace

from custom_components.thessla_green_modbus.services_handler_deps import ServiceHandlerDeps
from custom_components.thessla_green_modbus.services_handlers_parameters import (
    _parameter_registrations,
    register_parameter_services,
)
from custom_components.thessla_green_modbus.services_schema import (
    SET_AIR_QUALITY_THRESHOLDS_SCHEMA,
    SET_BYPASS_PARAMETERS_SCHEMA,
    SET_GWC_PARAMETERS_SCHEMA,
    SET_TEMPERATURE_CURVE_SCHEMA,
)


class _Services:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, object]] = []

    def async_register(self, _domain: str, service: str, handler: object, schema: object) -> None:
        self.calls.append((service, handler, schema))


def _deps() -> ServiceHandlerDeps:
    async def _noop_write(*_args, **_kwargs):
        return True

    return ServiceHandlerDeps(
        domain="thessla_green_modbus",
        logger=logging.getLogger(__name__),
        special_function_map={},
        day_to_device_key={},
        air_quality_register_map={"co2_low": "co2_low", "co2_medium": "co2_medium", "co2_high": "co2_high", "humidity_target": "humidity_target"},
        iter_target_coordinators=lambda _h, _c: [],
        normalize_option=lambda value: value,
        clamp_airflow_rate=lambda value: value,
        write_register=_noop_write,
        create_log_level_manager=lambda *_args, **_kwargs: None,
        dt_now=lambda: None,
        scanner_create=lambda *_args, **_kwargs: None,
    )


def test_register_parameter_services_preserves_order_and_schema() -> None:
    hass = SimpleNamespace(services=_Services())

    register_parameter_services(hass, _deps())

    expected = [
        ("set_bypass_parameters", SET_BYPASS_PARAMETERS_SCHEMA),
        ("set_gwc_parameters", SET_GWC_PARAMETERS_SCHEMA),
        ("set_air_quality_thresholds", SET_AIR_QUALITY_THRESHOLDS_SCHEMA),
        ("set_temperature_curve", SET_TEMPERATURE_CURVE_SCHEMA),
    ]
    assert len(hass.services.calls) == len(expected)
    assert [(service, schema) for service, _handler, schema in hass.services.calls] == expected


def test_parameter_registrations_service_names_and_order() -> None:
    hass = SimpleNamespace(services=_Services())

    registrations = _parameter_registrations(hass, _deps())

    assert [service for service, _handler, _schema in registrations] == [
        "set_bypass_parameters",
        "set_gwc_parameters",
        "set_air_quality_thresholds",
        "set_temperature_curve",
    ]


def test_parameter_registrations_schema_binding() -> None:
    hass = SimpleNamespace(services=_Services())

    registrations = _parameter_registrations(hass, _deps())

    assert [(service, schema) for service, _handler, schema in registrations] == [
        ("set_bypass_parameters", SET_BYPASS_PARAMETERS_SCHEMA),
        ("set_gwc_parameters", SET_GWC_PARAMETERS_SCHEMA),
        ("set_air_quality_thresholds", SET_AIR_QUALITY_THRESHOLDS_SCHEMA),
        ("set_temperature_curve", SET_TEMPERATURE_CURVE_SCHEMA),
    ]
