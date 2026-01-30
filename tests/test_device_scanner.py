"""Test device scanner for ThesslaGreen Modbus integration."""

import logging
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP, SENSOR_UNAVAILABLE
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.scanner_core import (
    DeviceCapabilities,
    ScannerDeviceInfo,
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


async def test_scanner_core_initialization():
    """Test device scanner initialization."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)

    assert hasattr(scanner, "_read_coil")
    assert hasattr(scanner, "_read_holding")
    assert hasattr(scanner, "_read_discrete")

    assert scanner.host == "192.168.3.17"
    assert scanner.port == 8899
    assert scanner.slave_id == 10
    assert scanner.retry == 3
    assert scanner.backoff == 0


async def test_verify_connection_close_non_awaitable_on_failure():
    """Verify close() handles non-awaitable result on connection failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    fake_transport = MagicMock()
    fake_transport.ensure_connected = AsyncMock(side_effect=ConnectionException("fail"))
    fake_transport.read_input_registers = AsyncMock()
    fake_transport.read_holding_registers = AsyncMock()
    fake_transport.close = MagicMock(return_value=None)

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with pytest.raises(ConnectionException):
            await scanner.verify_connection()

    fake_transport.close.assert_called_once()


async def test_verify_connection_close_non_awaitable_on_success():
    """Verify close() handles non-awaitable result on success."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    fake_transport = MagicMock()
    fake_transport.ensure_connected = AsyncMock(return_value=True)
    fake_transport.read_input_registers = AsyncMock()
    fake_transport.read_holding_registers = AsyncMock()
    fake_transport.close = MagicMock(return_value=None)

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        await scanner.verify_connection()

    fake_transport.close.assert_called_once()


async def test_create_binds_read_helpers():
    """Scanner.create binds read helper methods to the instance."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    assert hasattr(scanner, "_read_holding")
    assert hasattr(scanner, "_read_coil")
    assert hasattr(scanner, "_read_discrete")


async def test_scanner_has_read_coil_method():
    """Ensure scanner exposes coil reading helper."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    assert hasattr(scanner, "_read_coil")


async def test_read_holding_skips_after_failure():
    """Holding registers are cached after a failed read."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    # Initial failing scan
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ) as call_mock1,
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_holding(mock_client, 168, 1)
        assert result is None
        assert call_mock1.await_count == scanner.retry

    # Subsequent call should be skipped
    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        AsyncMock(),
    ) as call_mock2:
        result = await scanner._read_holding(mock_client, 168, 1)
        assert result is None
        call_mock2.assert_not_called()

    assert 168 in scanner._failed_holding


async def test_read_holding_exception_response(caplog):
    """Exception responses should include the exception code in logs."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    mock_client = AsyncMock()

    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.exception_code = 6

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(return_value=error_response),
        ) as call_mock,
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.DEBUG),
    ):
        result = await scanner._read_holding(mock_client, 1, 1)

    assert result is None
    assert call_mock.await_count == scanner.retry
    assert f"Exception code {error_response.exception_code}" in caplog.text


async def test_read_holding_timeout_logging(caplog):
    """Timeout errors should log a warning and a final error."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=TimeoutError()),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.WARNING),
    ):
        result = await scanner._read_holding(mock_client, 1, 1)

    assert result is None
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Timeout reading holding 1" in msg for msg in warnings)
    errors = [r.message for r in caplog.records if r.levelno == logging.ERROR]
    assert any("Failed to read holding registers 1-1" in msg for msg in errors)


