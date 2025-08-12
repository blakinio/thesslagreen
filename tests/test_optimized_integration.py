"""Comprehensive test suite for ThesslaGreen Modbus integration - OPTIMIZED VERSION."""
import pytest
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import CoordinatorMock

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady

# Setup logging for tests
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class TestThesslaGreenIntegration:
    """Test the main integration setup and teardown."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {}
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.services = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        hass.services.async_register = MagicMock()
        hass.services.async_remove = MagicMock()
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.data = {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 502,
            "slave_id": 10,
        }
        entry.options = {
            "scan_interval": 30,
            "timeout": 10,
            "retry": 3,
        }
        entry.add_update_listener = MagicMock()
        entry.async_on_unload = MagicMock()
        return entry

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with realistic data."""
        coordinator = CoordinatorMock()
        coordinator.host = "192.168.1.100"
        coordinator.port = 502
        coordinator.slave_id = 10
        coordinator.last_update_success = True
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.async_shutdown = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.async_write_register = AsyncMock(return_value=True)
        
        # Realistic device data
        coordinator.data = {
            "outside_temperature": 15.5,
            "supply_temperature": 22.0,
            "exhaust_temperature": 18.5,
            "mode": 0,
            "on_off_panel_mode": 1,
            "supply_percentage": 50,
            "exhaust_percentage": 50,
            "special_mode": 0,
            "constant_flow_active": 1,
            "gwc_mode": 0,
            "bypass_mode": 0,
        }
        
        # Device scan result sets device_info and capabilities
        coordinator.device_scan_result = {
            "device_info": {
                "device_name": "ThesslaGreen AirPack Test",
                "firmware": "4.85.0",
                "serial_number": "S/N: 1234 5678 9abc",
                "processor": "ATmega2561",
            },
            "capabilities": {
                "basic_control": True,
                "constant_flow": True,
                "gwc_system": True,
                "bypass_system": True,
                "comfort_mode": True,
                "expansion_module": False,
                "temperature_sensors_count": 7,
                "model_type": "AirPack Home Energy+ with CF and GWC",
            },
        }
        
        # Available registers
        coordinator.available_registers = {
            "input_registers": {
                "outside_temperature", "supply_temperature", "exhaust_temperature",
                "firmware_major", "firmware_minor", "firmware_patch",
                "constant_flow_active", "supply_percentage", "exhaust_percentage",
            },
            "holding_registers": {
                "mode", "on_off_panel_mode", "air_flow_rate_manual",
                "special_mode", "gwc_mode", "bypass_mode",
            },
            "coil_registers": {"power_supply_fans", "bypass", "gwc"},
            "discrete_inputs": {"expansion", "contamination_sensor"},
        }
        
        return coordinator

    @pytest.mark.asyncio
    async def test_async_setup_entry_success(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test successful setup of config entry."""
        from custom_components.thessla_green_modbus import async_setup_entry
        from custom_components.thessla_green_modbus.const import DOMAIN
        
        with patch(
            "custom_components.thessla_green_modbus.ThesslaGreenCoordinator",
            return_value=mock_coordinator
        ):
            result = await async_setup_entry(mock_hass, mock_config_entry)
            
            assert result is True
            assert DOMAIN in mock_hass.data
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
            mock_hass.config_entries.async_forward_entry_setups.assert_called_once()
            mock_coordinator.async_config_entry_first_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_entry_connection_failure(self, mock_hass, mock_config_entry):
        """Test setup failure due to connection issues."""
        from custom_components.thessla_green_modbus import async_setup_entry
        
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        
        with patch(
            "custom_components.thessla_green_modbus.ThesslaGreenCoordinator",
            return_value=mock_coordinator
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_async_unload_entry_success(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test successful unloading of config entry."""
        from custom_components.thessla_green_modbus import async_unload_entry
        from custom_components.thessla_green_modbus.const import DOMAIN
        
        # Setup initial state
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}
        
        result = await async_unload_entry(mock_hass, mock_config_entry)
        
        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once()
        mock_coordinator.async_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_services_registration(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test that services are properly registered."""
        from custom_components.thessla_green_modbus import async_setup_entry
        
        with patch(
            "custom_components.thessla_green_modbus.ThesslaGreenCoordinator",
            return_value=mock_coordinator
        ):
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Check that services were registered
            service_calls = mock_hass.services.async_register.call_args_list
            service_names = [call[0][1] for call in service_calls]
            
            expected_services = ["set_mode", "set_intensity", "set_special_function"]
            for service in expected_services:
                assert service in service_names


class TestThesslaGreenCoordinator:
    """Test the data coordinator functionality."""

    @pytest.fixture
    def coordinator_data(self):
        """Create coordinator with test data."""
        from custom_components.thessla_green_modbus.coordinator import ThesslaGreenCoordinator
        
        hass = MagicMock()
        coordinator = ThesslaGreenCoordinator(
            hass=hass,
            host="192.168.1.100",
            port=502,
            slave_id=10,
            scan_interval=30,
            timeout=10,
            retry=3,
        )
        
        # Mock the client and successful data
        coordinator.available_registers = {
            "input_registers": {"outside_temperature", "supply_temperature"},
            "holding_registers": {"mode", "on_off_panel_mode"},
        }
        
        return coordinator

    @pytest.mark.asyncio
    async def test_coordinator_data_update(self, coordinator_data):
        """Test data update mechanism."""
        mock_data = {
            "outside_temperature": 20.5,
            "supply_temperature": 22.0,
            "mode": 0,
            "on_off_panel_mode": 1,
        }
        
        with patch.object(
            coordinator_data.hass,
            "async_add_executor_job",
            AsyncMock(return_value=mock_data),
        ) as mock_executor:
            result = await coordinator_data._async_update_data()

        mock_executor.assert_awaited_once_with(coordinator_data._update_data_sync)
        assert result == mock_data
        assert "outside_temperature" in result
        assert result["outside_temperature"] == 20.5

    @pytest.mark.asyncio
    async def test_coordinator_write_register(self, coordinator_data):
        """Test register writing functionality."""
        with patch.object(
            coordinator_data.hass,
            "async_add_executor_job",
            AsyncMock(return_value=True),
        ) as mock_executor:
            result = await coordinator_data.async_write_register("mode", 1)

        mock_executor.assert_awaited_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_coordinator_write_invalid_register(self, coordinator_data):
        """Test writing to invalid register."""
        result = await coordinator_data.async_write_register("invalid_register", 1)
        assert result is False

    def test_temperature_value_processing(self, coordinator_data):
        """Test temperature value processing."""
        # Valid temperature (20.5°C -> raw value 205)
        result = coordinator_data._process_register_value("outside_temperature", 205)
        assert result == 20.5

        # Invalid temperature (sensor disconnected)
        result = coordinator_data._process_register_value("outside_temperature", 0x8000)
        assert result is None

        # Negative temperature (-5.0°C -> raw value 65486)
        result = coordinator_data._process_register_value("outside_temperature", 65486)
        assert result == -5.0

    def test_register_grouping(self, coordinator_data):
        """Test register grouping algorithm."""
        registers = {
            "reg1": 0x0010,
            "reg2": 0x0011,
            "reg3": 0x0012,
            "reg4": 0x0020,  # Gap of 14
            "reg5": 0x0021,
        }

        groups = coordinator_data._create_consecutive_groups(registers)

        # Should create 2 groups
        assert len(groups) == 2
        start_addresses = [start for start, *_ in groups]
        assert 0x0010 in start_addresses
        assert 0x0020 in start_addresses

        for start, count, key_map in groups:
            if start == 0x0010:
                assert count == 3
                assert len(key_map) == 3
            if start == 0x0020:
                assert count == 2
                assert len(key_map) == 2


class TestThesslaGreenConfigFlow:
    """Test the configuration flow."""

    @pytest.fixture
    def mock_scanner(self):
        """Create a mock device scanner."""
        scanner_result = {
            "available_registers": {
                "input_registers": {"outside_temperature", "supply_temperature"},
                "holding_registers": {"mode", "on_off_panel_mode"},
            },
            "device_info": {
                "device_name": "ThesslaGreen AirPack Test",
                "firmware": "4.85.0",
            },
            "capabilities": {
                "basic_control": True,
                "constant_flow": True,
            },
        }
        
        with patch(
            "custom_components.thessla_green_modbus.device_scanner.ThesslaGreenDeviceScanner.scan_device",
            return_value=scanner_result
        ):
            yield

    @pytest.mark.asyncio
    async def test_config_flow_user_step(self, mock_scanner):
        """Test the user configuration step."""
        from custom_components.thessla_green_modbus.config_flow import ConfigFlow
        
        flow = ConfigFlow()
        flow.hass = MagicMock()
        
        # Test form display
        result = await flow.async_step_user()
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_config_flow_user_input_success(self, mock_scanner):
        """Test successful user input processing."""
        from custom_components.thessla_green_modbus.config_flow import ConfigFlow
        
        flow = ConfigFlow()
        flow.hass = MagicMock()
        
        with patch.object(flow, 'async_set_unique_id'), \
             patch.object(flow, '_abort_if_unique_id_configured'):
            
            result = await flow.async_step_user({
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
            })
            
            assert result["type"] == "create_entry"
            assert "ThesslaGreen AirPack Test" in result["title"]

    @pytest.mark.asyncio
    async def test_config_flow_cannot_connect(self):
        """Test connection failure handling."""
        from custom_components.thessla_green_modbus.config_flow import ConfigFlow, CannotConnect
        
        flow = ConfigFlow()
        flow.hass = MagicMock()
        
        with patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            side_effect=CannotConnect
        ):
            result = await flow.async_step_user({
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
            })
            
            assert result["type"] == "form"
            assert result["errors"]["base"] == "cannot_connect"


class TestThesslaGreenDeviceScanner:
    """Test the device scanner functionality."""

    @pytest.fixture
    def mock_modbus_client(self):
        """Create a mock Modbus client."""
        client = MagicMock()
        client.connect.return_value = True
        client.close = MagicMock()
        
        # Mock successful responses
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        mock_response.registers = [4, 85, 0, 1, 2]  # Firmware 4.85.2
        mock_response.bits = [True, False, True]
        
        client.read_input_registers.return_value = mock_response
        client.read_holding_registers.return_value = mock_response
        client.read_coils.return_value = mock_response
        client.read_discrete_inputs.return_value = mock_response
        
        return client

    @pytest.mark.asyncio
    async def test_device_scanner_success(self, mock_modbus_client):
        """Test successful device scanning."""
        from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner
        
        scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
        
        with patch("pymodbus.client.ModbusTcpClient", return_value=mock_modbus_client):
            result = await scanner.scan_device()
            
            assert "available_registers" in result
            assert "device_info" in result
            assert "capabilities" in result
            assert result["device_info"]["firmware"] == "4.85.2"

    @pytest.mark.asyncio 
    async def test_device_scanner_connection_failure(self):
        """Test scanner behavior on connection failure."""
        from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner
        
        scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
        
        mock_client = MagicMock()
        mock_client.connect.return_value = False
        
        with patch("pymodbus.client.ModbusTcpClient", return_value=mock_client):
            with pytest.raises(Exception, match="Failed to connect to device"):
                await scanner.scan_device()

    def test_register_value_validation(self):
        """Test register value validation logic."""
        from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner
        
        scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
        
        # Valid values
        assert scanner._is_valid_register_value("test_register", 100) is True
        assert scanner._is_valid_register_value("mode", 1) is True
        
        # Invalid temperature sensor value
        assert scanner._is_valid_register_value("outside_temperature", 32768) is False
        
        # Invalid air flow value
        assert scanner._is_valid_register_value("supply_air_flow", 65535) is False
        
        # Invalid mode value
        assert scanner._is_valid_register_value("mode", 5) is False

    def test_capability_analysis(self):
        """Test capability analysis logic."""
        from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner
        
        scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
        scanner.available_registers = {
            "input_registers": {"constant_flow_active", "outside_temperature", "supply_temperature"},
            "holding_registers": {"gwc_mode", "bypass_mode", "mode", "on_off_panel_mode"},
            "coil_registers": {"power_supply_fans", "gwc", "bypass"},
            "discrete_inputs": {"expansion", "contamination_sensor"},
        }
        
        capabilities = scanner._analyze_capabilities_enhanced()
        
        assert capabilities["basic_control"] is True
        assert capabilities["constant_flow"] is True
        assert capabilities["gwc_system"] is True
        assert capabilities["bypass_system"] is True
        assert capabilities["expansion_module"] is True
        assert capabilities["sensor_outside_temperature"] is True
        assert capabilities["temperature_sensors_count"] == 2


class TestThesslaGreenClimate:
    """Test the climate entity functionality."""

    @pytest.fixture
    def mock_climate_coordinator(self):
        """Create a coordinator specifically for climate testing."""
        coordinator = CoordinatorMock()
        coordinator.host = "192.168.1.100"
        coordinator.slave_id = 10
        coordinator.device_scan_result = {
            "device_info": {
                "device_name": "Test AirPack",
                "firmware": "4.85.0",
            }
        }
        coordinator.available_registers = {
            "holding_registers": {"mode", "on_off_panel_mode", "air_flow_rate_manual"}
        }
        coordinator.data = {
            "on_off_panel_mode": 1,
            "mode": 0,
            "supply_temperature": 22.0,
            "supply_percentage": 50,
            "air_flow_rate_manual": 60,
            "special_mode": 0,
        }
        coordinator.async_write_register = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        return coordinator

    @pytest.mark.asyncio
    async def test_climate_entity_creation(self, mock_climate_coordinator):
        """Test climate entity creation and basic properties."""
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
        from homeassistant.components.climate import HVACMode
        
        climate = ThesslaGreenClimate(mock_climate_coordinator)
        
        assert climate.name == "Test AirPack Rekuperator"
        assert HVACMode.AUTO in climate.hvac_modes
        assert HVACMode.FAN_ONLY in climate.hvac_modes
        assert HVACMode.OFF in climate.hvac_modes
        assert climate.hvac_mode == HVACMode.AUTO  # mode = 0

    @pytest.mark.asyncio
    async def test_climate_set_hvac_mode(self, mock_climate_coordinator):
        """Test setting HVAC mode."""
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
        from homeassistant.components.climate import HVACMode
        
        climate = ThesslaGreenClimate(mock_climate_coordinator)
        
        await climate.async_set_hvac_mode(HVACMode.FAN_ONLY)
        
        mock_climate_coordinator.async_write_register.assert_called_with(
            "mode", 1, refresh=False
        )
        mock_climate_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_climate_set_preset_mode(self, mock_climate_coordinator):
        """Test setting preset mode."""
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
        from homeassistant.components.climate import PRESET_ECO
        
        climate = ThesslaGreenClimate(mock_climate_coordinator)
        
        await climate.async_set_preset_mode(PRESET_ECO)
        
        # Should set manual mode and low intensity
        assert mock_climate_coordinator.async_write_register.call_count >= 2

    def test_climate_fan_mode_calculation(self, mock_climate_coordinator):
        """Test fan mode calculation."""
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
        
        climate = ThesslaGreenClimate(mock_climate_coordinator)
        
        # Test manual mode intensity
        mock_climate_coordinator.data["mode"] = 1  # Manual mode
        mock_climate_coordinator.data["air_flow_rate_manual"] = 65
        
        fan_mode = climate.fan_mode
        assert fan_mode == "70%"  # Should round to nearest 10%


class TestPerformanceOptimizations:
    """Test performance optimizations and benchmarks."""

    @pytest.mark.asyncio
    async def test_register_grouping_performance(self):
        """Test that register grouping reduces Modbus calls."""
        from custom_components.thessla_green_modbus.coordinator import ThesslaGreenCoordinator
        
        # Create coordinator with many registers
        hass = MagicMock()
        coordinator = ThesslaGreenCoordinator(
            hass=hass, host="192.168.1.100", port=502, slave_id=10,
            scan_interval=30, timeout=10, retry=3
        )
        
        # Simulate many sequential registers
        test_registers = {f"reg_{i}": 0x1000 + i for i in range(50)}
        
        groups = coordinator._create_consecutive_groups(test_registers)

        # Should group into fewer batches than individual registers
        assert len(groups) < len(test_registers)

        # Verify total registers are preserved
        total_grouped = sum(len(key_map) for _, _, key_map in groups)
        assert total_grouped == len(test_registers)

    @pytest.mark.asyncio
    async def test_scan_optimization_stats(self):
        """Test that device scanner provides optimization statistics."""
        from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner
        
        scanner = ThesslaGreenDeviceScanner("192.168.1.100", 502, 10)
        
        # Mock successful scan
        with patch("pymodbus.client.ModbusTcpClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.connect.return_value = True
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            mock_response.registers = [4, 85, 0]
            mock_response.bits = [True, False]
            mock_client.read_input_registers.return_value = mock_response
            mock_client.read_holding_registers.return_value = mock_response
            mock_client.read_coils.return_value = mock_response
            mock_client.read_discrete_inputs.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            result = await scanner.scan_device()
            
            assert "scan_stats" in result
            stats = result["scan_stats"]
            assert "total_attempts" in stats
            assert "successful_reads" in stats
            assert "scan_duration" in stats
            assert stats["scan_duration"] > 0


if __name__ == "__main__":
    """Run the test suite."""
    import sys
    import time
    
    print("🧪 Running Comprehensive ThesslaGreen Modbus Integration Tests...")
    start_time = time.time()
    
    # Run tests with pytest
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-ra",
        "--asyncio-mode=auto",
    ])
    
    duration = time.time() - start_time
    
    if exit_code == 0:
        print(f"✅ All tests passed! ({duration:.2f}s)")
    else:
        print(f"❌ Some tests failed! ({duration:.2f}s)")
    
    sys.exit(exit_code)