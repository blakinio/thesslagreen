"""Test device scanner for ThesslaGreen Modbus integration."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.const import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    SENSOR_UNAVAILABLE,
)
from custom_components.thessla_green_modbus.device_scanner import (
    ThesslaGreenDeviceScanner,
    _decode_bcd_time,
    _decode_register_time,
    _decode_setting_value,
    _format_register_value,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS, INPUT_REGISTERS

pytestmark = pytest.mark.asyncio


async def test_device_scanner_initialization():
    """Test device scanner initialization."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)

    assert scanner.host == "192.168.3.17"
    assert scanner.port == 8899
    assert scanner.slave_id == 10
    assert scanner.retry == 3
    assert scanner.backoff == 0


async def test_read_holding_skips_after_failure():
    """Holding registers are cached after a failed read."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    # Initial failing scan
    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ) as call_mock1,
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_holding(mock_client, 0x00A8, 1)
        assert result is None
        assert call_mock1.await_count == scanner.retry

    # Subsequent call should be skipped
    with patch(
        "custom_components.thessla_green_modbus.device_scanner._call_modbus",
        AsyncMock(),
    ) as call_mock2:
        result = await scanner._read_holding(mock_client, 0x00A8, 1)
        assert result is None
        call_mock2.assert_not_called()

    assert 0x00A8 in scanner._failed_holding


async def test_read_holding_exception_response(caplog):
    """Exception responses should include the exception code in logs."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    mock_client = AsyncMock()

    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.exception_code = 6

    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(return_value=error_response),
        ) as call_mock,
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.DEBUG),
    ):
        result = await scanner._read_holding(mock_client, 0x0001, 1)

    assert result is None
    assert call_mock.await_count == scanner.retry
    assert f"Exception code {error_response.exception_code}" in caplog.text


