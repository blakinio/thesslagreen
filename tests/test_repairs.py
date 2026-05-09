"""Tests for the repairs platform (async_create_fix_flow)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from custom_components.thessla_green_modbus.repairs import async_create_fix_flow
from homeassistant.components.repairs import ConfirmRepairFlow


@pytest.mark.asyncio
async def test_async_create_fix_flow_returns_confirm_repair_flow() -> None:
    """async_create_fix_flow must return a ConfirmRepairFlow for any issue_id."""
    hass = MagicMock()
    result = await async_create_fix_flow(hass, "modbus_write_failed", None)
    assert isinstance(result, ConfirmRepairFlow)


@pytest.mark.asyncio
async def test_async_create_fix_flow_unknown_issue_id() -> None:
    """Unknown issue_ids are handled gracefully by the catch-all ConfirmRepairFlow."""
    hass = MagicMock()
    result = await async_create_fix_flow(hass, "some_unknown_issue", {"key": "value"})
    assert isinstance(result, ConfirmRepairFlow)


@pytest.mark.asyncio
async def test_async_create_fix_flow_none_data() -> None:
    """None data is valid — the function must not raise."""
    hass = MagicMock()
    result = await async_create_fix_flow(hass, "modbus_write_failed", None)
    assert result is not None


@pytest.mark.asyncio
async def test_async_create_fix_flow_with_data_dict() -> None:
    """Non-None data dict is accepted without raising."""
    hass = MagicMock()
    result = await async_create_fix_flow(
        hass, "modbus_write_failed", {"register": "mode", "value": 1}
    )
    assert isinstance(result, ConfirmRepairFlow)
