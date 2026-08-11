# mypy: ignore-errors
"""Test configuration for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import os
import sys
import warnings
from unittest.mock import AsyncMock, MagicMock

import pytest

# Treat unawaited coroutines as hard test failures. A green CI run must not hide
# asynchronous programming errors behind RuntimeWarning output.
warnings.filterwarnings("error", message="coroutine.*was never awaited", category=RuntimeWarning)

pytest_plugins = ("tests.helpers_register_loader", "tests.helpers_coordinator")


def _ensure_current_event_loop() -> asyncio.AbstractEventLoop:
    """Ensure a main-thread event loop exists for PHCC/pytest-asyncio startup."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from custom_components.thessla_green_modbus.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Required workaround for current PHCC/pytest-asyncio behavior on Python 3.13:
# ensure the main-thread loop exists before plugin fixtures request it.
_ensure_current_event_loop()

# Populate entity mappings before test modules are collected. Some test-module-
# level code reads entity mappings at import time; without this call those dicts
# would be empty because mapping construction is intentionally kept off the HA
# event-loop import path.
import custom_components.thessla_green_modbus.mappings as _thessla_mappings

_thessla_mappings._run_build_entity_mappings()


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.100",
            "port": 502,
            "slave_id": 10,
            "name": "Test Device",
            "connection_type": "tcp",
            "connection_mode": "tcp",
        },
        options={
            "scan_interval": 30,
            "timeout": 10,
            "retry": 3,
            "force_full_register_list": False,
        },
    )


@pytest.fixture(autouse=True)
def enable_event_loop_debug():
    """Keep PHCC debug-loop fixture compatible when no loop is pre-created."""
    loop = _ensure_current_event_loop()
    loop.set_debug(True)
    yield
    # Some plugin teardown paths clear the current loop. Re-establish one so
    # subsequent fixture teardown/setup does not emit the Python 3.13
    # "There is no current event loop" deprecation warning.
    _ensure_current_event_loop()


@pytest.fixture
def mock_coordinator():
    """Return a coordinator-shaped mock with current device-domain state."""
    from custom_components.thessla_green_modbus.registers.maps import (
        coil_registers,
        discrete_input_registers,
        holding_registers,
        input_registers,
    )

    coordinator = MagicMock()
    coordinator.device_client.config.host = "192.168.1.100"
    coordinator.device_client.config.port = 502
    coordinator.device_client.slave_id = 10
    coordinator.last_update_success = True
    coordinator.data = {
        "outside_temperature": 15.5,
        "supply_temperature": 20.0,
        "exhaust_temperature": 18.0,
        "mode": 0,
        "on_off_panel_mode": 1,
        "supply_percentage": 50,
    }
    device_info = {
        "device_name": "ThesslaGreen AirPack",
        "firmware": "4.85.0",
        "serial_number": "S/N: 1234 5678 9abc",
    }
    coordinator.device_info = device_info
    coordinator.device_client.device_info = device_info
    capabilities = MagicMock(
        constant_flow=True,
        gwc_system=True,
        bypass_system=True,
        heating_system=True,
        cooling_system=True,
        weekly_schedule=True,
        sensor_outside_temperature=True,
        sensor_supply_temperature=True,
        sensor_exhaust_temperature=True,
        sensor_fpx_temperature=True,
        sensor_duct_supply_temperature=True,
        sensor_gwc_temperature=True,
        sensor_ambient_temperature=True,
        sensor_heating_temperature=True,
    )
    coordinator.device_client.capabilities = capabilities
    available_registers = {
        "input_registers": {"outside_temperature", "supply_temperature", "exhaust_temperature"},
        "holding_registers": {"mode", "on_off_panel_mode", "air_flow_rate_manual"},
        "coil_registers": {"power_supply_fans", "bypass"},
        "discrete_inputs": {"expansion", "contamination_sensor"},
        "calculated": {
            "device_clock",
            "heat_recovery_efficiency",
            "heat_recovery_power",
            "electrical_power",
        },
    }
    coordinator.device_client.available_registers = available_registers
    register_maps = {
        "input_registers": input_registers().copy(),
        "holding_registers": holding_registers().copy(),
        "coil_registers": coil_registers().copy(),
        "discrete_inputs": discrete_input_registers().copy(),
    }
    coordinator.device_client.get_register_map = lambda register_type: register_maps.get(
        register_type, {}
    )
    coordinator.device_client.force_full_register_list = False
    coordinator.device_client.device_scan_result = None
    coordinator.device_client.statistics = {
        "successful_reads": 0,
        "failed_reads": 0,
        "connection_errors": 0,
        "timeout_errors": 0,
        "last_error": None,
        "last_successful_update": None,
        "average_response_time": 0.0,
        "total_registers_read": 0,
    }
    coordinator.device_client.offline_state = False
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator
