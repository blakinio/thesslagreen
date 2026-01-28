"""Tests for hardening helpers and write chunking."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.registers import REG_TEMPORARY_FLOW_MODE
from custom_components.thessla_green_modbus.utils import decode_int16, decode_temp_01c


class DummyResponse:
    """Simple Modbus response stub."""

    def isError(self) -> bool:
        return False


def test_decode_int16_signed_values():
    """Signed int16 decoding should handle negative values."""
    assert decode_int16(0) == 0
    assert decode_int16(32767) == 32767
    assert decode_int16(32768) == -32768
    assert decode_int16(65535) == -1


def test_decode_temp_01c_handles_missing():
    """Temperature decode should handle missing values and scaling."""
    assert decode_temp_01c(32768) is None
    assert decode_temp_01c(250) == 25.0
    assert decode_temp_01c(65526) == -1.0


@pytest.mark.asyncio
async def test_async_write_registers_chunks():
    """Writes should be chunked to 16 registers."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev")
    coordinator.client = MagicMock()
    coordinator._ensure_connected = AsyncMock()
    coordinator._call_modbus = AsyncMock(return_value=DummyResponse())

    values = list(range(40))
    result = await coordinator.async_write_registers(100, values, refresh=False)

    assert result is True
    assert len(coordinator._call_modbus.call_args_list) == 3
    for call in coordinator._call_modbus.call_args_list:
        assert len(call.kwargs["values"]) <= 16


@pytest.mark.asyncio
async def test_temporary_airflow_multi_register_write():
    """Temporary airflow writes should use mode/value/flag registers."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev")
    coordinator.client = MagicMock()
    coordinator._ensure_connected = AsyncMock()
    coordinator._call_modbus = AsyncMock(return_value=DummyResponse())
    coordinator._find_register_name = MagicMock(return_value=None)

    result = await coordinator.async_write_temporary_airflow(
        mode=2,
        airflow=120,
        flag=1,
        refresh=False,
    )

    assert result is True
    call = coordinator._call_modbus.call_args_list[0]
    assert call.kwargs["address"] == REG_TEMPORARY_FLOW_MODE
    assert call.kwargs["values"] == [2, 120, 1]