@pytest.mark.parametrize(
    "method, address",
    [("_read_input", 0x0001), ("_read_holding", 0x0001)],
)
async def test_read_backoff_delay(method, address):
    """Ensure exponential backoff delays between retries."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=3, backoff=0.1)
    mock_client = AsyncMock()
    sleep_mock = AsyncMock()
    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ) as call_mock,
        patch("asyncio.sleep", sleep_mock),
    ):
        result = await getattr(scanner, method)(mock_client, address, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry

    assert [call.args[0] for call in sleep_mock.await_args_list] == [0.1, 0.2]


@pytest.mark.parametrize(
    "method, address",
    [("_read_input", 0x0001), ("_read_holding", 0x0001)],
)
async def test_read_default_delay(method, address):
    """Use default delay when backoff is not specified."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=3)
    mock_client = AsyncMock()
    sleep_mock = AsyncMock()
    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ) as call_mock,
        patch("asyncio.sleep", sleep_mock),
    ):
        result = await getattr(scanner, method)(mock_client, address, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry

    assert [call.args[0] for call in sleep_mock.await_args_list] == [1, 2]


async def test_read_input_logs_warning_on_failure(caplog):
    """Warn when input registers cannot be read after retries."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    caplog.set_level(logging.WARNING)
    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ) as call_mock,
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_input(mock_client, 0x0001, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry

    assert "Device does not expose register 0x0001" in caplog.text


async def test_read_input_skips_cached_failures():
    """Input registers are cached after repeated failures."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ) as call_mock,
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_input(mock_client, 0x0001, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry

    assert {0x0001} <= scanner._failed_input

    # Subsequent call should be skipped
    with patch(
        "custom_components.thessla_green_modbus.device_scanner._call_modbus",
        AsyncMock(),
    ) as call_mock2:
        result = await scanner._read_input(mock_client, 0x0001, 1)
        assert result is None
        call_mock2.assert_not_called()


async def test_read_input_logs_once_per_skipped_range(caplog):
    """Only one log message is emitted per skipped register range."""
    scanner = await ThesslaGreenDeviceScanner.create(
        "192.168.3.17", 8899, 10, retry=2
    )
    mock_client = AsyncMock()
    scanner._failed_input.update({0x0001, 0x0002, 0x0003})

    caplog.set_level(logging.DEBUG)
    for addr in range(0x0001, 0x0004):
        result = await scanner._read_input(mock_client, addr, 1)
        assert result is None

    messages = [
        record.message
        for record in caplog.records
        if "Skipping cached failed input registers" in record.message
    ]
    assert messages == [
        "Skipping cached failed input registers 0x0001-0x0003"
    ]


async def test_scan_device_success_dynamic():
    """Test successful device scan with dynamic register scanning."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count):
        if address == 0:
            data = [4, 85, 0, 0, 0]
            return data[:count]
        if address == 0x0018:
            return [0x001A, 0x002B, 0x003C, 0x004D, 0x005E, 0x006F][:count]
        return [1] * count

    async def fake_read_holding(client, address, count):
        return [10] * count

    async def fake_read_coil(client, address, count):
        return [False] * count

    async def fake_read_discrete(client, address, count):
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
            patch.object(scanner, "_is_valid_register_value", return_value=True),
        ):
            result = await scanner.scan_device()
    assert "outside_temperature" in result["available_registers"]["input_registers"]
    assert "access_level" in result["available_registers"]["holding_registers"]
    assert "power_supply_fans" in result["available_registers"]["coil_registers"]
    assert "expansion" in result["available_registers"]["discrete_inputs"]
    assert set(result["available_registers"]["input_registers"]) == set(INPUT_REGISTERS.keys())
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
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusException("boom")),
        ) as call_mock,
        caplog.at_level(logging.DEBUG),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_coil(mock_client, 0x0000, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry


async def test_read_discrete_retries_on_failure(caplog):
    """Discrete input reads should retry on failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusException("boom")),
        ) as call_mock,
        caplog.at_level(logging.DEBUG),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_discrete(mock_client, 0x0000, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry


async def test_scan_device_success_static(mock_modbus_response):
    """Test successful device scan with predefined registers."""
    regs = {
        "04": {16: "outside_temperature"},
        "03": {0: "mode"},
        "01": {0: "power_supply_fans"},
        "02": {0: "expansion"},
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
                result = await scanner.scan_device()

                assert "available_registers" in result
                assert "device_info" in result
                assert "capabilities" in result
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
            await scanner.scan_device()
        await scanner.close()


async def test_scan_device_firmware_unavailable(caplog):
    """Missing firmware registers should log info and report unknown firmware."""
    empty_regs = {"04": {}, "03": {}, "01": {}, "02": {}}
    with patch.object(
        ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count):
        if address == 0x0000:
            return None
        return [1] * count

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

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            caplog.set_level(logging.INFO)
            result = await scanner.scan_device()

    assert result["device_info"]["firmware"] == "Unknown"
    assert "Firmware registers unavailable" in caplog.text


async def test_scan_blocks_propagated():
    """Ensure scan_device returns discovered register blocks."""
    # Avoid scanning extra registers from CSV for test speed
    empty_regs = {"04": {}, "03": {}, "01": {}, "02": {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(empty_regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

        async def fake_read_input(client, address, count):
            return [1] * count

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

            with (
                patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
                patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
                patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
                patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
            ):
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


async def test_scan_device_batch_fallback():
    """Batch read failures should fall back to single-register reads."""
    empty_regs = {"04": {}, "03": {}, "01": {}, "02": {}}
    with (
        patch.object(
            ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"ir1": 0x10, "ir2": 0x11},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS",
            {"hr1": 0x20, "hr2": 0x21},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS",
            {"cr1": 0x00, "cr2": 0x01},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {"dr1": 0x00, "dr2": 0x01},
        ),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

        async def fake_read_input(client, address, count):
            if address == 0 and count == 5:
                return [4, 85, 0, 0, 0]
            if count > 1:
                return None
            return [0]

        async def fake_read_holding(client, address, count):
            if count > 1:
                return None
            return [0]

        async def fake_read_coil(client, address, count):
            if count > 1:
                return None
            return [False]

        async def fake_read_discrete(client, address, count):
            if count > 1:
                return None
            return [False]

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client_class.return_value = mock_client

            with (
                patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)) as ri,
                patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
                patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
                patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
            ):
                result = await scanner.scan_device()

    assert set(result["available_registers"]["input_registers"]) == {"ir1", "ir2"}
    assert set(result["available_registers"]["holding_registers"]) == {"hr1", "hr2"}
    assert set(result["available_registers"]["coil_registers"]) == {"cr1", "cr2"}
    assert set(result["available_registers"]["discrete_inputs"]) == {"dr1", "dr2"}

    # Ensure batch read was attempted and individual fallback reads occurred
    batch_calls = [call for call in ri.await_args_list if call.args[1] == 0x10]
    assert any(call.args[2] == 2 for call in batch_calls)

    single_calls = [call.args[1] for call in ri.await_args_list if call.args[2] == 1]
    assert single_calls.count(0x10) == 1
    assert single_calls.count(0x11) == 1


async def test_missing_register_logged_once(caplog):
    """Each missing register should trigger only one read and log entry."""
    empty_regs = {"04": {}, "03": {}, "01": {}, "02": {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(empty_regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    call_log: list[tuple[int, int]] = []

    async def fake_read_input(client, address, count):
        call_log.append((address, count))
        if address == 0x0000 and count == 5:
            return [4, 85, 0, 0, 0]
        if address == 0x0018 and count == 6:
            return [0] * 6
        if address == 1 and count == 2:
            return None
        if address == 1 and count == 1:
            return [1]
        if address == 2 and count == 1:
            return None
        return [0] * count

    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"reg_ok": 1, "reg_missing": 2},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS",
            {},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS",
            {},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.KNOWN_MISSING_REGISTERS",
            {},
        ),
        patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class,
    ):
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(return_value=[0])),
            patch.object(scanner, "_read_coil", AsyncMock(return_value=[False])),
            patch.object(scanner, "_read_discrete", AsyncMock(return_value=[False])),
            patch.object(scanner, "_is_valid_register_value", return_value=True),
        ):
            caplog.set_level(logging.DEBUG)
            result = await scanner.scan_device()

    # Block read + single read for each register
    assert call_log.count((1, 2)) == 1
    assert call_log.count((1, 1)) == 1
    assert call_log.count((2, 1)) == 1

    # Missing register logged only once
    assert caplog.text.count("Failed to read input_registers register 0x0002") == 1

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

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            result = await scanner.scan_device()

    assert "outside_temperature" not in result["available_registers"]["input_registers"]


async def test_is_valid_register_value():
    """Test register value validation."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    # Valid values
    assert scanner._is_valid_register_value("test_register", 100) is True
    assert scanner._is_valid_register_value("test_register", 0) is True

    # SENSOR_UNAVAILABLE should be treated as unavailable for temperature and airflow sensors
    assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is False
    assert scanner._is_valid_register_value("supply_air_flow", SENSOR_UNAVAILABLE) is False

    # Invalid air flow value
    assert scanner._is_valid_register_value("supply_air_flow", 65535) is False

    # Mode values respect allowed set
    assert scanner._is_valid_register_value("mode", 1) is True
    assert scanner._is_valid_register_value("mode", 3) is False

    # Range from CSV
    assert scanner._is_valid_register_value("supply_percentage", 100) is True
    assert scanner._is_valid_register_value("supply_percentage", 200) is False

    # Dynamic percentage limits should accept device-provided values
    assert scanner._is_valid_register_value("min_percentage", 20) is True
    assert scanner._is_valid_register_value("max_percentage", 120) is True
    assert scanner._is_valid_register_value("min_percentage", -1) is False
    assert scanner._is_valid_register_value("max_percentage", 200) is False
    # HH:MM time registers
    scanner._register_ranges["schedule_start_time"] = (0, 2359)
    assert scanner._is_valid_register_value("schedule_start_time", 0x081E) is True
    assert scanner._is_valid_register_value("schedule_start_time", 0x0800) is True
    assert scanner._is_valid_register_value("schedule_start_time", 0x2460) is False
    assert scanner._is_valid_register_value("schedule_start_time", 0x0960) is False


async def test_decode_register_time():
    """Verify time decoding for HH:MM byte-encoded values."""
    assert _decode_register_time(0x081E) == 830
    assert _decode_register_time(0x1234) == 1852
    assert _decode_register_time(0x2460) is None
    assert _decode_register_time(0x0960) is None


async def test_decode_bcd_time():
    """Verify time decoding for both BCD and decimal values."""
    assert _decode_bcd_time(0x1234) == 1234
    assert _decode_bcd_time(0x0800) == 800
    assert _decode_bcd_time(0x2460) is None
    assert _decode_bcd_time(2400) is None


async def test_decode_setting_value():
    """Verify decoding of combined airflow and temperature settings."""
    assert _decode_setting_value(0x3C28) == (60, 20.0)
    assert _decode_setting_value(-1) is None
    assert _decode_setting_value(0xFF28) is None


async def test_format_register_value_schedule():
    """Formatted schedule registers should render as HH:MM."""
    assert _format_register_value("schedule_summer_mon_1", 0x0615) == "06:15"


async def test_format_register_value_setting():
    """Formatted setting registers should show percent and temperature."""
    assert _format_register_value("setting_winter_mon_1", 0x3C28) == "60% @ 20°C"


async def test_scan_excludes_unavailable_temperature():
    """Temperature register with SENSOR_UNAVAILABLE should be excluded."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count):
        data = [1] * count
        if address == 0:
            data[0:3] = [4, 85, 0]
        temp_addr = INPUT_REGISTERS["outside_temperature"]
        if address <= temp_addr < address + count:
            data[temp_addr - address] = SENSOR_UNAVAILABLE
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

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            result = await scanner.scan_device()

    assert "outside_temperature" not in result["available_registers"]["input_registers"]


async def test_temperature_unavailable_no_warning(caplog):
    """SENSOR_UNAVAILABLE should not log a warning for temperature sensors."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    caplog.set_level(logging.WARNING)
    assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is False
    assert "outside_temperature" not in caplog.text


async def test_capabilities_detect_schedule_keywords():
    """Ensure capability detection considers scheduling related registers."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner.available_registers["holding_registers"].add("airing_start_time")
    caps = scanner._analyze_capabilities()
    assert caps.weekly_schedule is True


async def test_load_registers_duplicate_warning(tmp_path, caplog):
    """Warn when duplicate register addresses are encountered."""
    csv_content = "Function_Code,Register_Name,Address_DEC\n" "04,reg_a,1\n" "04,reg_b,1\n"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch("custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
    ):
        with caplog.at_level(logging.WARNING):
            await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert any("Duplicate register address" in record.message for record in caplog.records)


async def test_load_registers_duplicate_names(tmp_path):
    """Ensure duplicate register names are suffixed for uniqueness."""
    csv_content = "Function_Code,Register_Name,Address_DEC\n" "04,reg_a,1\n" "04,reg_a,2\n"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch("custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert scanner._registers["04"] == {1: "reg_a_1", 2: "reg_a_2"}


async def test_load_registers_missing_range_warning(tmp_path, caplog):
    """Warn when Min/Max range is incomplete."""
    csv_content = "Function_Code,Address_DEC,Register_Name,Min,Max\n" "04,1,reg_a,0,\n"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"reg_a": 1},
        ),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        caplog.at_level(logging.WARNING),
    ):
        await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert any("Incomplete range" in record.message for record in caplog.records)


