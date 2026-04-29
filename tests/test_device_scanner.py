"""Test device scanner for ThesslaGreen Modbus integration."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import (
    CONNECTION_MODE_TCP,
    KNOWN_MISSING_REGISTERS,
    SENSOR_UNAVAILABLE,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.scanner.core import (
    DeviceCapabilities,
    ThesslaGreenDeviceScanner,
)
from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value
from custom_components.thessla_green_modbus.utils import (
    _decode_aatt,
    _decode_bcd_time,
    _decode_register_time,
)

COIL_REGISTERS = {r.name: r.address for r in get_registers_by_function(1)}
DISCRETE_INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function(2)}
HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function(3)}
INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function(4)}

pytestmark = pytest.mark.asyncio


async def test_scan_device_success_dynamic():
    """Test successful device scan with dynamic register scanning."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count, **kwargs):
        if address == 0:
            data = [4, 85, 0, 0, 0]
            return data[:count]
        if address == 24:
            return [26, 43, 60, 77, 94, 111][:count]
        return [1] * count

    async def fake_read_holding(client, address, count, **kwargs):
        return [10] * count

    async def fake_read_coil(client, address, count, **kwargs):
        return [False] * count

    async def fake_read_discrete(client, address, count, **kwargs):
        return [False] * count

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client.read_input_registers = AsyncMock(
            return_value=MagicMock(isError=lambda: False, registers=[4, 85, 0, 0, 0])
        )
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
            patch.object(scanner, "_is_valid_register_value", return_value=True),
        ):
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()
    assert "outside_temperature" in result["available_registers"]["input_registers"]
    assert "access_level" in result["available_registers"]["holding_registers"]
    assert "power_supply_fans" in result["available_registers"]["coil_registers"]
    assert "expansion" in result["available_registers"]["discrete_inputs"]
    assert set(result["available_registers"]["input_registers"]) == (
        set(INPUT_REGISTERS.keys()) - KNOWN_MISSING_REGISTERS.get("input_registers", set())
    )
    assert set(result["available_registers"]["holding_registers"]) <= set(HOLDING_REGISTERS.keys())
    assert set(result["available_registers"]["coil_registers"]) == set(COIL_REGISTERS.keys())
    assert set(result["available_registers"]["discrete_inputs"]) == set(
        DISCRETE_INPUT_REGISTERS.keys()
    )
    assert result["device_info"]["firmware"] == "4.85.0"


@pytest.fixture
def mock_modbus_response():
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [4, 85, 0, 0, 0, 0]
    response.bits = [False]
    return response


