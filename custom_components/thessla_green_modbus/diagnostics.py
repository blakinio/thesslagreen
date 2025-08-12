"""Diagnostics platform for the ThesslaGreen Modbus integration."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: ThesslaGreenModbusCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]

    # Gather comprehensive diagnostic data from the coordinator
    diagnostics = coordinator.get_diagnostic_data()

    # Redact sensitive information
    diagnostics_safe = _redact_sensitive_data(diagnostics)

    _LOGGER.debug("Generated diagnostics for ThesslaGreen device")

    return diagnostics_safe


def _redact_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive information from diagnostics."""
    # Create a copy to avoid modifying original data
    safe_data = data.copy()

    # Redact sensitive connection information
    if "connection" in safe_data:
        connection = safe_data["connection"].copy()
        # Keep structure but redact actual host
        if "host" in connection:
            host_parts = connection["host"].split(".")
            if len(host_parts) == 4:
                # Redact middle parts of IP: 192.xxx.xxx.17
                connection["host"] = f"{host_parts[0]}.xxx.xxx.{host_parts[3]}"
        safe_data["connection"] = connection

    # Redact serial number if present
    if (
        "device_info" in safe_data
        and "serial_number" in safe_data["device_info"]
    ):
        serial = safe_data["device_info"]["serial_number"]
        if serial and len(serial) > 4:
            # Show only first and last 2 characters
            safe_data["device_info"]["serial_number"] = (
                f"{serial[:2]}***{serial[-2:]}"
            )

    # Keep error logs but redact any IP addresses in messages
    if "recent_errors" in safe_data:
        for error in safe_data["recent_errors"]:
            if "message" in error:
                # Simple IP redaction
                message = error["message"]
                message = re.sub(
                    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
                    "xxx.xxx.xxx.xxx",
                    message,
                )
                error["message"] = message

    return safe_data
