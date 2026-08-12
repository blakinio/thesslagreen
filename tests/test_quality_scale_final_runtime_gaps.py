# mypy: ignore-errors
"""Close the final measured runtime coverage gaps without coverage suppression."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.core import io_mixin, register_groups, retry
from custom_components.thessla_green_modbus.scanner import firmware
from custom_components.thessla_green_modbus.scanner.device_info import ScannerDeviceInfo
from pymodbus.exceptions import ConnectionException, ModbusException


def _retry_owner(*, transport=None, retry_count=2):
    client = object()
    device_client = SimpleNamespace(client=client, retry=retry_count, _transport=transport)
    owner = SimpleNamespace(
        device_client=device_client,
        backoff=0.0,
        _disconnect=AsyncMock(),
        _ensure_connection=AsyncMock(),
        _log_read_retry=Mock(),
    )
    return owner, client


@pytest.mark.asyncio
async def test_retry_disconnect_executes_and_restores_legacy_client() -> None:
    owner, original_client = _retry_owner()

    async def disconnect():
        owner.device_client.client = None

    owner._disconnect = AsyncMock(side_effect=disconnect)
    assert (
        await retry._safe_disconnect_for_retry(
            owner,
            register_type="input",
            start_address=10,
            attempt=1,
            restore_client=True,
        )
        is None
    )
    owner._disconnect.assert_awaited_once()
    assert owner.device_client.client is original_client


@pytest.mark.asyncio
async def test_retry_disconnect_and_reconnect_failure_paths() -> None:
    owner, _client = _retry_owner()
    owner._disconnect = AsyncMock(side_effect=TimeoutError("disconnect"))
    error = await retry.disconnect_and_reconnect_for_retry(
        owner, register_type="holding", start_address=20, attempt=1
    )
    assert isinstance(error, TimeoutError)

    owner, _client = _retry_owner(transport=object())
    owner._ensure_connection = AsyncMock(side_effect=ConnectionException("offline"))
    error = await retry.disconnect_and_reconnect_for_retry(
        owner, register_type="holding", start_address=20, attempt=1
    )
    assert isinstance(error, ConnectionException)


@pytest.mark.asyncio
async def test_retry_handler_terminal_and_reconnect_error_paths() -> None:
    owner, _client = _retry_owner(retry_count=1)
    terminal = TimeoutError("done")
    with pytest.raises(TimeoutError, match="done"):
        await retry._handle_retry_exception(
            owner,
            register_type="input",
            start_address=1,
            attempt=1,
            exc=terminal,
            reconnect=True,
        )

    owner, _client = _retry_owner(retry_count=2)
    reconnect_error = ConnectionException("reconnect")
    with patch.object(
        retry,
        "disconnect_and_reconnect_for_retry",
        new=AsyncMock(return_value=reconnect_error),
    ):
        returned = await retry._handle_retry_exception(
            owner,
            register_type="input",
            start_address=1,
            attempt=1,
            exc=TimeoutError("read"),
            reconnect=True,
        )
    assert returned is reconnect_error


@pytest.mark.asyncio
async def test_retry_zero_attempt_configuration_fails_closed() -> None:
    owner, _client = _retry_owner(retry_count=0)
    with pytest.raises(ModbusException, match="Failed to read input registers"):
        await retry.read_with_retry(owner, AsyncMock(), 7, 1, register_type="input")


@pytest.mark.asyncio
async def test_io_mixin_transport_wrappers_cover_connected_and_disconnected_clients() -> None:
    mixin = io_mixin._ModbusIOMixin()
    mixin.device_client = SimpleNamespace(client=None)
    mixin._call_modbus = AsyncMock(return_value="ok")

    with pytest.raises(ConnectionException, match="not connected"):
        await mixin._read_coils_transport(10, 1, count=2)
    with pytest.raises(ConnectionException, match="not connected"):
        await mixin._read_discrete_inputs_transport(10, 1, count=2)

    client = SimpleNamespace(read_coils=Mock(), read_discrete_inputs=Mock())
    mixin.device_client.client = client
    assert await mixin._read_coils_transport(10, 1, count=2, attempt=3) == "ok"
    mixin._call_modbus.assert_awaited_with(client.read_coils, 1, count=2, attempt=3)
    assert await mixin._read_discrete_inputs_transport(10, 2, count=1, attempt=4) == "ok"
    mixin._call_modbus.assert_awaited_with(client.read_discrete_inputs, 2, count=1, attempt=4)

    with patch.object(
        io_mixin,
        "_read_discrete_inputs_optimized_impl",
        new=AsyncMock(return_value={"ready": True}),
    ) as impl:
        assert await mixin._read_discrete_inputs_optimized() == {"ready": True}
    impl.assert_awaited_once_with(mixin)


def _register_group_client(*, safe_scan: bool):
    return SimpleNamespace(
        _register_groups={},
        available_registers={"holding_registers": {"r1"}},
        _register_maps={"holding_registers": {"r1": 10}},
        safe_scan=safe_scan,
        effective_batch=4,
    )


def test_register_groups_unexpected_definition_errors_fall_back_to_single_word() -> None:
    client = _register_group_client(safe_scan=True)
    register_groups.compute_register_groups(
        client,
        get_register_definition=Mock(side_effect=RuntimeError("definition")),
        group_reads=Mock(),
        holding_batch_boundaries=frozenset(),
    )
    assert client._register_groups["holding_registers"] == [(10, 1)]

    client = _register_group_client(safe_scan=False)
    group_reads = Mock(return_value=[(10, 1)])
    register_groups.compute_register_groups(
        client,
        get_register_definition=Mock(side_effect=OSError("definition")),
        group_reads=group_reads,
        holding_batch_boundaries=frozenset({20}),
    )
    group_reads.assert_called_once_with(
        [10], max_block_size=4, boundaries=frozenset({20})
    )
    assert client._register_groups["holding_registers"] == [(10, 1)]


def test_firmware_parse_unexpected_value_error_uses_addressable_test_map() -> None:
    class BadList(list):
        def __getitem__(self, index):
            raise RuntimeError("bad firmware value")

    test_map = {"version_major": 0, "version_minor": 1, "version_patch": 2}
    with patch.object(firmware, "INPUT_REGISTERS", test_map):
        major, minor, patch_value, error = firmware._parse_version_from_info_regs(
            BadList([1, 2, 3])
        )
    assert (major, minor, patch_value) == (None, None, None)
    assert isinstance(error, RuntimeError)


@pytest.mark.asyncio
async def test_firmware_probe_skips_part_absent_from_register_map() -> None:
    scanner = SimpleNamespace(_client=None, _read_input=AsyncMock())
    test_map = {"version_major": 0, "version_minor": 1}
    with patch.object(firmware, "INPUT_REGISTERS", test_map):
        result = await firmware._probe_missing_version_parts(scanner, 4, 85, None, None)
    assert result == (4, 85, None, None)
    scanner._read_input.assert_not_awaited()


@pytest.mark.asyncio
async def test_firmware_identity_unexpected_serial_parse_error_is_contained() -> None:
    class BadInfo(list):
        def __getitem__(self, index):
            if isinstance(index, slice):
                raise RuntimeError("serial slice")
            return super().__getitem__(index)

    device = ScannerDeviceInfo()
    scanner = SimpleNamespace(_read_holding_block=AsyncMock(return_value=[]))
    with patch.object(
        firmware,
        "INPUT_REGISTERS",
        {**firmware.INPUT_REGISTERS, "serial_number": 0},
    ):
        await firmware.scan_device_identity(scanner, BadInfo([0] * 16), device)
    assert device.serial_number == "Unknown"