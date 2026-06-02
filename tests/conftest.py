# mypy: ignore-errors
"""Test configuration for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
import warnings
from unittest.mock import AsyncMock, MagicMock

import pytest

# Temporarily convert unawaited-coroutine RuntimeWarning into a hard error so
# the exact failing test shows up in CI logs with a full traceback.
warnings.filterwarnings("error", message="coroutine.*was never awaited", category=RuntimeWarning)

pytest_plugins = ("tests.helpers_register_loader", "tests.helpers_coordinator")


def _ensure_current_event_loop() -> asyncio.AbstractEventLoop:
    """Ensure a main-thread event loop exists for PHCC/pytest-asyncio startup.

    On Python 3.13, pytest-asyncio may begin with no current loop in MainThread,
    while pytest-homeassistant-custom-component's debug fixture still calls
    ``asyncio.get_event_loop()`` during setup.
    """
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# HA 2024.3 doesn't accept config_entry in DataUpdateCoordinator.__init__.
# Shim it away so tests run against the installed HA without changing production code.
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator as _DUC

if "config_entry" not in inspect.signature(_DUC.__init__).parameters:
    _duc_orig_init = _DUC.__init__

    def _duc_compat_init(self, *args, **kwargs):
        kwargs.pop("config_entry", None)
        _duc_orig_init(self, *args, **kwargs)

    _DUC.__init__ = _duc_compat_init

from custom_components.thessla_green_modbus.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Required workaround for current PHCC/pytest-asyncio behavior on Python 3.13:
# ensure the main-thread loop exists before plugin fixtures request it.
_ensure_current_event_loop()

# Populate entity mappings before test modules are collected.  Some test-module-
# level code (e.g. test_translations.py) reads NUMBER_ENTITY_MAPPINGS at import
# time; without this call those dicts would be empty because the module-level
# _run_build_entity_mappings() call was removed to eliminate blocking file I/O
# from the HA event-loop import path.
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


@pytest.fixture
def mock_coordinator():
    """Return a mock coordinator using MagicMock(spec=ThesslaGreenModbusCoordinator)."""
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
    _device_info = {
        "device_name": "ThesslaGreen AirPack",
        "firmware": "4.85.0",
        "serial_number": "S/N: 1234 5678 9abc",
    }
    # Set on both coordinator and device_client so proxy and direct access work.
    coordinator.device_client.device_info = _device_info
    coordinator.device_client.device_info = _device_info
    _capabilities = MagicMock(
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
    coordinator.device_client.capabilities = _capabilities
    _available_registers = {
        "input_registers": {"outside_temperature", "supply_temperature", "exhaust_temperature"},
        "holding_registers": {"mode", "on_off_panel_mode", "air_flow_rate_manual"},
        "coil_registers": {"power_supply_fans", "bypass"},
        "discrete_inputs": {"expansion", "contamination_sensor"},
        "calculated": {"estimated_power", "total_energy"},
    }
    coordinator.device_client.available_registers = _available_registers
    _register_maps = {
        "input_registers": input_registers().copy(),
        "holding_registers": holding_registers().copy(),
        "coil_registers": coil_registers().copy(),
        "discrete_inputs": discrete_input_registers().copy(),
    }
    coordinator.device_client.get_register_map = lambda rt: _register_maps.get(rt, {})
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