@pytest.mark.parametrize(
    "method, address",
    [("_read_input", 1), ("_read_holding", 1)],
)
async def test_read_backoff_delay(method, address):
    """Ensure exponential backoff delays between retries."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=3, backoff=0.1)
    mock_client = AsyncMock()
    if method == "_read_input":
        mock_client.read_input_registers = AsyncMock(side_effect=ModbusIOException("boom"))
        mock_client.read_holding_registers = AsyncMock(side_effect=ModbusIOException("boom"))
    else:
        mock_client.read_holding_registers = AsyncMock(side_effect=ModbusIOException("boom"))

    sleep_mock = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.modbus_helpers.asyncio.sleep",
        sleep_mock,
    ):
        result = await getattr(scanner, method)(mock_client, address, 1)
        assert result is None

    assert [call.args[0] for call in sleep_mock.await_args_list] == [0.1, 0.2]


@pytest.mark.parametrize(
    "method, address",
    [("_read_input", 1), ("_read_holding", 1)],
)
async def test_read_default_delay(method, address):
    """Use default delay when backoff is not specified."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=3)
    mock_client = AsyncMock()
    if method == "_read_input":
        mock_client.read_input_registers = AsyncMock(side_effect=ModbusIOException("boom"))
        mock_client.read_holding_registers = AsyncMock(side_effect=ModbusIOException("boom"))
    else:
        mock_client.read_holding_registers = AsyncMock(side_effect=ModbusIOException("boom"))

    sleep_mock = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.modbus_helpers.asyncio.sleep",
        sleep_mock,
    ):
        result = await getattr(scanner, method)(mock_client, address, 1)
        assert result is None

    assert sleep_mock.await_args_list == []


@pytest.mark.parametrize(
    "func, address",
    [
        (ThesslaGreenDeviceScanner._read_coil, 0),
        (ThesslaGreenDeviceScanner._read_discrete, 0),
    ],
)
async def test_read_binary_backoff_delay(func, address):
    """Coil and discrete reads should respect configured backoff."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=3, backoff=0.1)
    mock_client = AsyncMock()
    if func is ThesslaGreenDeviceScanner._read_coil:
        mock_client.read_coils = AsyncMock(side_effect=ModbusIOException("boom"))
    else:
        mock_client.read_discrete_inputs = AsyncMock(side_effect=ModbusIOException("boom"))

    sleep_mock = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.modbus_helpers.asyncio.sleep",
        sleep_mock,
    ):
        result = await func(scanner, mock_client, address, 1)
        assert result is None

    assert [call.args[0] for call in sleep_mock.await_args_list] == [0.1, 0.2]


@pytest.mark.parametrize(
    "func, address",
    [
        (ThesslaGreenDeviceScanner._read_coil, 0),
        (ThesslaGreenDeviceScanner._read_discrete, 0),
    ],
)
async def test_read_binary_default_delay(func, address):
    """Default backoff of zero should not delay retries."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=3)
    mock_client = AsyncMock()
    if func is ThesslaGreenDeviceScanner._read_coil:
        mock_client.read_coils = AsyncMock(side_effect=ModbusIOException("boom"))
    else:
        mock_client.read_discrete_inputs = AsyncMock(side_effect=ModbusIOException("boom"))

    sleep_mock = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.modbus_helpers.asyncio.sleep",
        sleep_mock,
    ):
        result = await func(scanner, mock_client, address, 1)
        assert result is None

    assert sleep_mock.await_args_list == []


async def test_read_input_logs_warning_on_failure(caplog):
    """Warn when input registers cannot be read after retries."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    caplog.set_level(logging.WARNING)
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ) as call_mock,
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_input(mock_client, 1, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry

    assert "Device does not expose register 1" in caplog.text


async def test_read_input_skips_cached_failures():
    """Input registers are cached after repeated failures."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ) as call_mock,
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_input(mock_client, 1, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry

    assert {1} <= scanner._failed_input

    # Subsequent call should be skipped
    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        AsyncMock(),
    ) as call_mock2:
        result = await scanner._read_input(mock_client, 1, 1)
        assert result is None
        call_mock2.assert_not_called()


async def test_read_input_skips_range_on_exception_response(caplog):
    """Block failures with exception codes skip entire register range."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.exception_code = 2

    caplog.set_level(logging.WARNING)
    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        AsyncMock(return_value=error_response),
    ) as call_mock:
        result = await scanner._read_input(mock_client, 256, 3)

    scanner._log_skipped_ranges()

    assert result is None
    assert call_mock.await_count == 1
    assert set(range(256, 259)) <= scanner._failed_input
    assert "Skipping unsupported input registers 256-258 (exception code 2)" in caplog.text

    # Further reads within the range should be skipped without new calls
    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        AsyncMock(),
    ) as call_mock2:
        result = await scanner._read_input(mock_client, 257, 1)
        assert result is None
        call_mock2.assert_not_called()


async def test_read_holding_skips_range_on_exception_response(caplog):
    """Block failures with exception codes skip entire holding register range."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.exception_code = 2

    caplog.set_level(logging.WARNING)
    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        AsyncMock(return_value=error_response),
    ) as call_mock:
        result = await scanner._read_holding(mock_client, 512, 2)

    scanner._log_skipped_ranges()

    assert result is None
    assert call_mock.await_count == 1
    assert (512, 513) in scanner._unsupported_holding_ranges
    assert "Skipping unsupported holding registers 512-513 (exception code 2)" in caplog.text

    # Further reads within the range should be skipped without new calls
    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        AsyncMock(),
    ) as call_mock2:
        result = await scanner._read_holding(mock_client, 513, 1)
        assert result is None
        call_mock2.assert_not_called()


