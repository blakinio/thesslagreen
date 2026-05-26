"""Split coordinator coverage tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.helpers_coordinator import make_coordinator as _make_coordinator


@pytest.mark.asyncio
async def test_async_write_temporary_airflow():
    """async_write_temporary_airflow calls async_write_registers when registers exist."""
    coord = _make_coordinator()
    coord.async_write_registers = AsyncMock(return_value=True)
    mock_def = MagicMock()
    mock_def.encode = MagicMock(return_value=1)
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_temporary_airflow(50.0)
    assert result is True
    coord.async_write_registers.assert_called_once()


@pytest.mark.asyncio
async def test_async_write_temporary_airflow_missing_register():
    """async_write_temporary_airflow returns False when registers unavailable (lines 2327-2329)."""
    coord = _make_coordinator()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        side_effect=KeyError("cfg_mode_1"),
    ):
        result = await coord.async_write_temporary_airflow(50.0)
    assert result is False


@pytest.mark.asyncio
async def test_async_write_temporary_temperature():
    """async_write_temporary_temperature calls async_write_registers when registers exist."""
    coord = _make_coordinator()
    coord.async_write_registers = AsyncMock(return_value=True)
    mock_def = MagicMock()
    mock_def.encode = MagicMock(return_value=1)
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_temporary_temperature(22.0)
    assert result is True
    coord.async_write_registers.assert_called_once()


@pytest.mark.asyncio
async def test_async_write_temporary_temperature_missing_register():
    """async_write_temporary_temperature returns False when registers unavailable (lines 2352-2354)."""
    coord = _make_coordinator()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        side_effect=KeyError("cfg_mode_2"),
    ):
        result = await coord.async_write_temporary_temperature(22.0)
    assert result is False


# ---------------------------------------------------------------------------
# Group S — _disconnect_locked / _disconnect / async_shutdown (lines 2368-2416)
# ---------------------------------------------------------------------------


def test_process_register_value_schedule_hh_mm():
    """schedule_ register with HH:MM decoded → stored as HH:MM string (not minutes)."""
    from custom_components.thessla_green_modbus.core import register_processing as rp

    coord = _make_coordinator()
    mock_def = MagicMock()
    mock_def.is_temperature.return_value = False
    mock_def.enum = None
    mock_def.decode.return_value = "06:30"
    with patch.object(rp, "get_register_definitions", return_value={"schedule_on_1": mock_def}):
        result = coord.device_client._process_register_value("schedule_on_1", 390)
    assert result == "06:30"


# ---------------------------------------------------------------------------
# Pass 15 — Sekcja D: async_write_register paths (lines 1997-2166)
# ---------------------------------------------------------------------------


def test_process_register_value_schedule_hh_mm_invalid():
    """schedule_ register with bad HH:MM → ValueError caught, decoded unchanged (lines 1850-1851)."""
    from custom_components.thessla_green_modbus.core import register_processing as rp

    coord = _make_coordinator()
    mock_def = MagicMock()
    mock_def.is_temperature.return_value = False
    mock_def.enum = None
    mock_def.decode.return_value = "ab:cd"  # valid format but int() will fail
    with patch.object(rp, "get_register_definitions", return_value={"schedule_on_1": mock_def}):
        result = coord.device_client._process_register_value("schedule_on_1", 999)
    assert result == "ab:cd"  # returned unchanged after ValueError
