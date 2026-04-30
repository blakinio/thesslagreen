"""Shared scanner test helpers kept for split scanner test modules."""

from unittest.mock import AsyncMock, MagicMock

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
    from unittest.mock import patch

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
