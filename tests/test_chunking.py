from unittest.mock import AsyncMock

import pytest

from custom_components.thessla_green_modbus.modbus_helpers import (
    chunk_register_range,
    chunk_register_values,
)
from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner


def test_chunk_register_values_max_16():
    values = list(range(20))
    chunks = chunk_register_values(100, values, max_block_size=16)
    assert sum(len(chunk) for _, chunk in chunks) == 20
    assert max(len(chunk) for _, chunk in chunks) <= 16


def test_chunk_register_range_max_16():
    chunks = chunk_register_range(10, 20, max_block_size=16)
    assert sum(count for _, count in chunks) == 20
    assert max(count for _, count in chunks) <= 16


@pytest.mark.asyncio
async def test_scanner_read_block_chunks_requests():
    scanner = ThesslaGreenDeviceScanner("host", 1234)
    scanner.effective_batch = 16
    scanner._read_input = AsyncMock(side_effect=lambda *_args, **_kwargs: [0])

    await scanner._read_input_block(AsyncMock(), 0, 20)

    counts = [call.args[2] for call in scanner._read_input.await_args_list]
    assert all(count <= 16 for count in counts)
