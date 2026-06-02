"""Tests for coordinator/errors.py (apply_update_failure_state / handle_update_error)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator.errors import (
    apply_update_failure_state,
    handle_update_error,
)
from homeassistant.helpers.update_coordinator import UpdateFailed


def _make_coord(*, consecutive_failures: int = 0, max_failures: int = 5):
    coord = MagicMock()
    coord.device_client = SimpleNamespace(
        statistics={"failed_reads": 0, "timeout_errors": 0, "last_error": None},
        _consecutive_failures=consecutive_failures,
        _max_failures=max_failures,
        offline_state=False,
    )
    coord._disconnect = AsyncMock()
    coord._trigger_reauth = MagicMock()
    coord._resolve_update_failure = MagicMock(return_value=UpdateFailed("resolved"))
    return coord


# ---------------------------------------------------------------------------
# apply_update_failure_state
# ---------------------------------------------------------------------------


def test_apply_increments_failed_reads():
    coord = _make_coord()
    apply_update_failure_state(coord, RuntimeError("x"), timeout_error=False)
    assert coord.device_client.statistics["failed_reads"] == 1


def test_apply_increments_timeout_errors_when_true():
    coord = _make_coord()
    apply_update_failure_state(coord, RuntimeError("x"), timeout_error=True)
    assert coord.device_client.statistics["timeout_errors"] == 1


def test_apply_skips_timeout_counter_when_false():
    coord = _make_coord()
    apply_update_failure_state(coord, RuntimeError("x"), timeout_error=False)
    assert coord.device_client.statistics["timeout_errors"] == 0


def test_apply_sets_offline_state():
    coord = _make_coord()
    apply_update_failure_state(coord, RuntimeError("x"), timeout_error=False)
    assert coord.device_client.offline_state is True


def test_apply_records_error_message():
    coord = _make_coord()
    apply_update_failure_state(coord, RuntimeError("bad stuff"), timeout_error=False)
    assert "bad stuff" in coord.device_client.statistics["last_error"]


def test_apply_increments_consecutive_failures():
    coord = _make_coord(consecutive_failures=2)
    apply_update_failure_state(coord, RuntimeError("x"), timeout_error=False)
    assert coord.device_client._consecutive_failures == 3


# ---------------------------------------------------------------------------
# handle_update_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_calls_disconnect():
    coord = _make_coord()
    await handle_update_error(coord, RuntimeError("x"), reauth_reason="r", message="m")
    coord._disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_handle_triggers_reauth_when_at_max_failures():
    coord = _make_coord(consecutive_failures=4, max_failures=5)
    await handle_update_error(coord, RuntimeError("x"), reauth_reason="too_many", message="m")
    coord._trigger_reauth.assert_called_once_with("too_many")


@pytest.mark.asyncio
async def test_handle_no_reauth_below_max_failures():
    coord = _make_coord(consecutive_failures=1, max_failures=5)
    await handle_update_error(coord, RuntimeError("x"), reauth_reason="r", message="m")
    coord._trigger_reauth.assert_not_called()


@pytest.mark.asyncio
async def test_handle_uses_resolve_helper_by_default():
    coord = _make_coord()
    result = await handle_update_error(coord, RuntimeError("x"), reauth_reason="r", message="m")
    coord._resolve_update_failure.assert_called_once()
    assert isinstance(result, UpdateFailed)


@pytest.mark.asyncio
async def test_handle_returns_update_failed_when_use_helper_false():
    coord = _make_coord()
    result = await handle_update_error(
        coord, RuntimeError("oops"), reauth_reason="r", message="msg", use_helper=False
    )
    assert isinstance(result, UpdateFailed)
    assert "oops" in str(result)


@pytest.mark.asyncio
async def test_handle_applies_failure_state():
    coord = _make_coord()
    await handle_update_error(coord, RuntimeError("x"), reauth_reason="r", message="m")
    assert coord.device_client.statistics["failed_reads"] == 1
    assert coord.device_client.offline_state is True


@pytest.mark.asyncio
async def test_handle_triggers_invalid_auth_reauth_when_check_auth():
    from unittest.mock import patch

    coord = _make_coord()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.errors.is_invalid_auth_error",
        return_value=True,
    ):
        await handle_update_error(
            coord,
            RuntimeError("auth error"),
            reauth_reason="r",
            message="m",
            check_auth=True,
        )
    coord._trigger_reauth.assert_called_with("invalid_auth")