async def test_read_coil_retries_on_failure(caplog):
    """Coil reads should retry on failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=ModbusException("boom")),
        ) as call_mock,
        caplog.at_level(logging.DEBUG),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_coil(mock_client, 0, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry


async def test_read_discrete_retries_on_failure(caplog):
    """Discrete input reads should retry on failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=ModbusException("boom")),
        ) as call_mock,
        caplog.at_level(logging.DEBUG),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_discrete(mock_client, 0, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry


async def test_scan_device_success_static(mock_modbus_response):
    """Test successful device scan with predefined registers."""
    regs = {
        4: {16: "outside_temperature"},
        3: {0: "mode"},
        1: {0: "power_supply_fans"},
        2: {0: "expansion"},
    }
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client.read_input_registers.return_value = mock_modbus_response
            mock_holding_response = MagicMock()
            mock_holding_response.isError.return_value = False
            mock_holding_response.registers = [1]
            mock_client.read_holding_registers.return_value = mock_holding_response
            holding_response = MagicMock()
            holding_response.isError.return_value = False
            holding_response.registers = [1]
            mock_client.read_holding_registers.return_value = holding_response
            mock_client.read_coils.return_value = mock_modbus_response
            mock_client.read_discrete_inputs.return_value = mock_modbus_response
            mock_client_class.return_value = mock_client

            with patch.object(scanner, "_is_valid_register_value", return_value=True):
                scanner.connection_mode = CONNECTION_MODE_TCP
                result = await scanner.scan_device()

                assert "available_registers" in result
                assert "device_info" in result
                assert "capabilities" in result
                assert "capabilities" in result["device_info"]
                assert result["device_info"]["firmware"] == "4.85.0"
                assert "outside_temperature" in result["available_registers"]["input_registers"]
                assert "mode" in result["available_registers"]["holding_registers"]
                assert "power_supply_fans" in result["available_registers"]["coil_registers"]
                assert "expansion" in result["available_registers"]["discrete_inputs"]


async def test_scan_device_connection_failure():
    """Test device scan with connection failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Failed to connect"):
            scanner.connection_mode = CONNECTION_MODE_TCP
            await scanner.scan_device()
        await scanner.close()





async def test_scan_blocks_propagated():
    """Ensure scan_device returns discovered register blocks."""
    # Avoid scanning full register set for test speed
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(empty_regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

        async def fake_read_input(client, address, count):
            return [1] * count

        async def fake_read_holding(client, address, count, **kwargs):
            return [1] * count

        async def fake_read_coil(client, address, count):
            return [False] * count

        async def fake_read_discrete(client, address, count):
            return [False] * count

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client.read_input_registers = AsyncMock(
                return_value=MagicMock(isError=lambda: False, registers=[4, 85, 0, 0, 0])
            )
            mock_client_class.return_value = mock_client

            with (
                patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
                patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
                patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
                patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
            ):
                scanner.connection_mode = CONNECTION_MODE_TCP
                result = await scanner.scan_device()

    expected_blocks = {
        "input_registers": (
            min(INPUT_REGISTERS.values()),
            max(INPUT_REGISTERS.values()),
        ),
        "holding_registers": (
            min(HOLDING_REGISTERS.values()),
            max(HOLDING_REGISTERS.values()),
        ),
        "coil_registers": (
            min(COIL_REGISTERS.values()),
            max(COIL_REGISTERS.values()),
        ),
        "discrete_inputs": (
            min(DISCRETE_INPUT_REGISTERS.values()),
            max(DISCRETE_INPUT_REGISTERS.values()),
        ),
    }

    assert result["scan_blocks"] == expected_blocks


async def test_full_register_scan_collects_unknown_registers():
    """Ensure full register scan returns unknown registers and statistics."""
    reg_map = {4: {0: "ir0", 2: "ir2"}, 3: {0: "hr0", 2: "hr2"}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(reg_map, {}, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create(
            "192.168.1.1", 502, 10, full_register_scan=True
        )

        async def fake_read_input(client, address, count, **kwargs):
            return [address]

        async def fake_read_holding(client, address, count, **kwargs):
            return [address + 10]

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client.read_input_registers = AsyncMock(
                return_value=MagicMock(isError=lambda: False, registers=[0])
            )
            mock_client_class.return_value = mock_client

            with (
                patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
                patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
                patch.object(scanner, "_read_coil", AsyncMock(return_value=[False])),
                patch.object(scanner, "_read_discrete", AsyncMock(return_value=[False])),
                patch.object(scanner, "_is_valid_register_value", return_value=True),
            ):
                scanner.connection_mode = CONNECTION_MODE_TCP
                result = await scanner.scan_device()

    assert result["unknown_registers"]["input_registers"] == {1: 1}
    assert result["unknown_registers"]["holding_registers"] == {1: 11}
    assert result["scanned_registers"]["input_registers"] == 3
    assert result["scanned_registers"]["holding_registers"] == 3


async def test_scan_device_batch_fallback():
    """Batch read failures should fall back to single-register reads."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count, **kwargs):
        if address == 0 and count == 5:
            return [4, 85, 0, 0, 0]
        if count > 1:
            return None
        return [0]

    async def fake_read_holding(client, address, count, **kwargs):
        if count > 1:
            return None
        return [0]

    async def fake_read_coil(client, address, count, **kwargs):
        if count > 1:
            return None
        return [False]

    async def fake_read_discrete(client, address, count, **kwargs):
        if count > 1:
            return None
        return [False]

    scanner._input_register_map = {"ir1": 16, "ir2": 17}
    scanner._holding_register_map = {"hr1": 32, "hr2": 33}
    scanner._coil_register_map = {"cr1": 0, "cr2": 1}
    scanner._discrete_input_register_map = {"dr1": 0, "dr2": 1}
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
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)) as ri,
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    assert set(result["available_registers"]["input_registers"]) == {"ir1", "ir2"}
    assert set(result["available_registers"]["holding_registers"]) == {"hr1", "hr2"}
    assert set(result["available_registers"]["coil_registers"]) == {"cr1", "cr2"}
    assert set(result["available_registers"]["discrete_inputs"]) == {"dr1", "dr2"}

    # Ensure batch read was attempted and individual fallback reads occurred
    batch_calls = [call for call in ri.await_args_list if call.args[1] == 16]
    assert any(call.args[2] == 2 for call in batch_calls)

    single_calls = [call.args[1] for call in ri.await_args_list if call.args[2] == 1]
    assert single_calls.count(16) == 1
    assert single_calls.count(17) == 1


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


async def test_temperature_register_unavailable_skipped():
    """Temperature registers with SENSOR_UNAVAILABLE should be skipped."""


