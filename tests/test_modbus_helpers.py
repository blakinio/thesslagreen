# mypy: ignore-errors
"""Tests for the Modbus helper utilities."""

import asyncio
import gc
import sys
import types
import weakref

import pytest

original_registers = sys.modules.get("custom_components.thessla_green_modbus.registers")
original_loader = sys.modules.get("custom_components.thessla_green_modbus.registers.loader")

loader_stub = types.SimpleNamespace(
    load_registers=lambda: ([], {}),
    get_all_registers=lambda: [],
    get_registers_by_function=lambda fn: [],
)
sys.modules["custom_components.thessla_green_modbus.registers.loader"] = loader_stub
sys.modules["custom_components.thessla_green_modbus.registers"] = types.SimpleNamespace(
    loader=loader_stub,
    get_all_registers=loader_stub.get_all_registers,
    get_registers_by_function=loader_stub.get_registers_by_function,
)

from custom_components.thessla_green_modbus.modbus_helpers import (  # noqa: E402
    _KWARG_CACHE,
    _SIG_CACHE,
    _call_modbus,
    async_close_client,
    group_reads,
)

if original_loader is not None:
    sys.modules["custom_components.thessla_green_modbus.registers.loader"] = original_loader
else:
    sys.modules.pop("custom_components.thessla_green_modbus.registers.loader", None)

if original_registers is not None:
    sys.modules["custom_components.thessla_green_modbus.registers"] = original_registers
else:
    sys.modules.pop("custom_components.thessla_green_modbus.registers", None)

pytestmark = pytest.mark.asyncio


async def test_call_modbus_supports_unit_keyword():
    """Functions expecting ``unit`` should be handled."""

    async def func(address, *, count, unit=None):
        return address, count, unit

    result = await _call_modbus(func, 1, 10, 2)
    assert result == (10, 2, 1)  # nosec B101


async def test_call_modbus_supports_slave_keyword():
    """Functions expecting ``slave`` should be handled."""

    async def func(address, *, count, slave=None):
        return address, count, slave

    result = await _call_modbus(func, 1, 20, 3)
    assert result == (20, 3, 1)  # nosec B101


async def test_call_modbus_supports_no_slave_or_unit():
    """Functions expecting neither keyword should be handled."""

    async def func(address, *, count):
        return address, count

    result = await _call_modbus(func, 1, 30, 4)
    assert result == (30, 4)  # nosec B101


async def test_call_modbus_propagates_cancelled_error():
    """Cancelled errors should propagate without being mapped."""

    async def func(address, *, count):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _call_modbus(func, 1, 30, 4)


async def test_group_reads_merges_sequential_addresses():
    """Sequential addresses are merged into contiguous blocks."""

    assert group_reads([0, 1, 2, 4, 5]) == [(0, 3), (4, 2)]


async def test_group_reads_honours_block_size():
    """Groups are split when exceeding ``max_block_size``."""

    assert group_reads(range(10), max_block_size=4) == [
        (0, 4),
        (4, 4),
        (8, 2),
    ]


async def test_modbus_cache_entries_removed_on_gc():
    """Cached entries should disappear when functions are garbage collected."""

    _KWARG_CACHE.clear()
    _SIG_CACHE.clear()

    async def func(address, *, count, unit=None):
        return address, count, unit

    await _call_modbus(func, 1, 10, 2)
    assert func in _KWARG_CACHE
    assert func in _SIG_CACHE

    func_ref = weakref.ref(func)
    del func
    gc.collect()

    assert func_ref() is None
    assert len(_KWARG_CACHE) == 0
    assert len(_SIG_CACHE) == 0


async def test_async_close_client_with_sync_close():
    """Synchronous close should be handled without awaiting."""

    class SyncClient:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True
            return None

    client = SyncClient()
    await async_close_client(client)
    assert client.closed is True  # nosec B101


async def test_async_close_client_with_async_close():
    """Async close should be awaited."""

    class AsyncClient:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    client = AsyncClient()
    await async_close_client(client)
    assert client.closed is True  # nosec B101
