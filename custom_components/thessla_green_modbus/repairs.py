"""Repairs support for the ThesslaGreen Modbus integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_WRITE_FAILURE_KEY = "modbus_write_failed"


def write_failure_issue_id(entry: Any | None) -> str:
    """Return an issue id unique to a config entry when available."""
    entry_id = getattr(entry, "entry_id", None)
    return f"{_WRITE_FAILURE_KEY}_{entry_id}" if entry_id else _WRITE_FAILURE_KEY


def create_write_failure_issue(
    hass: HomeAssistant,
    entry: Any | None,
    *,
    register: str | None = None,
) -> None:
    """Create an actionable repair issue after a final Modbus write failure.

    The issue is non-persistent because write connectivity is re-evaluated on
    every operation.  A later successful write clears it automatically.
    """
    data = {"register": register} if register else None
    ir.async_create_issue(
        hass,
        DOMAIN,
        write_failure_issue_id(entry),
        data=data,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=_WRITE_FAILURE_KEY,
    )


def clear_write_failure_issue(hass: HomeAssistant, entry: Any | None) -> None:
    """Clear the write-failure repair issue after a confirmed successful write."""
    ir.async_delete_issue(hass, DOMAIN, write_failure_issue_id(entry))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict | None,
) -> RepairsFlow:
    """Create a compatibility confirmation flow for legacy/future fixable issues.

    The active ``modbus_write_failed`` issue is deliberately non-fixable: the
    remedy is to restore the Modbus connection/permissions, after which the
    integration removes the issue on the next successful write.  Keeping this
    hook preserves compatibility with previously-created fixable issues.
    """
    return ConfirmRepairFlow()