async def test_read_holding_skip_cache_reads_unsupported_range():
    """Single reads are attempted even if range was marked unsupported."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    mock_client = AsyncMock()
    scanner._unsupported_holding_ranges[(512, 513)] = 1
    scanner._failed_holding.update({512, 513})

    response = MagicMock()
    response.isError.return_value = False
    response.registers = [123]

    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        AsyncMock(return_value=response),
    ) as call_mock:
        result = await scanner._read_holding(mock_client, 512, 1, skip_cache=True)

    assert result == [123]
    call_mock.assert_awaited_once()


async def test_single_read_clears_failed_holding_cache():
    """Successful single reads remove addresses from cached failure ranges."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    client = AsyncMock()
    scanner._mark_holding_unsupported(768, 770, 1)
    scanner._failed_holding.update({768, 769, 770})

    response = MagicMock()
    response.isError.return_value = False
    response.registers = [55]

    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        AsyncMock(return_value=response),
    ) as call_mock:
        result = await scanner._read_holding(client, 769, 1, skip_cache=True)

    assert result == [55]
    call_mock.assert_awaited_once()
    assert 769 not in scanner._failed_holding
    assert (768, 768) in scanner._unsupported_holding_ranges
    assert (770, 770) in scanner._unsupported_holding_ranges
    assert all(not (start <= 769 <= end) for start, end in scanner._unsupported_holding_ranges)


async def test_log_skipped_ranges_no_overlap(caplog):
    """Logged skipped ranges should not contain overlaps."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._mark_holding_unsupported(1024, 1028, 1)
    scanner._mark_holding_unsupported(1026, 1030, 2)

    with caplog.at_level(logging.WARNING):
        scanner._log_skipped_ranges()

    assert "1024-1025 (exception code 1)" in caplog.text
    assert "1026-1030 (exception code 2)" in caplog.text
    assert "1024-1028" not in caplog.text


async def test_read_input_logs_once_per_skipped_range(caplog):
    """Only one log message is emitted per skipped register range."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()
    scanner._failed_input.update({1, 2, 3})

    caplog.set_level(logging.DEBUG)
    for addr in range(1, 4):
        result = await scanner._read_input(mock_client, addr, 1)
        assert result is None

    messages = [
        record.message
        for record in caplog.records
        if "Skipping cached failed input registers" in record.message
    ]
    assert messages == ["Skipping cached failed input registers 1-3"]


async def test_read_holding_exponential_backoff(caplog):
    """Ensure exponential backoff and error reporting when device fails to respond."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10, retry=3, backoff=0.5)
    client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=ModbusException("boom")),
        ),
        patch(
            "custom_components.thessla_green_modbus.modbus_helpers.asyncio.sleep",
            AsyncMock(),
        ) as sleep_mock,
        caplog.at_level(logging.WARNING),
    ):
        result = await scanner._read_holding(client, 1, 1)

    assert result is None
    assert sleep_mock.await_args_list == [call(0.5), call(1.0)]
    assert any(
        "Failed to read holding registers 1-1" in record.message for record in caplog.records
    )


async def test_read_holding_returns_none_on_modbus_error():
    """A Modbus error response should return None without raising."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    client = AsyncMock()
    response = MagicMock()
    response.isError.return_value = True
    call_modbus = AsyncMock(return_value=response)

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            call_modbus,
        ),
        patch(
            "custom_components.thessla_green_modbus.modbus_helpers.asyncio.sleep",
            AsyncMock(),
        ),
    ):
        result = await scanner._read_holding(client, 1, 1)

    assert result is None
    assert call_modbus.await_count == scanner.retry


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
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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


