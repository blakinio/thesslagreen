"""Helpers for rendering config-flow confirmation steps."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import translation

from .const import (
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_PORT,
    DOMAIN,
)
from .utils import resolve_connection_settings

_LOGGER = logging.getLogger(__name__)


def _build_capabilities_list(cap_cls: Any, caps_obj: Any, *, caps_to_dict: Any) -> list[str]:
    """Build a list of enabled boolean capabilities from scan data."""
    if dataclasses.is_dataclass(caps_obj) or isinstance(caps_obj, cap_cls):
        try:
            caps_data = cap_cls(**caps_to_dict(caps_obj))
        except (TypeError, ValueError):
            caps_data = cap_cls()
    elif isinstance(caps_obj, dict):
        try:
            caps_data = cap_cls(**caps_obj)
        except TypeError:
            caps_data = cap_cls()
    else:
        caps_data = cap_cls()

    return [
        field.name.replace("_", " ").title()
        for field in dataclasses.fields(cap_cls)
        if field.type in (bool, "bool") and getattr(caps_data, field.name)
    ]


async def _get_translations(hass: HomeAssistant) -> dict[str, str]:
    """Load integration translations for the active language."""
    language = getattr(getattr(hass, "config", None), "language", "en")
    try:
        return await translation.async_get_translations(hass, language, "component", [DOMAIN])
    except (OSError, ValueError, HomeAssistantError) as err:
        _LOGGER.debug("Translation load failed: %s", err)
    except (TypeError, AttributeError, RuntimeError) as err:
        _LOGGER.exception("Unexpected error loading translations: %s", err)
    return {}


def _resolve_transport_labels(
    data: dict[str, Any],
    translations: dict[str, str],
) -> tuple[str, str, str, str, str]:
    """Return host, port, endpoint and transport label for confirmation UI."""
    connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    connection_mode = data.get(CONF_CONNECTION_MODE)
    normalized_type, resolved_mode = resolve_connection_settings(
        connection_type, connection_mode, data.get(CONF_PORT, DEFAULT_PORT)
    )

    if normalized_type == CONNECTION_TYPE_RTU:
        endpoint = data.get(CONF_SERIAL_PORT, "Unknown") or "Unknown"
        host_value = data.get(CONF_HOST, "-")
        port_value = str(data.get(CONF_PORT, DEFAULT_PORT))
        transport_label = translations.get(
            f"component.{DOMAIN}.connection_type_rtu_label", "Modbus RTU"
        )
    elif resolved_mode == CONNECTION_MODE_TCP_RTU:
        host_value = data.get(CONF_HOST, "Unknown")
        port_value = str(data.get(CONF_PORT, DEFAULT_PORT))
        endpoint = f"{host_value}:{port_value}"
        transport_label = translations.get(
            f"component.{DOMAIN}.connection_type_tcp_rtu_label", "Modbus TCP RTU"
        )
    else:
        host_value = data.get(CONF_HOST, "Unknown")
        port_value = str(data.get(CONF_PORT, DEFAULT_PORT))
        endpoint = f"{host_value}:{port_value}"
        transport_label = translations.get(
            f"component.{DOMAIN}.connection_mode_auto_label", "Modbus TCP (Auto)"
        )
        if resolved_mode == CONNECTION_MODE_TCP:
            transport_label = translations.get(
                f"component.{DOMAIN}.connection_type_tcp_label", "Modbus TCP"
            )

    transport = (resolved_mode or normalized_type).upper()
    return host_value, port_value, endpoint, transport_label, transport


async def build_confirmation_placeholders(
    *,
    hass: HomeAssistant,
    data: dict[str, Any],
    device_info: dict[str, Any],
    scan_result: dict[str, Any],
    cap_cls: Any,
    caps_to_dict: Any,
) -> dict[str, str]:
    """Build description placeholders used in confirm and reauth-confirm steps."""
    device_name = device_info.get("device_name", "Unknown")
    firmware_version = device_info.get("firmware", "Unknown")
    serial_number = device_info.get("serial_number", "Unknown")

    available_registers = scan_result.get("available_registers", {})
    register_count = scan_result.get(
        "register_count",
        sum(len(regs) for regs in available_registers.values()),
    )
    scan_success_rate = "100%" if register_count > 0 else "0%"

    capabilities_list = _build_capabilities_list(
        cap_cls,
        scan_result.get("capabilities"),
        caps_to_dict=caps_to_dict,
    )

    translations = await _get_translations(hass)
    key = "auto_detected_note_success" if register_count > 0 else "auto_detected_note_limited"
    auto_detected_note = translations.get(
        f"component.{DOMAIN}.{key}",
        "Auto-detection successful!"
        if register_count > 0
        else "Limited auto-detection - some registers may be missing.",
    )

    host_value, port_value, endpoint, transport_label, transport = _resolve_transport_labels(
        data, translations
    )

    return {
        "host": host_value,
        "port": port_value,
        "endpoint": endpoint,
        "transport_label": transport_label,
        "transport": transport,
        "slave_id": str(data[CONF_SLAVE_ID]),
        "device_name": device_name,
        "firmware_version": firmware_version,
        "serial_number": serial_number,
        "register_count": str(register_count),
        "scan_success_rate": scan_success_rate,
        "capabilities_count": str(len(capabilities_list)),
        "capabilities_list": ", ".join(capabilities_list) if capabilities_list else "None",
        "auto_detected_note": auto_detected_note,
    }
