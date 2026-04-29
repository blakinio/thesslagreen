"""Capabilities-related tests for ThesslaGreen scanner."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP
from custom_components.thessla_green_modbus.scanner.core import (
    DeviceCapabilities,
    ScannerDeviceInfo,
    ThesslaGreenDeviceScanner,
)

pytestmark = pytest.mark.asyncio


async def test_capabilities_detect_schedule_keywords():
    """Ensure capability detection considers scheduling related registers."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner.available_registers["holding_registers"].add("airing_start_time")
    caps = scanner._analyze_capabilities()
    assert caps.weekly_schedule is True


@pytest.mark.parametrize(
    "register",
    ["constant_flow_active", "supply_air_flow", "supply_flow_rate", "cf_version"],
)
async def test_constant_flow_detected_from_various_registers(register):
    """Constant flow capability is detected from different register names."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner.available_registers = {
        "input_registers": {register},
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    caps = scanner._analyze_capabilities()
    assert caps.constant_flow is True


async def test_analyze_capabilities():
    """Test capability analysis."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
    scanner.available_registers = {
        "input_registers": {"constant_flow_active", "outside_temperature"},
        "holding_registers": {"gwc_mode", "bypass_mode"},
        "coil_registers": {"power_supply_fans"},
        "discrete_inputs": {"expansion"},
    }

    capabilities = scanner._analyze_capabilities()

    assert capabilities.constant_flow is True
    assert capabilities.gwc_system is True
    assert capabilities.bypass_system is True
    assert capabilities.expansion_module is True
    assert capabilities.sensor_outside_temperature is True


async def test_analyze_capabilities_flag_presence():
    """Capabilities should reflect register presence and absence."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
    scanner.available_registers = {
        "input_registers": {"constant_flow_active", "outside_temperature"},
        "holding_registers": {"gwc_mode", "airing_start_time"},
        "coil_registers": set(),
        "discrete_inputs": {"expansion"},
    }
    capabilities = scanner._analyze_capabilities()
    assert capabilities.constant_flow is True
    assert capabilities.sensor_outside_temperature is True
    assert capabilities.expansion_module is True
    assert capabilities.gwc_system is True
    assert capabilities.weekly_schedule is True

    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    capabilities = scanner._analyze_capabilities()
    assert capabilities.constant_flow is False
    assert capabilities.sensor_outside_temperature is False
    assert capabilities.expansion_module is False
    assert capabilities.gwc_system is False
    assert capabilities.weekly_schedule is False


async def test_capability_rules_detect_heating_and_bypass():
    """Capability rules infer heating and bypass systems from registers."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
    scanner.available_registers = {
        "input_registers": {"heater_active"},
        "holding_registers": {"bypass_position"},
        "coil_registers": set(),
        "discrete_inputs": set(),
    }

    capabilities = scanner._analyze_capabilities()

    assert capabilities.heating_system is True
    assert capabilities.bypass_system is True


async def test_scan_device_includes_capabilities_in_device_info():
    """Detected capabilities are exposed on device info returned by scanner."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    info = ScannerDeviceInfo(
        model="m", firmware="f", serial_number="s", capabilities=["heating_system"]
    )
    caps = DeviceCapabilities(heating_system=True)

    with patch.object(scanner, "scan", AsyncMock(return_value=(info, caps, {}))):
        scanner.connection_mode = CONNECTION_MODE_TCP
        result = await scanner.scan_device()

    assert result["device_info"]["capabilities"] == ["heating_system"]


async def test_capability_count_includes_booleans(caplog):
    """Log should count boolean capabilities even though bool is an int subclass."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(empty_regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)

    caps = DeviceCapabilities(
        basic_control=True,
        expansion_module=True,
        temperature_sensors={"outside"},
        temperature_sensors_count=1,
    )

    with patch.object(scanner, "_analyze_capabilities", return_value=caps):
        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client_class.return_value = mock_client

            with (
                patch.object(scanner, "_read_input", AsyncMock(return_value=[])),
                patch.object(scanner, "_read_holding", AsyncMock(return_value=[])),
                patch.object(scanner, "_read_coil", AsyncMock(return_value=[])),
                patch.object(scanner, "_read_discrete", AsyncMock(return_value=[])),
            ):
                with caplog.at_level(logging.INFO):
                    scanner.connection_mode = CONNECTION_MODE_TCP
                    await scanner.scan_device()

    assert any("2 capabilities" in record.message for record in caplog.records)
