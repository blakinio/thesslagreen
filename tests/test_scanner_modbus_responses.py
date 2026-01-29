"""Integration-style tests for Modbus retry/backoff handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner

pytestmark = pytest.mark.asyncio


async def test_scanner_retries_after_timeout() -> None:
    """Timeouts trigger retries with backoff before succeeding."""

    scanner = await ThesslaGreenDeviceScanner.create("host", 1234, 1, retry=2, backoff=0.5)
    scanner.retry = 2
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [42]
    attempts: list[int] = []

    async def fake_call(_func, _slave_id, *_args, attempt: int, **_kwargs):
        attempts.append(attempt)
        if attempt == 1:
            raise ConnectionException("boom")
        return response

    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        side_effect=fake_call,
    ):
        result = await scanner._read_input(AsyncMock(), 1, 1)

    assert result == [42]  # nosec: explicit assertion
    assert attempts[0] == 1 and attempts[-1] == 2  # nosec: explicit assertion


async def test_scanner_marks_permanent_failures() -> None:
    """Repeated errors mark registers as failed and stop retrying."""

    scanner = await ThesslaGreenDeviceScanner.create("host", 1234, 1, retry=2, backoff=0)
    mock_client = AsyncMock()
    mock_client.read_input_registers = AsyncMock(side_effect=ConnectionException("down"))

    result = await scanner._read_input(mock_client, 1, 1)

    assert result is None  # nosec: explicit assertion
    assert 1 in scanner._failed_input  # nosec: explicit assertion