async def test_load_registers_sanitize_range_values(tmp_path, caplog):
    """Sanitize range values and ignore non-numeric entries."""
    csv_content = (
        "Function_Code,Address_DEC,Register_Name,Min,Max\n" "04,1,reg_a,0 # comment,10abc\n"
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"reg_a": 1},
        ),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        caplog.at_level(logging.WARNING),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert scanner._register_ranges["reg_a"] == (0, None)
    assert any("non-numeric Max" in record.message for record in caplog.records)


async def test_load_registers_hex_range(tmp_path, caplog):
    """Parse hexadecimal Min/Max values without warnings."""
    csv_content = "Function_Code,Address_DEC,Register_Name,Min,Max\n" "04,1,reg_a,0x0,0x423f\n"
@pytest.mark.parametrize("min_raw,max_raw", [("1", "10"), ("0x1", "0xA")])
async def test_load_registers_parses_range_formats(tmp_path, min_raw, max_raw):
    """Support decimal and hexadecimal ranges."""
    csv_content = (
        "Function_Code,Address_DEC,Register_Name,Min,Max\n" f"04,1,reg_a,{min_raw},{max_raw}\n"
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"reg_a": 1},
        ),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        caplog.at_level(logging.WARNING),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert scanner._register_ranges["reg_a"] == (0x0, 0x423F)
    assert not caplog.records
    ):
        scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert scanner._register_ranges["reg_a"] == (1, 10)


