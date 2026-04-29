"""Register/value-oriented tests for device scanner."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP, SENSOR_UNAVAILABLE
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value
from custom_components.thessla_green_modbus.utils import (
    _decode_aatt,
    _decode_bcd_time,
    _decode_register_time,
)

INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function(4)}

pytestmark = pytest.mark.asyncio


async def test_missing_register_logged_once(caplog):
    """Each missing register should trigger only one read and log entry."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(empty_regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    call_log: list[tuple[int, int]] = []

    async def fake_read_input(client, address, count, **kwargs):
        call_log.append((address, count))
        if address == 0 and count == 5:
            return [4, 85, 0, 0, 0]
        if address == 24 and count == 6:
            return [0] * 6
        if address == 1 and count == 2:
            return None
        if address == 1 and count == 1:
            return [1]
        if address == 2 and count == 1:
            return None
        return [0] * count

    scanner._input_register_map = {"reg_ok": 1, "reg_missing": 2}
    scanner._holding_register_map = {}
    scanner._coil_register_map = {}
    scanner._discrete_input_register_map = {}
    scanner._known_missing_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    scanner._update_known_missing_addresses()

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client.read_input_registers = AsyncMock(
            return_value=MagicMock(isError=lambda: False, registers=[4, 85, 0, 0, 0])
        )
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(return_value=[0])),
            patch.object(scanner, "_read_coil", AsyncMock(return_value=[False])),
            patch.object(scanner, "_read_discrete", AsyncMock(return_value=[False])),
            patch.object(scanner, "_is_valid_register_value", return_value=True),
        ):
            caplog.set_level(logging.DEBUG)
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    # Block read + single read for each register
    assert call_log.count((1, 2)) == 1
    assert call_log.count((1, 1)) == 1
    assert call_log.count((2, 1)) == 1

    # Missing register logged only once
    assert caplog.text.count("Failed to read input_registers register 2") == 1

    # Only valid register is reported as available
    assert "reg_ok" in result["available_registers"]["input_registers"]
    assert "reg_missing" not in result["available_registers"]["input_registers"]


