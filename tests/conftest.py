# mypy: ignore-errors
"""Test configuration for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from homeassistant.components import climate as ha_climate
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _HA_AVAILABLE = True
except ImportError:
    _HA_AVAILABLE = False
    HomeAssistant = MagicMock  # type: ignore[misc,assignment]
    MockConfigEntry = MagicMock  # type: ignore[misc,assignment]

from custom_components.thessla_green_modbus.const import DOMAIN

try:
    asyncio.get_event_loop()
except RuntimeError:
    # pytest-asyncio 1.x can start with no current loop in MainThread.
    # Some HA plugin fixtures still call get_event_loop() during setup.
    asyncio.set_event_loop(asyncio.new_event_loop())

if _HA_AVAILABLE:
    if not hasattr(dr, "DeviceRegistryStore"):
        dr.DeviceRegistryStore = object  # type: ignore[attr-defined]
    if not hasattr(ha_climate, "PRESET_ECO"):
        ha_climate.PRESET_ECO = "eco"  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def ensure_ha_compat_symbols():
    """Re-add HA compat symbols when tests stub out HA modules."""
    dr_module = sys.modules.get("homeassistant.helpers.device_registry")
    if dr_module is None:
        dr_module = types.ModuleType("homeassistant.helpers.device_registry")
        sys.modules["homeassistant.helpers.device_registry"] = dr_module
    if not hasattr(dr_module, "DeviceRegistryStore"):
        dr_module.DeviceRegistryStore = object  # type: ignore[attr-defined]

    climate_module = sys.modules.get("homeassistant.components.climate")
    if climate_module is not None and not hasattr(climate_module, "PRESET_ECO"):
        climate_module.PRESET_ECO = "eco"  # type: ignore[attr-defined]
    yield


def _fake_modbus_response(*, registers=None, bits=None):
    """Build a minimal pymodbus-like response object for tests."""
    resp = MagicMock()
    resp.isError.return_value = False
    if registers is not None:
        resp.registers = registers
    if bits is not None:
        resp.bits = bits
    return resp


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    if _HA_AVAILABLE:
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
    # Minimal stub when HA is not installed
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.entry_id = "test_entry_id"
    entry.data = {
        "host": "192.168.1.100",
        "port": 502,
        "slave_id": 10,
        "name": "Test Device",
        "connection_type": "tcp",
        "connection_mode": "tcp",
    }
    entry.options = {
        "scan_interval": 30,
        "timeout": 10,
        "retry": 3,
        "force_full_register_list": False,
    }
    entry.runtime_data = MagicMock()
    return entry


@pytest.fixture(autouse=True)
def enable_event_loop_debug():
    """Compatibility override for HA plugin fixture on Python 3.13."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.set_debug(True)
    yield


@pytest.fixture
def mock_coordinator():
    """Return a mock coordinator using MagicMock(spec=ThesslaGreenModbusCoordinator)."""
    from custom_components.thessla_green_modbus.const import (
        coil_registers,
        discrete_input_registers,
        holding_registers,
        input_registers,
    )

    coordinator = MagicMock()
    coordinator.host = "192.168.1.100"
    coordinator.port = 502
    coordinator.slave_id = 10
    coordinator.last_update_success = True
    coordinator.data = {
        "outside_temperature": 15.5,
        "supply_temperature": 20.0,
        "exhaust_temperature": 18.0,
        "mode": 0,
        "on_off_panel_mode": 1,
        "supply_percentage": 50,
    }
    coordinator.device_info = {
        "device_name": "ThesslaGreen AirPack",
        "firmware": "4.85.0",
        "serial_number": "S/N: 1234 5678 9abc",
    }
    coordinator.capabilities = MagicMock(
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
    coordinator.available_registers = {
        "input_registers": {"outside_temperature", "supply_temperature", "exhaust_temperature"},
        "holding_registers": {"mode", "on_off_panel_mode", "air_flow_rate_manual"},
        "coil_registers": {"power_supply_fans", "bypass"},
        "discrete_inputs": {"expansion", "contamination_sensor"},
        "calculated": {"estimated_power", "total_energy"},
    }
    _register_maps = {
        "input_registers": input_registers().copy(),
        "holding_registers": holding_registers().copy(),
        "coil_registers": coil_registers().copy(),
        "discrete_inputs": discrete_input_registers().copy(),
    }
    coordinator.get_register_map = lambda rt: _register_maps.get(rt, {})
    coordinator.force_full_register_list = False
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator
