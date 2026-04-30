"""Targeted coverage tests for scanner_core.py uncovered lines."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


def _make_ok_response(registers):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = list(registers)
    return resp


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


def _make_transport(
    *, raises_on_close=None, ensure_side_effect=None, input_response=None, holding_response=None
):
    transport = MagicMock()
    if raises_on_close:
        transport.close = AsyncMock(side_effect=raises_on_close)
    else:
        transport.close = AsyncMock()
    if ensure_side_effect:
        transport.ensure_connected = AsyncMock(side_effect=ensure_side_effect)
    else:
        transport.ensure_connected = AsyncMock()
    transport.read_input_registers = AsyncMock(return_value=input_response or _make_ok_response([1]))
    transport.read_holding_registers = AsyncMock(return_value=holding_response or _make_ok_response([1]))
    transport.is_connected = MagicMock(return_value=True)
    return transport


def _ok_input_block(count):
    return [0] * count


async def _run_minimal_scan(
    scanner, *, input_return=None, holding_return=None, coil_return=None, discrete_return=None
):
    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=_ok_input_block(30))),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=input_return)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=holding_return)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=coil_return)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=discrete_return)),
    ):
        return await scanner.scan()


def _sized_read_mock(value=1):
    async def _mock(*args, **kw):
        count = 1
        for arg in reversed(args):
            if isinstance(arg, int):
                count = arg
                break
        return [value] * count

    return _mock


def test_build_register_maps_direct():
    from custom_components.thessla_green_modbus.scanner.register_map_runtime import (
        build_register_maps,
    )

    build_register_maps()
    from custom_components.thessla_green_modbus.scanner.core import REGISTER_DEFINITIONS

    assert isinstance(REGISTER_DEFINITIONS, dict)


@pytest.mark.asyncio
async def test_scan_raises_without_transport_and_client():
    scanner = await _make_scanner()
    scanner._transport = None
    scanner._client = None
    with pytest.raises(ConnectionException, match="Transport not connected"):
        await scanner.scan()


@pytest.mark.asyncio
async def test_scan_raises_when_transport_disconnected_and_no_client():
    scanner = await _make_scanner()
    mock_transport = MagicMock()
    mock_transport.is_connected.return_value = False
    scanner._transport = mock_transport
    scanner._client = None
    with pytest.raises(ConnectionException, match="Transport not connected"):
        await scanner.scan()


@pytest.mark.asyncio
async def test_full_register_scan_discrete_unknown_addr():
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {2: "fake_discrete"}}
    scanner._names_by_address[2] = {2: {"fake_discrete"}}

    async def discrete_mock(*args, **kw):
        count = 1
        for a in reversed(args):
            if isinstance(a, int):
                count = a
                break
        return [True] * count

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", side_effect=discrete_mock),
    ):
        result = await scanner.scan()

    assert 0 in result["unknown_registers"]["discrete_inputs"]


@pytest.mark.asyncio
async def test_scan_input_probe_returns_invalid_value_v2():
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {9999: "fake_input"}, 3: {}, 1: {}, 2: {}}
    scanner._names_by_address[4] = {9999: {"fake_input"}}

    async def smart_read_input(*args, **kwargs):
        skip_cache = kwargs.get("skip_cache", False)
        addr = None
        if len(args) >= 2:
            for a in args:
                if isinstance(a, int):
                    addr = a
                    break
        if addr == 9999:
            if not skip_cache:
                return None
            return [65535]
        return None

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", side_effect=smart_read_input),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert 9999 in result["failed_addresses"]["invalid_values"]["input_registers"]
