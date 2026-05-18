"""Entry payload helpers for config flow."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from ..const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_DEEP_SCAN,
    CONF_ENABLE_DEVICE_SCAN,
    CONF_LOG_LEVEL,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_DEEP_SCAN,
    DEFAULT_ENABLE_DEVICE_SCAN,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOP_BITS,
)
from ..utils import resolve_connection_settings
from .payloads import caps_to_dict


def build_unique_id(data: dict[str, Any]) -> str:
    """Generate a unique identifier for the config entry."""
    connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    slave_id = data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)

    if connection_type == CONNECTION_TYPE_RTU:
        serial_port = str(data.get(CONF_SERIAL_PORT, ""))
        identifier = serial_port or "serial"
        sanitized = identifier.replace(":", "-").replace("/", "_")
        return f"{connection_type}:{sanitized}:{slave_id}"

    host = str(data.get(CONF_HOST, ""))
    port = data.get(CONF_PORT, DEFAULT_PORT)
    unique_host = host.replace(":", "-") if host else ""
    return f"{unique_host}:{port}:{slave_id}"


def _build_config_flow_scan_cache(
    scan_result: dict[str, Any],
    cap_cls: Any,
) -> dict[str, Any] | None:
    """Build a one-time scan cache dict from a config-flow scan result."""
    available = scan_result.get("available_registers")
    if not isinstance(available, dict) or not available:
        return None

    serialized: dict[str, list[str]] = {}
    for key, value in available.items():
        if isinstance(value, (list, set)):
            serialized[key] = sorted(value)

    if not serialized:
        return None

    device_info = scan_result.get("device_info") or {}
    caps = scan_result.get("capabilities")
    if dataclasses.is_dataclass(caps) or isinstance(caps, cap_cls):
        caps_dict: dict[str, Any] = caps_to_dict(caps)
    elif isinstance(caps, dict):
        caps_dict = dict(caps)
    else:
        caps_dict = {}

    return {
        "available_registers": serialized,
        "device_info": device_info,
        "capabilities": caps_dict,
        "firmware": device_info.get("firmware") if isinstance(device_info, dict) else None,
        "register_count": scan_result.get("register_count", 0),
    }


def prepare_entry_payload(
    data: dict[str, Any],
    scan_result: dict[str, Any],
    cap_cls: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return data and options payloads for the config entry."""
    caps_obj = scan_result.get("capabilities")
    if dataclasses.is_dataclass(caps_obj) or isinstance(caps_obj, cap_cls):
        caps_dict = caps_to_dict(caps_obj)
    elif isinstance(caps_obj, dict):
        try:
            caps_dict = caps_to_dict(cap_cls(**caps_obj))
        except (TypeError, ValueError):
            caps_dict = caps_to_dict(cap_cls())
    else:
        caps_dict = caps_to_dict(cap_cls())

    connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    connection_mode = data.get(CONF_CONNECTION_MODE)
    normalized_type, resolved_mode = resolve_connection_settings(
        connection_type, connection_mode, data.get(CONF_PORT, DEFAULT_PORT)
    )

    entry_data: dict[str, Any] = {
        CONF_CONNECTION_TYPE: normalized_type,
        CONF_SLAVE_ID: data[CONF_SLAVE_ID],
        CONF_NAME: data.get(CONF_NAME, DEFAULT_NAME),
        "capabilities": caps_dict,
    }

    if normalized_type == CONNECTION_TYPE_TCP:
        entry_data[CONF_HOST] = data.get(CONF_HOST, "")
        entry_data[CONF_PORT] = data.get(CONF_PORT, DEFAULT_PORT)
        entry_data[CONF_CONNECTION_MODE] = resolved_mode
    else:
        entry_data[CONF_SERIAL_PORT] = data.get(CONF_SERIAL_PORT, "")
        entry_data[CONF_BAUD_RATE] = data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)
        entry_data[CONF_PARITY] = data.get(CONF_PARITY, DEFAULT_PARITY)
        entry_data[CONF_STOP_BITS] = data.get(CONF_STOP_BITS, DEFAULT_STOP_BITS)
        if CONF_HOST in data:
            entry_data[CONF_HOST] = data.get(CONF_HOST, "")
        if CONF_PORT in data:
            entry_data[CONF_PORT] = data.get(CONF_PORT, DEFAULT_PORT)

    options: dict[str, Any] = {
        CONF_DEEP_SCAN: data.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN),
        CONF_MAX_REGISTERS_PER_REQUEST: data.get(
            CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
        ),
        CONF_ENABLE_DEVICE_SCAN: data.get(CONF_ENABLE_DEVICE_SCAN, DEFAULT_ENABLE_DEVICE_SCAN),
        CONF_LOG_LEVEL: DEFAULT_LOG_LEVEL,
    }

    scan_cache = _build_config_flow_scan_cache(scan_result, cap_cls)
    if scan_cache is not None:
        options["config_flow_scan_cache"] = scan_cache

    return entry_data, options
