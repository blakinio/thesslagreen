"""Coordinator and scanner update behavior tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE


class TestThesslaGreenModbusCoordinator:
    @pytest.fixture
    def coordinator_data(self):
        from custom_components.thessla_green_modbus.coordinator import (
            ThesslaGreenModbusCoordinator,
        )

        hass = MagicMock()
        coordinator = ThesslaGreenModbusCoordinator.from_params(
            hass=hass,
            host="192.168.1.100",
            port=502,
            slave_id=10,
            name="Test",
            scan_interval=30,
            timeout=10,
            retry=3,
        )
        coordinator.available_registers = {
            "input_registers": {"outside_temperature", "supply_temperature"},
            "holding_registers": {"mode", "on_off_panel_mode"},
        }
        return coordinator

    @pytest.mark.asyncio
    async def test_coordinator_data_update(self, coordinator_data):
        mock_data = {
            "outside_temperature": 20.5,
            "supply_temperature": 22.0,
            "mode": 0,
            "on_off_panel_mode": 1,
        }
        coordinator_data.client = MagicMock()
        with (
            patch.object(coordinator_data, "_ensure_connection", AsyncMock()),
            patch.object(
                coordinator_data,
                "_read_input_registers_optimized",
                AsyncMock(return_value=mock_data),
            ),
            patch.object(
                coordinator_data,
                "_read_holding_registers_optimized",
                AsyncMock(return_value={}),
            ),
            patch.object(
                coordinator_data,
                "_read_coil_registers_optimized",
                AsyncMock(return_value={}),
            ),
            patch.object(
                coordinator_data,
                "_read_discrete_inputs_optimized",
                AsyncMock(return_value={}),
            ),
            patch.object(coordinator_data, "_post_process_data", side_effect=lambda d: d),
        ):
            result = await coordinator_data._async_update_data()

        assert "outside_temperature" in result
        assert result["outside_temperature"] == 20.5

    @pytest.mark.asyncio
    async def test_coordinator_write_register(self, coordinator_data):
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        mock_client = AsyncMock()
        mock_client.write_register.return_value = mock_response
        with patch.object(coordinator_data, "_ensure_connection", AsyncMock()):
            coordinator_data.client = mock_client
            result = await coordinator_data.async_write_register("mode", 1)
        assert result is True

    @pytest.mark.asyncio
    async def test_coordinator_write_invalid_register(self, coordinator_data):
        result = await coordinator_data.async_write_register("invalid_register", 1)
        assert result is False

    def test_signed_value_processing(self, coordinator_data):
        assert coordinator_data._process_register_value("outside_temperature", 205) == 20.5
        assert (
            coordinator_data._process_register_value(
                "outside_temperature", SENSOR_UNAVAILABLE
            )
            is None
        )
        assert (
            coordinator_data._process_register_value(
                "heating_temperature", SENSOR_UNAVAILABLE
            )
            is None
        )
        assert coordinator_data._process_register_value("outside_temperature", 65486) == -5.0
        assert coordinator_data._process_register_value("supply_temperature", 65511) == -2.5
        assert coordinator_data._process_register_value("supply_flow_rate", 65436) == -100
        assert (
            coordinator_data._process_register_value(
                "exhaust_flow_rate", SENSOR_UNAVAILABLE
            )
            == SENSOR_UNAVAILABLE
        )

    def test_register_grouping(self, coordinator_data):
        from custom_components.thessla_green_modbus._coordinator_register_processing import (
            create_consecutive_groups,
        )

        registers = {"reg1": 16, "reg2": 17, "reg3": 18, "reg4": 32, "reg5": 33}
        groups = create_consecutive_groups(registers)
        assert len(groups) == 2
        start_addresses = [start for start, *_ in groups]
        assert 16 in start_addresses
        assert 32 in start_addresses
        for start, count, key_map in groups:
            if start == 16:
                assert count == 3
                assert len(key_map) == 3
            if start == 32:
                assert count == 2
                assert len(key_map) == 2


class TestThesslaGreenDeviceScanner:
    @pytest.mark.asyncio
    async def test_scanner_core_success(self):
        from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
        expected = {
            "available_registers": {
                "input_registers": set(),
                "holding_registers": set(),
            },
            "device_info": {"firmware": "4.85.2", "device_name": "TestDevice"},
            "capabilities": {},
        }
        with patch.object(scanner, "scan", AsyncMock(return_value=expected)):
            mock_transport = AsyncMock()
            mock_transport.ensure_connected = AsyncMock()
            mock_transport.is_connected.return_value = True
            mock_transport.close = AsyncMock()
            with patch.object(
                scanner,
                "_build_auto_tcp_attempts",
                return_value=[("tcp", mock_transport, 5.0)],
            ):
                result = await scanner.scan_device()
        assert "available_registers" in result
        assert "device_info" in result
        assert "capabilities" in result
        assert result["device_info"]["firmware"] == "4.85.2"

    def test_register_value_validation(self):
        from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

        scanner = asyncio.run(ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10))
        assert scanner._is_valid_register_value("test_register", 100) is True
        assert scanner._is_valid_register_value("mode", 1) is True
        assert scanner._is_valid_register_value("schedule_summer_mon_1", 1024) is True
        assert scanner._is_valid_register_value("schedule_summer_mon_1", 8704) is True
        assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is True
        assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is True
        assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is True
        assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is True
        assert scanner._is_valid_register_value("supply_air_flow", 65535) is False
        assert scanner._is_valid_register_value("mode", 5) is False
        scanner._register_ranges["schedule_start_time"] = (0, 2359)
        assert scanner._is_valid_register_value("schedule_start_time", 2078) is True
        assert scanner._is_valid_register_value("schedule_start_time", 2048) is True
        assert scanner._is_valid_register_value("schedule_start_time", 9312) is False
        assert scanner._is_valid_register_value("schedule_start_time", 2400) is False

    def test_capability_analysis(self):
        from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

        scanner = asyncio.run(ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10))
        scanner.available_registers = {
            "input_registers": {
                "constant_flow_active",
                "outside_temperature",
                "supply_temperature",
            },
            "holding_registers": {"gwc_mode", "bypass_mode", "mode", "on_off_panel_mode"},
            "coil_registers": {"power_supply_fans", "gwc", "bypass"},
            "discrete_inputs": {"expansion", "contamination_sensor"},
        }
        capabilities = scanner._analyze_capabilities().as_dict()
        assert capabilities["basic_control"] is True
        assert capabilities["constant_flow"] is True
        assert capabilities["gwc_system"] is True
        assert capabilities["bypass_system"] is True
        assert capabilities["expansion_module"] is True
        assert capabilities["sensor_outside_temperature"] is True
        assert capabilities["temperature_sensors_count"] == 2


class TestPerformanceOptimizations:
    @pytest.mark.asyncio
    async def test_register_grouping_performance(self):
        from custom_components.thessla_green_modbus._coordinator_register_processing import (
            create_consecutive_groups,
        )

        test_registers = {f"reg_{i}": 4096 + i for i in range(50)}
        groups = create_consecutive_groups(test_registers)
        assert len(groups) < len(test_registers)
        total_grouped = sum(len(key_map) for _, _, key_map in groups)
        assert total_grouped == len(test_registers)

    @pytest.mark.asyncio
    async def test_scan_optimization_stats(self):
        from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
        fake_transport = MagicMock()
        fake_transport.ensure_connected = AsyncMock()
        fake_transport.close = AsyncMock()
        fake_transport.read_input_registers = AsyncMock(return_value=MagicMock())
        fake_result = {
            "scan_stats": {
                "total_attempts": 1,
                "successful_reads": 1,
                "scan_duration": 0.01,
            }
        }
        with (
            patch.object(
                scanner,
                "_build_auto_tcp_attempts",
                return_value=[("tcp", fake_transport, 1.0)],
            ),
            patch.object(scanner, "scan", AsyncMock(return_value=fake_result)),
            patch.object(scanner, "close", AsyncMock()),
        ):
            result = await scanner.scan_device()
        assert "scan_stats" in result
        stats = result["scan_stats"]
        assert "total_attempts" in stats
        assert "successful_reads" in stats
        assert "scan_duration" in stats
        assert stats["scan_duration"] > 0
