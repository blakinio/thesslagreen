"""Repairs platform for the ThesslaGreen Modbus integration."""

from __future__ import annotations

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict | None,
) -> RepairsFlow:
    """Create a repair fix flow for the given issue.

    Currently all issues (e.g. modbus_write_failed) are handled by a simple
    confirmation flow: the user acknowledges the issue and is directed to check
    the Modbus connection.  When the underlying condition resolves, HA will
    clear the issue automatically on the next successful operation.
    """
    return ConfirmRepairFlow()
