from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymodbus.exceptions import ConnectionException


@pytest.mark.asyncio
async def test_coordinator_tracks_offline_and_recovers(monkeypatch) -> None:
    """Transient failures increment counters and successful reads reset them."""

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        MagicMock(),
        "host",
        502,
        1,
        "name",
        scan_interval=5,
        retry=1,
    )
    coordinator.client = MagicMock(connected=True)
    coordinator._disconnect = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    coordinator._read_input_registers_optimized = AsyncMock(
        side_effect=[ConnectionException("fail"), {"reg": 1}]
    )
    coordinator._read_holding_registers_optimized = AsyncMock(return_value={})
    coordinator._read_coil_registers_optimized = AsyncMock(return_value={})
    coordinator._read_discrete_inputs_optimized = AsyncMock(return_value={})

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator._consecutive_failures == 1  # nosec: explicit state check
    coordinator._read_input_registers_optimized.reset_mock(side_effect=True)
    coordinator._read_input_registers_optimized.side_effect = None
    coordinator._read_input_registers_optimized.return_value = {"reg": 1}

    data = await coordinator._async_update_data()

    assert data["reg"] == 1  # nosec: explicit state check
    assert coordinator._consecutive_failures == 0  # nosec: explicit state check
    assert coordinator.statistics["last_successful_update"] is not None  # nosec


@pytest.mark.asyncio
async def test_coordinator_disconnects_after_retries(monkeypatch) -> None:
    """Persistent failures force a disconnect and surface an error."""

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        MagicMock(),
        "host",
        502,
        1,
        "name",
        scan_interval=5,
        retry=1,
    )
    coordinator._max_failures = 1
    coordinator.client = MagicMock(connected=True)
    coordinator._disconnect = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    coordinator._read_input_registers_optimized = AsyncMock(side_effect=TimeoutError("boom"))
    coordinator._read_holding_registers_optimized = AsyncMock(return_value={})
    coordinator._read_coil_registers_optimized = AsyncMock(return_value={})
    coordinator._read_discrete_inputs_optimized = AsyncMock(return_value={})

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    coordinator._disconnect.assert_awaited_once()
    assert coordinator.client.connected  # nosec: explicit state check
