# mypy: ignore-errors
"""Exercise remaining scanner orchestration transport and scan branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.scanner import orchestration
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException


@pytest.mark.asyncio
async def test_accumulate_raw_registers_disabled_none_data_and_failure_isolation() -> None:
    scanner = SimpleNamespace(deep_scan=False)
    assert await orchestration._accumulate_raw_registers(scanner) == {}

    failed = {"modbus_exceptions": {"input_registers": {1}}}
    scanner = SimpleNamespace(
        deep_scan=True,
        failed_addresses=failed,
        _client=None,
        _group_registers_for_batch_read=Mock(return_value=[(0, 2), (2, 1)]),
        _read_input=AsyncMock(side_effect=[None, [9]]),
    )
    assert await orchestration._accumulate_raw_registers(scanner) == {2: 9}
    assert scanner.failed_addresses["modbus_exceptions"]["input_registers"] == {1}

    scanner.failed_addresses = {"modbus_exceptions": {"input_registers": {1}}}

    async def add_failure(_client, start, count):
        scanner.failed_addresses["modbus_exceptions"]["input_registers"].add(5)
        return [7] * count

    scanner._client = object()
    scanner._group_registers_for_batch_read = Mock(return_value=[(0, 1)])
    scanner._read_input = AsyncMock(side_effect=add_failure)
    result = await orchestration._accumulate_raw_registers(scanner)
    assert result == {0: 7}
    assert scanner.failed_addresses["deep_scan_raw_failures"]["input_registers"] == {5}
    assert scanner.failed_addresses["modbus_exceptions"]["input_registers"] == {1}


@pytest.mark.asyncio
async def test_auto_detect_tcp_transport_timeout_cancel_protocol_and_success_paths() -> None:
    scanner = SimpleNamespace(
        slave_id=10,
        host="host",
        port=502,
        _transport=None,
        _resolved_connection_mode=None,
    )

    failed_transport = SimpleNamespace(
        ensure_connected=AsyncMock(side_effect=ConnectionException("offline")),
        read_input_registers=AsyncMock(),
        close=AsyncMock(),
    )
    protocol_ok_transport = SimpleNamespace(
        ensure_connected=AsyncMock(),
        read_input_registers=AsyncMock(side_effect=ModbusException("protocol response")),
        close=AsyncMock(),
    )
    scanner._build_auto_tcp_attempts = Mock(
        return_value=[("tcp", failed_transport, 1), ("tcp_rtu", protocol_ok_transport, 1)]
    )
    await orchestration._auto_detect_tcp_transport(scanner)
    failed_transport.close.assert_awaited_once()
    assert scanner._transport is protocol_ok_transport
    assert scanner._resolved_connection_mode == "tcp_rtu"

    cancelled_transport = SimpleNamespace(
        ensure_connected=AsyncMock(),
        read_input_registers=AsyncMock(
            side_effect=ModbusIOException("request cancelled outside pymodbus")
        ),
        close=AsyncMock(),
    )
    scanner._build_auto_tcp_attempts = Mock(return_value=[("tcp", cancelled_transport, 1)])
    with pytest.raises(ConnectionException, match="Auto-detect"):
        await orchestration._auto_detect_tcp_transport(scanner)
    cancelled_transport.close.assert_awaited_once()

    timeout_transport = SimpleNamespace(
        ensure_connected=AsyncMock(),
        read_input_registers=AsyncMock(side_effect=TimeoutError("timeout")),
        close=AsyncMock(),
    )
    scanner._build_auto_tcp_attempts = Mock(return_value=[("tcp", timeout_transport, 1)])
    with pytest.raises(ConnectionException, match="Auto-detect"):
        await orchestration._auto_detect_tcp_transport(scanner)


@pytest.mark.asyncio
async def test_prepare_scan_transport_rtu_missing_rtu_auto_and_explicit_tcp() -> None:
    scanner = SimpleNamespace(
        connection_type=orchestration.CONNECTION_TYPE_RTU,
        serial_port="",
        _transport=None,
    )
    with pytest.raises(ConnectionException, match="Serial port"):
        await orchestration._prepare_scan_transport(scanner)

    scanner.serial_port = "/dev/ttyUSB0"
    with patch.object(orchestration, "_create_rtu_transport", return_value="rtu"):
        await orchestration._prepare_scan_transport(scanner)
    assert scanner._transport == "rtu"

    scanner.connection_type = "tcp"
    scanner._resolved_connection_mode = None
    scanner.connection_mode = orchestration.CONNECTION_MODE_AUTO
    with patch.object(orchestration, "_auto_detect_tcp_transport", new=AsyncMock()) as auto:
        await orchestration._prepare_scan_transport(scanner)
    auto.assert_awaited_once_with(scanner)

    scanner.connection_mode = "tcp"
    scanner._build_tcp_transport = Mock(return_value="tcp-transport")
    await orchestration._prepare_scan_transport(scanner)
    assert scanner._transport == "tcp-transport"


def test_create_rtu_transport_uses_fallback_serial_settings() -> None:
    transport_cls = Mock(return_value="rtu")
    scanner = SimpleNamespace(
        parity="unknown",
        stop_bits=999,
        serial_port="tty",
        baud_rate=9600,
        retry=2,
        backoff=0.1,
        timeout=3,
        _rtu_transport_cls=transport_cls,
    )
    assert orchestration._create_rtu_transport(scanner) == "rtu"
    transport_cls.assert_called_once()


@pytest.mark.asyncio
async def test_word_and_bit_phases_none_alias_unknown_and_delay_paths() -> None:
    scanner = SimpleNamespace(
        effective_batch=10,
        delay_between_requests_ms=1,
        failed_addresses={
            "batch_failures": {
                "input_registers": set(),
                "coil_registers": set(),
            }
        },
        _registers={1: {0: "coil_zero"}},
        _alias_names=Mock(side_effect=[{"alias"}, set()]),
        available_registers={"coil_registers": set()},
    )
    unknown = {"input_registers": {}, "coil_registers": {}}
    scanned = {"input_registers": 0, "coil_registers": 0}
    with (
        patch.object(orchestration, "_group_reads", return_value=[(0, 1)]),
        patch.object(orchestration.asyncio, "sleep", new=AsyncMock()) as sleep,
    ):
        await orchestration._run_word_phase(
            scanner, 0, "input_registers", 4, AsyncMock(return_value=None), unknown, scanned
        )
    assert scanner.failed_addresses["batch_failures"]["input_registers"] == {0}
    sleep.assert_awaited()

    with (
        patch.object(orchestration, "_group_reads", return_value=[(0, 2)]),
        patch.object(orchestration.asyncio, "sleep", new=AsyncMock()),
    ):
        await orchestration._run_bit_phase(
            scanner,
            1,
            "coil_registers",
            1,
            AsyncMock(return_value=[True, False]),
            unknown,
            scanned,
        )
    assert "alias" in scanner.available_registers["coil_registers"]
    assert unknown["coil_registers"][1] is False


def test_scan_transport_ready_all_states() -> None:
    scanner = SimpleNamespace(_transport=None, _client=None)
    with pytest.raises(ConnectionException):
        orchestration._check_scan_transport_ready(scanner)
    scanner._client = object()
    orchestration._check_scan_transport_ready(scanner)
    scanner._client = None
    scanner._transport = SimpleNamespace(is_connected=Mock(return_value=False))
    with pytest.raises(ConnectionException):
        orchestration._check_scan_transport_ready(scanner)
    scanner._transport.is_connected.return_value = True
    orchestration._check_scan_transport_ready(scanner)


@pytest.mark.asyncio
async def test_collect_scan_device_info_empty_block_still_calls_firmware_and_identity() -> None:
    scanner = SimpleNamespace(
        _read_input_block=AsyncMock(return_value=None),
        _scan_firmware_info=AsyncMock(),
        _scan_device_identity=AsyncMock(),
    )
    device = orchestration.ScannerDeviceInfo()
    await orchestration._collect_scan_device_info(scanner, device)
    scanner._scan_firmware_info.assert_awaited_once_with([], device)
    scanner._scan_device_identity.assert_awaited_once_with([], device)


@pytest.mark.asyncio
async def test_scan_device_custom_scan_connect_failure_type_validation_and_close() -> None:
    scanner = SimpleNamespace(close=AsyncMock())
    with (
        patch.object(orchestration.scanner_custom_scan, "uses_custom_scan_impl", return_value=True),
        patch.object(
            orchestration.scanner_custom_scan,
            "run_custom_scan",
            new=AsyncMock(return_value={"ok": 1}),
        ),
    ):
        assert await orchestration.scan_device(scanner) == {"ok": 1}
    scanner.close.assert_awaited_once()

    scanner = SimpleNamespace(
        host="host",
        port=502,
        timeout=1,
        _transport=SimpleNamespace(
            ensure_connected=AsyncMock(side_effect=TimeoutError()), client=None
        ),
        _client=None,
        close=AsyncMock(),
        scan=AsyncMock(),
    )
    with (
        patch.object(
            orchestration.scanner_custom_scan, "uses_custom_scan_impl", return_value=False
        ),
        patch.object(orchestration, "_prepare_scan_transport", new=AsyncMock()),
    ):
        with pytest.raises(ConnectionException, match="Failed to connect"):
            await orchestration.scan_device(scanner)
    scanner.close.assert_awaited_once()

    scanner._transport = SimpleNamespace(ensure_connected=AsyncMock(), client=object())
    scanner.close.reset_mock()
    scanner.scan = AsyncMock(return_value="not-a-dict")
    with (
        patch.object(
            orchestration.scanner_custom_scan, "uses_custom_scan_impl", return_value=False
        ),
        patch.object(orchestration, "_prepare_scan_transport", new=AsyncMock()),
    ):
        with pytest.raises(TypeError, match="must return a dict"):
            await orchestration.scan_device(scanner)
    scanner.close.assert_awaited_once()
