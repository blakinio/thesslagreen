from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.registers.loader import RegisterDef


@pytest.fixture
def coordinator() -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    available_registers = {
        "holding_registers": {"mode", "air_flow_rate_manual", "special_mode"},
        "input_registers": {"outside_temperature", "supply_temperature"},
        "coil_registers": {"system_on_off"},
        "discrete_inputs": set(),
    }
    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=10,
        retry=3,
    )
    coord.available_registers = available_registers
    return coord


@pytest.mark.asyncio
async def test_async_write_invalid_register(coordinator):
    """Return False and do not refresh on unknown register."""
    coordinator._ensure_connection = AsyncMock()
    result = await coordinator.async_write_register("invalid", 1)
    assert result is False


@pytest.mark.asyncio
async def test_async_write_valid_register(coordinator):
    """Test successful register write and refresh outside lock."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_register = AsyncMock(return_value=response)
    coordinator.client = client

    lock_state_during_refresh = None

    async def refresh_side_effect():
        nonlocal lock_state_during_refresh
        lock_state_during_refresh = coordinator._write_lock.locked()

    coordinator.async_request_refresh = AsyncMock(side_effect=refresh_side_effect)

    result = await coordinator.async_write_register("mode", 1)

    assert result is True
    coordinator.async_request_refresh.assert_called_once()
    assert lock_state_during_refresh is False


@pytest.mark.asyncio
async def test_async_write_register_numeric_out_of_range(coordinator, monkeypatch):
    """Numeric values outside defined range should raise."""
    coordinator._ensure_connection = AsyncMock()
    coordinator.client = MagicMock()

    import custom_components.thessla_green_modbus.coordinator.coordinator as coordinator_mod

    reg = RegisterDef(function="03", address=0, name="num", access="rw", min=0, max=10)
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: reg)

    with pytest.raises(ValueError):
        await coordinator.async_write_register("num", 11)


@pytest.mark.asyncio
async def test_async_write_register_enum_invalid(coordinator, monkeypatch):
    """Invalid enum values should raise and be propagated."""
    coordinator._ensure_connection = AsyncMock()
    coordinator.client = MagicMock()

    import custom_components.thessla_green_modbus.coordinator.coordinator as coordinator_mod

    reg = RegisterDef(function="03", address=0, name="mode", access="rw", enum={0: "off", 1: "on"})
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: reg)

    with pytest.raises(ValueError):
        await coordinator.async_write_register("mode", "invalid")


def test_validate_multi_register_write_request_limits(coordinator):
    """Reject empty writes and oversized single-request writes."""
    assert (
        coordinator._validate_multi_register_write_request(100, [], require_single_request=False)
        is False
    )
    assert (
        coordinator._validate_multi_register_write_request(
            100,
            list(range(1, 125)),
            require_single_request=True,
        )
        is False
    )


def test_plan_multi_register_chunks_respects_single_request(coordinator):
    """Single-request mode should avoid chunking."""
    coordinator.effective_batch = 2
    assert coordinator._plan_multi_register_chunks(200, [1, 2, 3], True) == [(200, [1, 2, 3])]
    assert coordinator._plan_multi_register_chunks(200, [1, 2, 3], False) == [
        (200, [1, 2]),
        (202, [3]),
    ]



def test_handle_write_response_failure_logs_retry(coordinator, caplog):
    """Non-final failures should log retry and continue."""
    caplog.set_level("INFO")
    should_retry = coordinator._handle_write_response_failure(
        is_final_attempt=False,
        final_error_message="Error writing to register %s: %s",
        retry_message="Retrying write to register mode",
        error_args=("mode", "err"),
    )
    assert should_retry is True
    assert "Retrying write to register mode" in caplog.text


def test_handle_write_response_failure_logs_error(coordinator, caplog):
    """Final failures should log error and stop."""
    caplog.set_level("ERROR")
    should_retry = coordinator._handle_write_response_failure(
        is_final_attempt=True,
        final_error_message="Error writing to register %s: %s",
        retry_message="Retrying write to register mode",
        error_args=("mode", "err"),
    )
    assert should_retry is False
    assert "Error writing to register mode: err" in caplog.text