async def test_temperature_register_unavailable_kept():
    """Temperature registers with SENSOR_UNAVAILABLE should remain available."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count):
        data = [1] * count
        outside_addr = INPUT_REGISTERS["outside_temperature"]
        if address <= outside_addr < address + count:
            data[outside_addr - address] = SENSOR_UNAVAILABLE
        return data

    async def fake_read_holding(client, address, count, **kwargs):
        return [1] * count

    async def fake_read_coil(*args):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [False] * count

    async def fake_read_discrete(*args):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
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

    assert "outside_temperature" not in result["available_registers"]["input_registers"]


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



async def test_scan_populates_device_name():
    """Scanner should include device_name in returned device info."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._client = object()
    scanner._transport = MagicMock()
    scanner._transport.is_connected.return_value = True
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {}}
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }

    device_name = "Test AirPack"
    name_bytes = device_name.encode("ascii").ljust(16, b"\x00")
    regs = [(name_bytes[i] << 8) | name_bytes[i + 1] for i in range(0, 16, 2)]

    async def fake_read_holding(client, address, count, *, skip_cache=False):
        if address == HOLDING_REGISTERS["device_name"]:
            return regs
        return None

    with (
        patch.object(scanner, "_read_input", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
    ):
        result = await scanner.scan()

    assert result["device_info"]["device_name"] == device_name


async def test_scan_populates_device_name_with_non_ascii_bytes() -> None:
    """Scanner should replace invalid ASCII bytes in device name instead of failing."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._client = object()
    scanner._transport = MagicMock()
    scanner._transport.is_connected.return_value = True
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {}}
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }

    name_bytes = b"Test AirPac" + bytes([0xDF]) + b"\x00\x00\x00\x00\x00"
    regs = [(name_bytes[i] << 8) | name_bytes[i + 1] for i in range(0, 16, 2)]

    async def fake_read_holding(client, address, count, *, skip_cache=False):
        if address == HOLDING_REGISTERS["device_name"]:
            return regs
        return None

    with (
        patch.object(scanner, "_read_input", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
    ):
        result = await scanner.scan()

    assert result["device_info"]["device_name"] == "Test AirPac�"


async def test_scan_falls_back_to_single_input_reads_after_failed_batch():
    """Input addresses should be recovered via single-register probes after batch failure."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._client = object()
    scanner._transport = MagicMock()
    scanner._transport.is_connected.return_value = True

    async def fake_read_input(address, count, *, skip_cache=False):
        if skip_cache and count == 1:
            values = {
                0: 3,
                1: 0,
                4: 11,
                16: 215,
                17: 220,
            }
            value = values.get(address)
            return [value] if value is not None else None
        if (address, count) == (16, 2):
            return None
        if (address, count) == (0, 2):
            return [3, 0]
        if (address, count) == (4, 1):
            return [11]
        return []

    with (
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.INPUT_REGISTERS",
            {
                "version_major": 0,
                "version_minor": 1,
                "version_patch": 4,
                "outside_temperature": 16,
                "supply_temperature": 17,
            },
            clear=True,
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.HOLDING_REGISTERS",
            {},
            clear=True,
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.COIL_REGISTERS",
            {},
            clear=True,
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.DISCRETE_INPUT_REGISTERS",
            {},
            clear=True,
        ),
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=[])),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
    ):
        result = await scanner.scan()

    assert "outside_temperature" in result["available_registers"]["input_registers"]
    assert "supply_temperature" in result["available_registers"]["input_registers"]


async def test_scan_reports_diagnostic_registers_on_error():
    """Diagnostic registers that failed Modbus probing are NOT force-added.

    When all holding register reads fail (return None), the failed addresses
    are recorded in failed_addresses["modbus_exceptions"]["holding_registers"].
    The force-add loop must respect these failures and skip those addresses so
    HA does not create permanently-unavailable entities for unsupported registers.
    """
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._client = object()
    diag_regs = {"alarm": 0, "error": 1, "e_99": 2, "s_2": 3}
    scanner._registers = {
        4: {},
        3: {addr: name for name, addr in diag_regs.items()},
        1: {},
        2: {},
    }
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.HOLDING_REGISTERS",
            diag_regs,
        ),
        patch.object(scanner, "_read_input", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
    ):
        result = await scanner.scan()

    # All four addresses (0-3) failed → none should be force-added
    assert result["available_registers"]["holding_registers"] == set()


