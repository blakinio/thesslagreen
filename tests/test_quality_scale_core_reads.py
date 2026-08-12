# mypy: ignore-errors
"""Risk-focused coverage for low-level read and transport-selection helpers."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pymodbus.exceptions import ConnectionException, ModbusException

from custom_components.thessla_green_modbus.const import (
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    DEFAULT_PORT,
)
from custom_components.thessla_green_modbus.core.read_bits import (
    read_coil_registers_optimized,
    read_discrete_inputs_optimized,
)
from custom_components.thessla_green_modbus.core.retry import _PermanentModbusError
from custom_components.thessla_green_modbus.core.transport_select import select_auto_transport


_BIT_READ_CASES = (
    (read_coil_registers_optimized, "coil_registers", "_read_coils_transport", "coil"),
    (
        read_discrete_inputs_optimized,
        "discrete_inputs",
        "_read_discrete_inputs_transport",
        "discrete",
    ),
)


def _bit_owner(
    *,
    group: str,
    transport_attr: str,
    bits: list[bool] | None = None,
    available: set[str] | None = None,
) -> SimpleNamespace:
    names = {0: "r0", 1: "r1", 2: "r2"}
    device_client = SimpleNamespace(
        _register_groups={group: [(0, 3)]},
        client=SimpleNamespace(connected=True),
        effective_batch=16,
        available_registers={group: available if available is not None else set(names.values())},
        statistics={"total_registers_read": 0},
    )
    owner = SimpleNamespace(
        device_client=device_client,
        _failed_registers=set(),
        _find_register_name=Mock(side_effect=lambda _group, address: names.get(address)),
        _mark_registers_failed=Mock(),
        _clear_register_failure=Mock(),
        _read_with_retry=AsyncMock(return_value=SimpleNamespace(bits=bits if bits is not None else [True, False, True])),
    )
    setattr(owner, transport_attr, AsyncMock())
    return owner


@pytest.mark.asyncio
@pytest.mark.parametrize("reader,group,transport_attr,register_type", _BIT_READ_CASES)
async def test_bit_reader_returns_empty_without_group(reader, group, transport_attr, register_type):
    owner = SimpleNamespace(device_client=SimpleNamespace(_register_groups={}))
    assert await reader(owner) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("reader,group,transport_attr,register_type", _BIT_READ_CASES)
@pytest.mark.parametrize("client", [None, SimpleNamespace(connected=False)])
async def test_bit_reader_requires_connected_client(
    reader, group, transport_attr, register_type, client
):
    owner = _bit_owner(group=group, transport_attr=transport_attr)
    owner.device_client.client = client
    with pytest.raises(ConnectionException, match="not connected"):
        await reader(owner)


@pytest.mark.asyncio
@pytest.mark.parametrize("reader,group,transport_attr,register_type", _BIT_READ_CASES)
async def test_bit_reader_skips_chunk_when_every_known_register_failed(
    reader, group, transport_attr, register_type
):
    owner = _bit_owner(group=group, transport_attr=transport_attr)
    owner._failed_registers = {"r0", "r1", "r2"}

    assert await reader(owner) == {}
    owner._read_with_retry.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("reader,group,transport_attr,register_type", _BIT_READ_CASES)
async def test_bit_reader_reads_full_chunk_and_clears_failures(
    reader, group, transport_attr, register_type
):
    owner = _bit_owner(group=group, transport_attr=transport_attr, bits=[True, False, True])

    result = await reader(owner)

    assert result == {"r0": True, "r1": False, "r2": True}
    assert owner.device_client.statistics["total_registers_read"] == 3
    owner._read_with_retry.assert_awaited_once_with(
        getattr(owner, transport_attr), 0, 3, register_type=register_type
    )
    assert owner._clear_register_failure.call_count == 3
    owner._mark_registers_failed.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("reader,group,transport_attr,register_type", _BIT_READ_CASES)
async def test_bit_reader_marks_short_response_tail_failed(
    reader, group, transport_attr, register_type
):
    owner = _bit_owner(group=group, transport_attr=transport_attr, bits=[True, False])

    result = await reader(owner)

    assert result == {"r0": True, "r1": False}
    assert owner.device_client.statistics["total_registers_read"] == 2
    owner._mark_registers_failed.assert_called_once_with(["r2"])


@pytest.mark.asyncio
@pytest.mark.parametrize("reader,group,transport_attr,register_type", _BIT_READ_CASES)
async def test_bit_reader_ignores_detected_name_not_in_available_set(
    reader, group, transport_attr, register_type
):
    owner = _bit_owner(
        group=group,
        transport_attr=transport_attr,
        bits=[True, False, True],
        available={"r0"},
    )

    assert await reader(owner) == {"r0": True}
    assert owner.device_client.statistics["total_registers_read"] == 1
    owner._clear_register_failure.assert_called_once_with("r0")


@pytest.mark.asyncio
@pytest.mark.parametrize("reader,group,transport_attr,register_type", _BIT_READ_CASES)
async def test_bit_reader_rejects_empty_response(
    reader, group, transport_attr, register_type
):
    owner = _bit_owner(group=group, transport_attr=transport_attr, bits=[])

    with pytest.raises(ModbusException, match="No bits returned"):
        await reader(owner)

    assert owner._mark_registers_failed.call_count >= 1
    assert owner._mark_registers_failed.call_args.args[0] == ["r0", "r1", "r2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("reader,group,transport_attr,register_type", _BIT_READ_CASES)
async def test_bit_reader_permanent_error_marks_chunk_and_continues(
    reader, group, transport_attr, register_type
):
    owner = _bit_owner(group=group, transport_attr=transport_attr)
    owner._read_with_retry.side_effect = _PermanentModbusError("unsupported")

    assert await reader(owner) == {}
    owner._mark_registers_failed.assert_called_once_with(["r0", "r1", "r2"])


@pytest.mark.asyncio
@pytest.mark.parametrize("reader,group,transport_attr,register_type", _BIT_READ_CASES)
async def test_bit_reader_transient_error_marks_chunk_and_reraises(
    reader, group, transport_attr, register_type
):
    owner = _bit_owner(group=group, transport_attr=transport_attr)
    owner._read_with_retry.side_effect = ValueError("bad response")

    with pytest.raises(ValueError, match="bad response"):
        await reader(owner)
    owner._mark_registers_failed.assert_called_once_with(["r0", "r1", "r2"])


class _FakeTransport:
    def __init__(self) -> None:
        self.ensure_connected = AsyncMock()
        self.read_holding_registers = AsyncMock(return_value=SimpleNamespace(registers=[1, 2]))
        self.close = AsyncMock()


def _transport_kwargs(*, port: int = DEFAULT_PORT, timeout: float = 6.0):
    logger = logging.getLogger("tests.quality_scale.transport")
    transports = {
        CONNECTION_MODE_TCP: _FakeTransport(),
        CONNECTION_MODE_TCP_RTU: _FakeTransport(),
    }
    build_calls: list[str] = []

    def build(mode: str):
        build_calls.append(mode)
        return transports[mode]

    direct = AsyncMock(return_value=False)
    kwargs = {
        "resolved_connection_mode": None,
        "build_tcp_transport": build,
        "try_direct_client_connect": direct,
        "port": port,
        "timeout": timeout,
        "slave_id": 1,
        "host": "192.0.2.10",
        "logger": logger,
    }
    return kwargs, transports, build_calls, direct


@pytest.mark.asyncio
async def test_auto_transport_uses_pre_resolved_mode_without_probing():
    kwargs, transports, build_calls, direct = _transport_kwargs()
    kwargs["resolved_connection_mode"] = CONNECTION_MODE_TCP_RTU

    transport, mode = await select_auto_transport(**kwargs)

    assert transport is transports[CONNECTION_MODE_TCP_RTU]
    assert mode == CONNECTION_MODE_TCP_RTU
    assert build_calls == [CONNECTION_MODE_TCP_RTU]
    direct.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_transport_accepts_direct_client_connection():
    kwargs, _transports, build_calls, direct = _transport_kwargs()
    direct.return_value = True

    assert await select_auto_transport(**kwargs) == (None, None)
    assert build_calls == []
    direct.assert_awaited_once_with(True)


@pytest.mark.asyncio
async def test_auto_transport_default_port_prefers_tcp():
    kwargs, transports, build_calls, _direct = _transport_kwargs(port=DEFAULT_PORT)

    transport, mode = await select_auto_transport(**kwargs)

    assert transport is transports[CONNECTION_MODE_TCP]
    assert mode == CONNECTION_MODE_TCP
    assert build_calls == [CONNECTION_MODE_TCP]
    transports[CONNECTION_MODE_TCP].read_holding_registers.assert_awaited_once_with(
        1, 0, count=2
    )


@pytest.mark.asyncio
async def test_auto_transport_non_default_port_prefers_rtu_over_tcp():
    kwargs, transports, build_calls, _direct = _transport_kwargs(port=12345)

    transport, mode = await select_auto_transport(**kwargs)

    assert transport is transports[CONNECTION_MODE_TCP_RTU]
    assert mode == CONNECTION_MODE_TCP_RTU
    assert build_calls == [CONNECTION_MODE_TCP_RTU]


@pytest.mark.asyncio
async def test_auto_transport_direct_error_falls_back_and_protocol_error_is_valid(caplog):
    kwargs, transports, build_calls, direct = _transport_kwargs()
    direct.side_effect = ValueError("direct unavailable")
    transports[CONNECTION_MODE_TCP].read_holding_registers.side_effect = ModbusException(
        "illegal address"
    )

    with caplog.at_level(logging.DEBUG, logger=kwargs["logger"].name):
        transport, mode = await select_auto_transport(**kwargs)

    assert transport is transports[CONNECTION_MODE_TCP]
    assert mode == CONNECTION_MODE_TCP
    assert build_calls == [CONNECTION_MODE_TCP]
    assert any("Direct client connect attempt failed" in record.message for record in caplog.records)
    assert any("valid protocol" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_auto_transport_closes_failed_candidate_then_uses_fallback():
    kwargs, transports, build_calls, _direct = _transport_kwargs()
    transports[CONNECTION_MODE_TCP].ensure_connected.side_effect = OSError("tcp down")

    transport, mode = await select_auto_transport(**kwargs)

    assert transport is transports[CONNECTION_MODE_TCP_RTU]
    assert mode == CONNECTION_MODE_TCP_RTU
    assert build_calls == [CONNECTION_MODE_TCP, CONNECTION_MODE_TCP_RTU]
    transports[CONNECTION_MODE_TCP].close.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_transport_all_candidates_fail_with_last_error_as_cause():
    kwargs, transports, build_calls, _direct = _transport_kwargs(port=12345)
    first_error = TimeoutError("rtu timeout")
    last_error = OSError("tcp down")
    transports[CONNECTION_MODE_TCP_RTU].ensure_connected.side_effect = first_error
    transports[CONNECTION_MODE_TCP].ensure_connected.side_effect = last_error

    with pytest.raises(ConnectionException, match="Auto-detect Modbus transport failed") as exc_info:
        await select_auto_transport(**kwargs)

    assert build_calls == [CONNECTION_MODE_TCP_RTU, CONNECTION_MODE_TCP]
    assert exc_info.value.__cause__ is last_error
    transports[CONNECTION_MODE_TCP_RTU].close.assert_awaited_once()
    transports[CONNECTION_MODE_TCP].close.assert_awaited_once()
