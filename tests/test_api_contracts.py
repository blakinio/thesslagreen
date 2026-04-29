"""Public API and contract tests for refactored modules."""

from __future__ import annotations

import custom_components.thessla_green_modbus.config_flow as config_flow
import custom_components.thessla_green_modbus.coordinator as coordinator
import custom_components.thessla_green_modbus.coordinator.retry as coordinator_retry
import custom_components.thessla_green_modbus.scanner.core as scanner_core
import custom_components.thessla_green_modbus.services as services
import custom_components.thessla_green_modbus.services_schema as services_schema
import custom_components.thessla_green_modbus.services_targets as services_targets


def test_coordinator_exports_permanent_modbus_error() -> None:
    """Coordinator should expose permanent modbus error type."""
    assert coordinator._PermanentModbusError is coordinator_retry._PermanentModbusError
    assert "_PermanentModbusError" in coordinator.__all__


def test_scanner_core_public_api_is_minimal() -> None:
    """Scanner core should expose only true scanner class API."""
    expected_exports = {
        "DeviceCapabilities",
        "ThesslaGreenDeviceScanner",
    }
    assert expected_exports.issubset(set(scanner_core.__all__))
    for export_name in expected_exports:
        assert hasattr(scanner_core, export_name)


def test_services_module_wrappers_delegate_to_targets() -> None:
    """Services wrappers should point to extracted target helpers."""
    assert (
        services._get_coordinator_from_entity_id_impl
        is services_targets.get_coordinator_from_entity_id
    )
    assert services._iter_target_coordinators_impl is services_targets.iter_target_coordinators
    expected_exports = {
        "extract_entity_ids",
        "extract_entity_ids_with_extractor",
        "iter_target_coordinators",
        "get_coordinator_from_entity_id",
    }
    assert expected_exports.issubset(set(services_targets.__all__))


def test_services_module_reexports_schema_constants() -> None:
    """Services module should expose schema symbols used by handlers and tests."""
    assert services.SET_SPECIAL_MODE_SCHEMA is services_schema.SET_SPECIAL_MODE_SCHEMA
    assert services.SET_AIRFLOW_SCHEDULE_SCHEMA is services_schema.SET_AIRFLOW_SCHEDULE_SCHEMA
    assert services.SET_LOG_LEVEL_SCHEMA is services_schema.SET_LOG_LEVEL_SCHEMA


def test_config_flow_keeps_helper_surface() -> None:
    """Config-flow helper symbols should stay importable for existing tests."""
    for helper_name in (
        "_is_request_cancelled_error",
        "_looks_like_hostname",
        "_run_with_retry",
        "_call_with_optional_timeout",
    ):
        assert hasattr(config_flow, helper_name)


def test_scanner_package_exports_cancelled_error_helper() -> None:
    """Scanner package should expose cancelled-request classifier from scanner.io."""
    import custom_components.thessla_green_modbus.scanner as scanner_pkg

    assert hasattr(scanner_pkg, "is_request_cancelled_error")
