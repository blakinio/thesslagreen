"""Test device scanner for ThesslaGreen Modbus integration."""
import pytest
from unittest.mock import MagicMock, patch

pytest.skip("Requires Home Assistant environment", allow_module_level=True)

from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner


@pytest.fixture
def mock_modbus_response():
    """Mock Modbus response."""
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [4, 85, 0]  # Version 4.85.0
    response.bits = [True, False, True]
    return response


async def test_device_scanner_initialization():
    """Test device scanner initialization."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    
    assert scanner.host == "192.168.1.100"
    assert scanner.port == 502
    assert scanner.slave_id == 10


async def test_scan_device_success(mock_modbus_response):
    """Test successful device scan."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    
    with patch("pymodbus.client.ModbusTcpClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.read_input_registers.return_value = mock_modbus_response
        mock_client.read_holding_registers.return_value = mock_modbus_response
        mock_client.read_coils.return_value = mock_modbus_response
        mock_client.read_discrete_inputs.return_value = mock_modbus_response
        mock_client_class.return_value = mock_client
        
        result = await scanner.scan_device()
        
        assert "available_registers" in result
        assert "device_info" in result
        assert "capabilities" in result
        assert result["device_info"]["firmware"] == "4.85.0"


async def test_scan_device_connection_failure():
    """Test device scan with connection failure."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    
    with patch("pymodbus.client.ModbusTcpClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client
        
        with pytest.raises(Exception, match="Failed to connect to device"):
            await scanner.scan_device()


async def test_is_valid_register_value():
    """Test register value validation."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    
    # Valid values
    assert scanner._is_valid_register_value("test_register", 100) is True
    assert scanner._is_valid_register_value("test_register", 0) is True
    
    # Invalid temperature sensor value
    assert scanner._is_valid_register_value("outside_temperature", 32768) is False
    
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
    
    assert capabilities["constant_flow"] is True
    assert capabilities["gwc_system"] is True
    assert capabilities["bypass_system"] is True
    assert capabilities["expansion_module"] is True
    assert capabilities["sensor_outside_temperature"] is True


async def test_group_registers_by_range():
    """Test register grouping by address ranges."""
    scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
    
    registers = {
        "reg1": 0x0010,
        "reg2": 0x0011,
        "reg3": 0x0012,
        "reg4": 0x0020,  # Gap of 14, should start new chunk
        "reg5": 0x0021,
    }
    
    chunks = scanner._group_registers_by_range(registers, max_gap=10)
    
    # Should have 2 chunks
    assert len(chunks) == 2
    assert 0x0010 in chunks
    assert 0x0020 in chunks
    
    # First chunk should have reg1, reg2, reg3
    assert len(chunks[0x0010]) == 3
    
    # Second chunk should have reg4, reg5
    assert len(chunks[0x0020]) == 2