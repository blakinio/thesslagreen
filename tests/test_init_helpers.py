"""Tests for __init__.py helper functions: async_setup, _apply_log_level."""

import logging


def test_async_setup_removed():
    """async_setup is no longer exported — coordinator lives in entry.runtime_data."""
    import custom_components.thessla_green_modbus as mod

    assert not hasattr(mod, "async_setup"), (
        "async_setup should have been removed; use entry.runtime_data instead of hass.data"
    )


def test_apply_log_level_sets_debug():
    """_apply_log_level('DEBUG') raises the logger to DEBUG.

    The function was moved from __init__.py to _setup.py during cleanup.
    """
    import importlib

    # _setup.py requires pydantic via its register-map imports; skip gracefully when unavailable.
    try:
        mod = importlib.import_module("custom_components.thessla_green_modbus._setup")
    except ModuleNotFoundError as exc:
        import pytest

        pytest.skip(f"Skipping: missing optional dependency — {exc}")
        return

    _apply_log_level = mod._apply_log_level
    _apply_log_level("DEBUG")
    pkg = "custom_components.thessla_green_modbus"
    logger = logging.getLogger(pkg)
    assert logger.level == logging.DEBUG  # nosec B101