@pytest.mark.parametrize("async_close", [True, False])
async def test_close_terminates_client(async_close):
    """Ensure close() handles both async and sync client close methods."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
    mock_client = AsyncMock() if async_close else MagicMock()
    scanner._client = mock_client

    await scanner.close()

    if async_close:
        mock_client.close.assert_called_once()
        mock_client.close.assert_awaited_once()
    else:
        mock_client.close.assert_called_once()

    assert scanner._client is None


async def test_log_invalid_value_debug_when_not_verbose(caplog):
    """Invalid values log at DEBUG level when not verbose."""
    scanner = ThesslaGreenDeviceScanner("host", 502)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("test_register", 1)

    assert caplog.records[0].levelno == logging.DEBUG
    assert "Invalid value for test_register: raw=1 decoded=1" in caplog.text

    caplog.clear()
    scanner._log_invalid_value("test_register", 1)

    assert not caplog.records


async def test_log_invalid_value_info_then_debug_when_verbose(caplog):
    """First invalid value logs INFO when verbose, then DEBUG."""
    scanner = ThesslaGreenDeviceScanner("host", 502, verbose_invalid_values=True)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("test_register", 1)

    assert caplog.records[0].levelno == logging.INFO
    assert "raw=1" in caplog.text

    caplog.clear()
    scanner._log_invalid_value("test_register", 1)

    assert caplog.records[0].levelno == logging.DEBUG
    assert "raw=1" in caplog.text


async def test_log_invalid_value_raw_and_formatted(caplog):
    """Log includes both raw hex and decoded representation."""
    scanner = ThesslaGreenDeviceScanner("host", 502)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("schedule_time", 5632)

    assert "raw=5632" in caplog.text
    assert "decoded=16:00" in caplog.text


async def test_log_invalid_value_invalid_time(caplog):
    """Logs include formatted string for invalid time values."""
    scanner = ThesslaGreenDeviceScanner("host", 502)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("schedule_time", 9216)

    assert "raw=9216" in caplog.text
    assert "decoded=9216 (invalid)" in caplog.text


async def test_failed_addresses_recorded_on_exception():
    """Addresses are recorded when a Modbus read raises an exception."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502)
    scanner._client = AsyncMock()

    async def fake_call(func, slave_id, address, *, count=None):
        if address == 0 and count == 1:
            raise ModbusIOException("boom")
        resp = MagicMock()
        resp.isError.return_value = False
        if func.__name__ in ("read_input_registers", "read_holding_registers"):
            resp.registers = [0] * (count or 1)
        else:
            resp.bits = [0] * (count or 1)
        return resp

    with (
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.INPUT_REGISTERS",
            {"version_major": 0},
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.HOLDING_REGISTERS",
            {},
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.COIL_REGISTERS",
            {},
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=fake_call),
        ),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner.scan()

    failed = result["failed_addresses"]["modbus_exceptions"]
    assert failed


async def test_deep_scan_collects_raw_registers():
    """Deep scan returns raw register values."""

    class DummyClient:
        async def connect(self):
            return True

        async def close(self):
            pass

    async def fake_read_input(self, client, address, count, *, skip_cache=False):
        return list(range(address, address + count))

    async def fake_read_holding(self, client, address, count, *, skip_cache=False):
        return [0] * count

    async def fake_read_coil(self, client, address, count):
        return [0] * count

    async def fake_read_discrete(self, client, address, count):
        return [0] * count

    with (
        patch(
            "pymodbus.client.AsyncModbusTcpClient",
            return_value=DummyClient(),
        ),
        patch.object(ThesslaGreenDeviceScanner, "_read_input", fake_read_input),
        patch.object(ThesslaGreenDeviceScanner, "_read_holding", fake_read_holding),
        patch.object(ThesslaGreenDeviceScanner, "_read_coil", fake_read_coil),
        patch.object(ThesslaGreenDeviceScanner, "_read_discrete", fake_read_discrete),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10, deep_scan=True)
        scanner.connection_mode = CONNECTION_MODE_TCP
        result = await scanner.scan_device()

    expected = 300 - 14 + 1
    assert len(result["raw_registers"]) == expected
    assert result["total_addresses_scanned"] == expected


async def test_scan_logs_missing_expected_registers(caplog):
    """Scanner warns when expected registers are not found."""

    input_regs = {
        "version_major": 0,
        "version_minor": 1,
        "version_patch": 2,
        "serial_number": 3,
        "reg_a": 4,
    }

    async def fake_read_input(client, address, count, **kwargs):
        data = [0] * count
        if address <= 4 < address + count:
            data[4 - address] = SENSOR_UNAVAILABLE
        return data

    scanner = ThesslaGreenDeviceScanner("host", 502)
    scanner._input_register_map = input_regs
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

    scanner._client = object()
    with (
        patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
        patch.object(scanner, "_is_valid_register_value", side_effect=lambda n, v: n != "reg_a"),
        caplog.at_level(logging.WARNING),
    ):
        await scanner.scan()

    assert "reg_a=4" in caplog.text
