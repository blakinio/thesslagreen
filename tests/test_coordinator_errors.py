from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.core.retry import _PermanentModbusError


@pytest.mark.asyncio
async def test_read_with_retry_retries_transient_errors():
    """DeviceClient retries transient read errors before succeeding."""

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        MagicMock(),
        "host",
        502,
        1,
        "name",
        retry=2,
    )
    dc = coordinator.device_client
    dc._disconnect = AsyncMock()
    response = MagicMock()
    response.isError.return_value = False
    dc._call_modbus = AsyncMock(side_effect=[TimeoutError("boom"), response])

    result = await dc._read_with_retry(
        lambda *_args, **_kwargs: None,
        10,
        1,
        register_type="input",
    )

    assert result is response  # nosec: explicit state check
    assert dc._call_modbus.await_count == 2


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
    dc = coordinator.device_client
    dc._disconnect = AsyncMock()

    response = MagicMock()
    response.isError.return_value = True
    response.exception_code = 2
    dc._call_modbus = AsyncMock(return_value=response)

    with pytest.raises(_PermanentModbusError):
        await dc._read_with_retry(
            lambda *_args, **_kwargs: None,
            10,
            1,
            register_type="input",
        )

    assert dc._call_modbus.await_count == 1
    dc._disconnect.assert_not_awaited()