async def test_load_registers_invalid_range_logs(tmp_path, caplog):
    """Warn when Min/Max cannot be parsed even after sanitization."""
    csv_content = "Function_Code,Address_DEC,Register_Name,Min,Max\n" "04,1,reg_a,abc,#comment\n"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"reg_a": 1},
        ),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        caplog.at_level(logging.WARNING),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert "reg_a" not in scanner._register_ranges
    assert any("non-numeric Min" in record.message for record in caplog.records)
    assert any("non-numeric Max" in record.message for record in caplog.records)


async def test_load_registers_missing_required_register(tmp_path):
    """Fail fast when a required register is absent from CSV."""
    csv_content = "Function_Code,Address_DEC,Register_Name\n"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"reg_a": 1},
        ),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
    ):
        with pytest.raises(ValueError, match="reg_a"):
            await ThesslaGreenDeviceScanner.create("host", 502, 10)


async def test_analyze_capabilities():
    """Test capability analysis."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

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


async def test_analyze_capabilities_flag_presence():
    """Capabilities should reflect register presence and absence."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    # Positive case: registers exist
    scanner.available_registers = {
        "input_registers": {"constant_flow_active", "outside_temperature"},
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    capabilities = scanner._analyze_capabilities()

    assert capabilities.constant_flow is True
    assert capabilities.sensor_outside_temperature is True

    # Negative case: registers absent
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    capabilities = scanner._analyze_capabilities()

    assert capabilities.constant_flow is False
    assert capabilities.sensor_outside_temperature is False


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
    assert (
        "Invalid value for test_register: raw=0x0001 decoded=1" in caplog.text
    )

    caplog.clear()
    scanner._log_invalid_value("test_register", 1)

    assert not caplog.records


async def test_log_invalid_value_info_then_debug_when_verbose(caplog):
    """First invalid value logs INFO when verbose, then DEBUG."""
    scanner = ThesslaGreenDeviceScanner("host", 502, verbose_invalid_values=True)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("test_register", 1)

    assert caplog.records[0].levelno == logging.INFO
    assert "raw=0x0001" in caplog.text

    caplog.clear()
    scanner._log_invalid_value("test_register", 1)

    assert caplog.records[0].levelno == logging.DEBUG
    assert "raw=0x0001" in caplog.text


async def test_log_invalid_value_raw_and_formatted(caplog):
    """Log includes both raw hex and decoded representation."""
    scanner = ThesslaGreenDeviceScanner("host", 502)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("schedule_time", 0x1600)

    assert "raw=0x1600" in caplog.text
    assert "decoded=16:00" in caplog.text
