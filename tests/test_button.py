"""Tests for the button platform (SyncDeviceClockButton)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.button import SyncDeviceClockButton
from custom_components.thessla_green_modbus.const import (
    CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
)
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError


def _make_coordinator(*, last_update_success=True, offline=False):
    coord = MagicMock()
    coord.last_update_success = last_update_success
    coord.device_client = SimpleNamespace(offline_state=offline)
    return coord


def _make_entry(options=None):
    entry = MagicMock()
    entry.options = options or {}
    return entry


def _make_button(*, last_update_success=True, offline=False, options=None):
    coord = _make_coordinator(last_update_success=last_update_success, offline=offline)
    entry = _make_entry(options=options)
    return SyncDeviceClockButton(coord, entry)


# ---------------------------------------------------------------------------
# Static attributes
# ---------------------------------------------------------------------------


def test_entity_category_is_config():
    btn = _make_button()
    assert btn._attr_entity_category == EntityCategory.CONFIG


def test_device_class_is_restart():
    btn = _make_button()
    assert btn._attr_device_class == ButtonDeviceClass.RESTART


def test_translation_key():
    btn = _make_button()
    assert btn._attr_translation_key == "sync_device_clock"


# ---------------------------------------------------------------------------
# available property
# ---------------------------------------------------------------------------


def test_available_when_connected():
    btn = _make_button(last_update_success=True, offline=False)
    assert btn.available is True


def test_available_false_when_last_update_failed():
    btn = _make_button(last_update_success=False, offline=False)
    assert btn.available is False


def test_available_false_when_offline():
    btn = _make_button(last_update_success=True, offline=True)
    assert btn.available is False


# ---------------------------------------------------------------------------
# async_press — success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_press_success_returns_none():
    btn = _make_button()
    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new=AsyncMock(return_value=True),
    ):
        result = await btn.async_press()
    assert result is None


@pytest.mark.asyncio
async def test_press_passes_force_true():
    btn = _make_button()
    mock_sync = AsyncMock(return_value=True)
    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new=mock_sync,
    ):
        await btn.async_press()
    _, kwargs = mock_sync.call_args
    assert kwargs["force"] is True


@pytest.mark.asyncio
async def test_press_uses_default_max_drift_when_option_absent():
    btn = _make_button(options={})
    mock_sync = AsyncMock(return_value=True)
    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new=mock_sync,
    ):
        await btn.async_press()
    _, kwargs = mock_sync.call_args
    assert kwargs["max_drift_seconds"] == DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS


@pytest.mark.asyncio
async def test_press_reads_max_drift_from_options():
    btn = _make_button(options={CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS: 120})
    mock_sync = AsyncMock(return_value=True)
    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new=mock_sync,
    ):
        await btn.async_press()
    _, kwargs = mock_sync.call_args
    assert kwargs["max_drift_seconds"] == 120


# ---------------------------------------------------------------------------
# async_press — failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_press_raises_ha_error_when_sync_returns_false():
    btn = _make_button()
    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(HomeAssistantError, match="Failed to write device clock registers"):
            await btn.async_press()


@pytest.mark.asyncio
async def test_press_reraises_ha_error_unchanged():
    btn = _make_button()
    original = HomeAssistantError("original error")
    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new=AsyncMock(side_effect=original),
    ):
        with pytest.raises(HomeAssistantError, match="original error"):
            await btn.async_press()


@pytest.mark.asyncio
async def test_press_wraps_generic_exception_in_ha_error():
    btn = _make_button()
    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(HomeAssistantError, match="Clock sync failed: boom"):
            await btn.async_press()


@pytest.mark.asyncio
async def test_press_wraps_oserror_in_ha_error():
    btn = _make_button()
    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new=AsyncMock(side_effect=OSError("connection refused")),
    ):
        with pytest.raises(HomeAssistantError, match="Clock sync failed"):
            await btn.async_press()
