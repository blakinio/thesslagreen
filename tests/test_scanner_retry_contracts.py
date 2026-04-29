"""Retry and reconnect behavior contracts for scanner I/O paths."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import ModbusException
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


def _make_ok_response(registers):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = list(registers)
    return resp


def _make_bit_response(bits):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.bits = list(bits)
    return resp


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


@pytest.mark.asyncio
async def test_maybe_retry_yield_backoff_positive():
    from custom_components.thessla_green_modbus.scanner.io_runtime import maybe_retry_yield

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        await maybe_retry_yield(backoff=0.1, attempt=0, retry=3)
        mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_call_modbus_with_fallback_type_error_reraise():
    from custom_components.thessla_green_modbus.scanner.io_runtime import call_modbus_with_fallback

    async def raise_other_type_error(*args, **kwargs):
        raise TypeError("something unrelated to keyword")

    with pytest.raises(TypeError, match="something unrelated"):
        await call_modbus_with_fallback(
            raise_other_type_error,
            MagicMock(),
            1,
            0,
            count=1,
            attempt=1,
            retry=1,
            timeout=5,
            backoff=0.0,
            backoff_jitter=None,
        )


@pytest.mark.asyncio
async def test_read_holding_skips_when_failures_exceed_retry():
    scanner = await _make_scanner(retry=2)
    scanner._holding_failures[10] = 2
    mock_client = AsyncMock()

    with patch(
        "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
        AsyncMock(),
    ) as mock_call:
        result = await scanner._read_holding(mock_client, 10, 1)

    assert result is None
    mock_call.assert_not_called()


@pytest.mark.asyncio
async def test_read_holding_success_clears_failure_counter():
    scanner = await _make_scanner(retry=3)
    scanner._holding_failures[5] = 1
    mock_client = AsyncMock()

    ok_resp = _make_ok_response([42])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(return_value=ok_resp),
        ),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_holding(mock_client, 5, 1)

    assert result == [42]
    assert 5 not in scanner._holding_failures


@pytest.mark.asyncio
async def test_read_coil_transport_reconnect_ensure_raises():
    scanner = await _make_scanner(retry=2)
    mock_transport = MagicMock()
    mock_transport.ensure_connected = AsyncMock(side_effect=OSError("reconnect fail"))
    scanner._transport = mock_transport

    mock_client = AsyncMock()
    scanner._client = mock_client

    bit_resp = _make_bit_response([True])
    call_count = {"n": 0}

    async def call_modbus_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ModbusException("connection lost")
        return bit_resp

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            side_effect=call_modbus_side_effect,
        ),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_coil(mock_client, 0, 1)

    assert result == [True]
    mock_transport.ensure_connected.assert_called()


@pytest.mark.asyncio
async def test_read_discrete_transport_reconnect_ensure_raises():
    scanner = await _make_scanner(retry=2)
    mock_transport = MagicMock()
    mock_transport.ensure_connected = AsyncMock(side_effect=OSError("reconnect fail"))
    scanner._transport = mock_transport

    mock_client = AsyncMock()
    scanner._client = mock_client

    bit_resp = _make_bit_response([True])
    call_count = {"n": 0}

    async def call_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ModbusException("connection lost")
        return bit_resp

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            side_effect=call_side_effect,
        ),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_discrete(mock_client, 0, 1)

    assert result == [True]
    mock_transport.ensure_connected.assert_called()
