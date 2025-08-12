"""Test device scanner for ThesslaGreen Modbus integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.const import (
    SENSOR_UNAVAILABLE,
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
)
from custom_components.thessla_green_modbus.registers import (
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
)


pytestmark = pytest.mark.asyncio


async def test_device_scanner_initialization():
    """Test device scanner initialization."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    
    assert scanner.host == "192.168.1.100"
    assert scanner.port == 502
    assert scanner.slave_id == 10


async def test_scan_device_success():
    """Test successful device scan with dynamic register scanning."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)

    async def fake_read_input(client, address, count):
        data = [1] * count
        if address == 0:
            data[0:3] = [4, 85, 0]
        return data

    async def fake_read_holding(client, address, count):
        return [1] * count

    async def fake_read_coil(client, address, count):
        return [False] * count

    async def fake_read_discrete(client, address, count):
        return [False] * count

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with patch.object(
            scanner, "_read_input", AsyncMock(side_effect=fake_read_input)
        ), patch.object(
            scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)
        ), patch.object(
            scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)
        ), patch.object(
            scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)
        ):
            result = await scanner.scan_device()

    assert set(result["available_registers"]["input_registers"]) == set(
        INPUT_REGISTERS.keys()
    )
    assert set(result["available_registers"]["holding_registers"]) == set(
        HOLDING_REGISTERS.keys()
    )
    assert set(result["available_registers"]["coil_registers"]) == set(
        COIL_REGISTERS.keys()
    )
    assert set(result["available_registers"]["discrete_inputs"]) == set(
        DISCRETE_INPUT_REGISTERS.keys()
    )
    assert result["device_info"]["firmware"] == "4.85.0"


async def test_scan_device_connection_failure():
    """Test device scan with connection failure."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    
    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Failed to connect"):
            await scanner.scan_device()
        await scanner.close()


async def test_is_valid_register_value():
    """Test register value validation."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    
    # Valid values
    assert scanner._is_valid_register_value("test_register", 100) is True
    assert scanner._is_valid_register_value("test_register", 0) is True
    
    # Invalid temperature sensor value
    assert (
        scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE)
        is False
    )
    
    # Invalid air flow value
    assert scanner._is_valid_register_value("supply_air_flow", 65535) is False


async def test_analyze_capabilities():
    """Test capability analysis."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    
    # Mock available registers
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


@pytest.mark.parametrize("async_close", [True, False])
async def test_close_terminates_client(async_close):
    """Ensure close() handles both async and sync client close methods."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    mock_client = AsyncMock() if async_close else MagicMock()
    scanner._client = mock_client

    await scanner.close()

    if async_close:
        mock_client.close.assert_called_once()
        mock_client.close.assert_awaited_once()
    else:
        mock_client.close.assert_called_once()

    assert scanner._client is None
