"""Focused tests for the load_scanner_module runtime helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.config_flow.runtime import (
    load_scanner_module,
)

# ---------------------------------------------------------------------------
# load_scanner_module — synchronous fallback (hass is None)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_scanner_module_none_hass_imports_synchronously():
    """When hass is None the import is performed synchronously."""
    fake_module = MagicMock()
    with patch(
        "custom_components.thessla_green_modbus.config_flow.runtime.import_module",
        return_value=fake_module,
    ) as mock_import:
        result = await load_scanner_module(None)

    assert result is fake_module
    mock_import.assert_called_once_with("custom_components.thessla_green_modbus.scanner.core")


@pytest.mark.asyncio
async def test_load_scanner_module_hass_without_executor_imports_synchronously():
    """hass without async_add_executor_job falls back to synchronous import."""
    fake_module = MagicMock()
    hass_stub = object()  # no async_add_executor_job attribute

    with patch(
        "custom_components.thessla_green_modbus.config_flow.runtime.import_module",
        return_value=fake_module,
    ) as mock_import:
        result = await load_scanner_module(hass_stub)

    assert result is fake_module
    mock_import.assert_called_once()


# ---------------------------------------------------------------------------
# load_scanner_module — executor path (hass has async_add_executor_job)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_scanner_module_uses_executor_when_hass_available():
    """When hass provides async_add_executor_job the module is loaded via executor."""
    fake_module = MagicMock()
    hass_stub = MagicMock()
    hass_stub.async_add_executor_job = AsyncMock(return_value=fake_module)

    result = await load_scanner_module(hass_stub)

    assert result is fake_module
    hass_stub.async_add_executor_job.assert_called_once()
    # Verify import_module was passed as the callable
    call_args = hass_stub.async_add_executor_job.call_args
    from importlib import import_module

    assert call_args.args[0] is import_module
    assert call_args.args[1] == "custom_components.thessla_green_modbus.scanner.core"


@pytest.mark.asyncio
async def test_load_scanner_module_executor_receives_correct_path():
    """The exact module path is passed to the executor import."""
    from custom_components.thessla_green_modbus.config_flow.runtime import (
        _SCANNER_MODULE_PATH,
    )

    fake_module = MagicMock()
    hass_stub = MagicMock()
    hass_stub.async_add_executor_job = AsyncMock(return_value=fake_module)

    await load_scanner_module(hass_stub)

    _, path_arg = hass_stub.async_add_executor_job.call_args.args
    assert path_arg == _SCANNER_MODULE_PATH


# ---------------------------------------------------------------------------
# load_scanner_module — real import (integration smoke test)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_scanner_module_returns_real_module_without_hass():
    """Without hass the real scanner.core module is importable."""
    module = await load_scanner_module(None)
    assert hasattr(module, "DeviceCapabilities"), "scanner.core must export DeviceCapabilities"