async def test_is_valid_register_value():
    """Test register value validation."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
    scanner._register_ranges["supply_percentage"] = (0, 100)
    scanner._register_ranges["min_percentage"] = (0, 100)
    scanner._register_ranges["max_percentage"] = (0, 120)

    # Valid values
    assert scanner._is_valid_register_value("test_register", 100) is True
    assert scanner._is_valid_register_value("test_register", 0) is True

    # SENSOR_UNAVAILABLE (0x8000) means the register EXISTS but sensor is not connected.
    # The register must produce an entity (shown as "unavailable" in HA), so return True.
    assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is True
    assert scanner._is_valid_register_value("supply_flow_rate", SENSOR_UNAVAILABLE) is True

    # Mode values respect allowed set
    assert scanner._is_valid_register_value("mode", 1) is True
    assert scanner._is_valid_register_value("mode", 3) is False

    # Range from register metadata
    assert scanner._is_valid_register_value("supply_percentage", 100) is True
    with patch.object(scanner, "_log_invalid_value") as log_mock:
        assert scanner._is_valid_register_value("supply_percentage", 200) is False
        log_mock.assert_not_called()

    # Dynamic percentage limits should accept device-provided values
    assert scanner._is_valid_register_value("min_percentage", 20) is True
    assert scanner._is_valid_register_value("max_percentage", 120) is True

    assert scanner._is_valid_register_value("min_percentage", -1) is False
    assert scanner._is_valid_register_value("max_percentage", 200) is False
    with patch.object(scanner, "_log_invalid_value") as log_mock:
        assert scanner._is_valid_register_value("min_percentage", -1) is False
        assert scanner._is_valid_register_value("max_percentage", 200) is False
        log_mock.assert_not_called()
    # HH:MM time registers
    scanner._register_ranges["schedule_start_time"] = (0, 2359)
    assert scanner._is_valid_register_value("schedule_start_time", 2078) is True
    assert scanner._is_valid_register_value("schedule_start_time", 2048) is True
    assert scanner._is_valid_register_value("schedule_start_time", 9312) is False
    assert scanner._is_valid_register_value("schedule_start_time", 2400) is False
    # BCD encoded times should also be recognized as valid
    assert scanner._is_valid_register_value("schedule_winter_mon_4", 8704) is True
    # Typical schedule and setting values
    assert scanner._is_valid_register_value("schedule_summer_mon_1", 1024) is True
    assert scanner._is_valid_register_value("setting_winter_mon_1", 12844) is True


async def test_decode_register_time():
    """Verify time decoding for HH:MM byte-encoded values."""
    assert _decode_register_time(1024) == 240
    assert _decode_register_time(2078) == 510
    assert _decode_register_time(4660) == 1132
    assert _decode_register_time(9312) is None
    assert _decode_register_time(2400) is None


async def test_decode_bcd_time():
    """Verify time decoding for both BCD and decimal values."""
    assert _decode_bcd_time(1024) == 240
    assert _decode_bcd_time(4660) == 754
    assert _decode_bcd_time(2048) == 480
    assert _decode_bcd_time(9312) is None
    assert _decode_bcd_time(2400) is None


async def test_decode_aatt_value():
    """Verify decoding of combined airflow and temperature settings."""
    assert _decode_aatt(15400) == {"airflow_pct": 60, "temp_c": 20.0}
    assert _decode_aatt(12844) == {"airflow_pct": 50, "temp_c": 22.0}
    assert _decode_aatt(-1) is None
    assert _decode_aatt(65320) is None


async def test_format_register_value_schedule():
    """Formatted schedule registers should render as HH:MM."""
    assert _format_register_value("schedule_summer_mon_1", 1557) == "06:15"


async def test_format_register_value_manual_airing_le():
    """Little-endian manual airing times should decode correctly."""
    assert _format_register_value("manual_airing_time_to_start", 7688) == "08:30"


async def test_format_register_value_airing_schedule():
    """Airing schedule registers should render as HH:MM."""
    assert _format_register_value("airing_summer_mon", 1557) == "06:15"


async def test_format_register_value_airing_durations():
    """Airing mode duration registers should return raw minute values."""
    assert _format_register_value("airing_panel_mode_time", 15) == 15
    assert _format_register_value("airing_switch_mode_time", 30) == 30
    assert _format_register_value("airing_switch_mode_on_delay", 5) == 5
    assert _format_register_value("airing_switch_mode_off_delay", 10) == 10
    assert _format_register_value("airing_switch_coef", 2) == 2


async def test_format_register_value_setting():
    """Formatted setting registers should show percent and temperature."""
    assert _format_register_value("setting_winter_mon_1", 15400) == "60% @ 20°C"


async def test_format_register_value_invalid_time():
    """Invalid time registers should show raw hex with invalid marker."""
    assert _format_register_value("schedule_summer_mon_1", 9216) == "9216 (invalid)"


async def test_scan_excludes_unavailable_temperature():
    """Temperature register with SENSOR_UNAVAILABLE should be included (sensor disconnected, register exists)."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count, **kwargs):
        data = [1] * count
        if address == 0:
            data[0:3] = [4, 85, 0]
        temp_addr = INPUT_REGISTERS["outside_temperature"]
        if address <= temp_addr < address + count:
            data[temp_addr - address] = SENSOR_UNAVAILABLE
        return data

    async def fake_read_holding(client, address, count, **kwargs):
        return [1] * count

    async def fake_read_coil(client, address, count, **kwargs):
        return [False] * count

    async def fake_read_discrete(client, address, count, **kwargs):
        return [False] * count

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    assert "outside_temperature" in result["available_registers"]["input_registers"]


async def test_temperature_unavailable_no_warning(caplog):
    """SENSOR_UNAVAILABLE should not log a warning — register exists, sensor just not connected."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    caplog.set_level(logging.WARNING)
    assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is True
    assert "outside_temperature" not in caplog.text

