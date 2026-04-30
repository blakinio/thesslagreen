"""Additional full-register scan coverage tests for scanner core."""

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


def _ok_input_block(count):
    return [0] * count


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


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
