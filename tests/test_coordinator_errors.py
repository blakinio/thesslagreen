from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
    _PermanentModbusError,
)


@pytest.mark.asyncio
async def test_read_with_retry_retries_transient_errors():
    """Coordinator retries transient read errors before succeeding."""

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        MagicMock(),
        "host",
        502,
        1,
        "name",
        retry=2,
    )
    coordinator._disconnect = AsyncMock()
    response = MagicMock()
    response.isError.return_value = False
    coordinator._call_modbus = AsyncMock(side_effect=[TimeoutError("boom"), response])

    result = await coordinator._read_with_retry(
        lambda *_args, **_kwargs: None,
        10,
        1,
        register_type="input",
    )

    assert result is response  # nosec: explicit state check
    assert coordinator._call_modbus.await_count == 2


@pytest.mark.asyncio
async def test_read_with_retry_skips_illegal_data_address():
    """Illegal data address errors should not be retried."""

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        MagicMock(),
        "host",
        502,
        1,
        "name",
        retry=3,
    )
    coordinator._disconnect = AsyncMock()

    response = MagicMock()
    response.isError.return_value = True
    response.exception_code = 2
    coordinator._call_modbus = AsyncMock(return_value=response)

    with pytest.raises(_PermanentModbusError):
        await coordinator._read_with_retry(
            lambda *_args, **_kwargs: None,
            10,
            1,
            register_type="input",
        )

    assert coordinator._call_modbus.await_count == 1
    coordinator._disconnect.assert_not_awaited()