async def test_scan_device_firmware_unavailable(caplog):
    """Missing firmware registers should log info and report unknown firmware."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count, *, skip_cache=False):
        if address == 0 and count == 30:
            return None
        if count == 1 and address in (
            INPUT_REGISTERS["version_major"],
            INPUT_REGISTERS["version_minor"],
            INPUT_REGISTERS["version_patch"],
        ):
            return None
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
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            caplog.set_level(logging.WARNING)
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    assert result["device_info"]["firmware"] == "Unknown"
    assert "Failed to read firmware version registers" in caplog.text


async def test_scan_device_firmware_bulk_fallback():
    """Bulk firmware read failure should fall back to individual reads."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count, *, skip_cache=False):
        if address == 0 and count == 30:
            return None
        if count == 1 and address == INPUT_REGISTERS["version_major"]:
            return [4]
        if count == 1 and address == INPUT_REGISTERS["version_minor"]:
            return [85]
        if count == 1 and address == INPUT_REGISTERS["version_patch"]:
            return [0]
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
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    assert result["device_info"]["firmware"] == "4.85.0"


async def test_scan_device_firmware_partial_bulk_fallback():
    """Partial firmware bulk read should fall back to individual reads."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count, *, skip_cache=False):
        if address == 0 and count == 30:
            return [4, 85]
        if count == 1 and address == INPUT_REGISTERS["version_patch"]:
            return [0]
        if count == 1 and address == INPUT_REGISTERS["version_major"]:
            return [4]
        if count == 1 and address == INPUT_REGISTERS["version_minor"]:
            return [85]
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
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    assert result["device_info"]["firmware"] == "4.85.0"


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

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core.INPUT_REGISTERS",
            {"ir1": 16, "ir2": 17},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner_core.HOLDING_REGISTERS",
            {"hr1": 32, "hr2": 33},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner_core.COIL_REGISTERS",
            {"cr1": 0, "cr2": 1},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner_core.DISCRETE_INPUT_REGISTERS",
            {"dr1": 0, "dr2": 1},
        ),
        patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class,
    ):
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

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core.INPUT_REGISTERS",
            {"reg_ok": 1, "reg_missing": 2},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner_core.HOLDING_REGISTERS",
            {},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner_core.COIL_REGISTERS",
            {},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner_core.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner_core.KNOWN_MISSING_REGISTERS",
            {},
        ),
        patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class,
    ):
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

    # SENSOR_UNAVAILABLE should be treated as unavailable for temperature and airflow sensors
    assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is False
    assert scanner._is_valid_register_value("supply_flow_rate", SENSOR_UNAVAILABLE) is False

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

    async def fake_read_holding(client, address, count, **kwargs):
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
            scanner.connection_mode = CONNECTION_MODE_TCP
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


async def test_scan_populates_device_name():
    """Scanner should include device_name in returned device info."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._client = object()
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


async def test_scan_reports_diagnostic_registers_on_error():
    """Diagnostic holding registers are reported even when reads fail."""
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
            "custom_components.thessla_green_modbus.scanner_core.HOLDING_REGISTERS",
            diag_regs,
        ),
        patch.object(scanner, "_read_input", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
    ):
        result = await scanner.scan()

    assert {"alarm", "error", "e_99", "s_2"} <= result["available_registers"]["holding_registers"]


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
            "custom_components.thessla_green_modbus.scanner_core.INPUT_REGISTERS",
            {"version_major": 0},
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner_core.HOLDING_REGISTERS",
            {},
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner_core.COIL_REGISTERS",
            {},
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner_core.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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
    with (
        patch("custom_components.thessla_green_modbus.scanner_core.INPUT_REGISTERS", input_regs),
        patch("custom_components.thessla_green_modbus.scanner_core.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.scanner_core.COIL_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.scanner_core.DISCRETE_INPUT_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.scanner_core.KNOWN_MISSING_REGISTERS",
            {
                "input_registers": set(),
                "holding_registers": set(),
                "coil_registers": set(),
                "discrete_inputs": set(),
            },
        ),
    ):
        scanner._client = object()
        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
            patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
            patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
            patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
            patch.object(
                scanner, "_is_valid_register_value", side_effect=lambda n, v: n != "reg_a"
            ),
            caplog.at_level(logging.WARNING),
        ):
            await scanner.scan()

    assert "reg_a=4" in caplog.text
