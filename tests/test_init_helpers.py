"""Tests for __init__.py and setup helper functions."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_async_setup_registers_global_services(monkeypatch):
    """async_setup owns process-lifetime integration service registration."""
    import custom_components.thessla_green_modbus as mod

    hass = MagicMock()
    setup_services = AsyncMock()
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.services.async_setup_services",
        setup_services,
    )

    assert await mod.async_setup(hass, {}) is True
    setup_services.assert_awaited_once_with(hass)


def test_apply_log_level_sets_debug():
    """_apply_log_level('DEBUG') raises the logger to DEBUG.

    The function was moved from __init__.py to _setup.py during cleanup.
    """
    import importlib

    try:
        mod = importlib.import_module("custom_components.thessla_green_modbus._setup")
    except ModuleNotFoundError as exc:
        pytest.skip(f"Skipping: missing optional dependency — {exc}")
        return

    _apply_log_level = mod._apply_log_level
    _apply_log_level("DEBUG")
    pkg = "custom_components.thessla_green_modbus"
    logger = logging.getLogger(pkg)
    assert logger.level == logging.DEBUG  # nosec B101
