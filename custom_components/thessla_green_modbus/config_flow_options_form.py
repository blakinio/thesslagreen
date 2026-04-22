"""Helpers for building options-flow form schema and placeholders."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.const import CONF_PORT

from .const import (
    AIRFLOW_UNIT_M3H,
    AIRFLOW_UNIT_PERCENTAGE,
    CONF_AIRFLOW_UNIT,
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_DEEP_SCAN,
    CONF_ENABLE_DEVICE_SCAN,
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_LOG_LEVEL,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_PARITY,
    CONF_RETRY,
    CONF_SAFE_SCAN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_UART_SETTINGS,
    CONF_SERIAL_PORT,
    CONF_SKIP_MISSING_REGISTERS,
    CONF_STOP_BITS,
    CONF_TIMEOUT,
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    DEFAULT_AIRFLOW_UNIT,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_DEEP_SCAN,
    DEFAULT_ENABLE_DEVICE_SCAN,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_RETRY,
    DEFAULT_SAFE_SCAN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_SKIP_MISSING_REGISTERS,
    DEFAULT_STOP_BITS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_BATCH_REGISTERS,
    MIN_SCAN_INTERVAL,
)
from .utils import resolve_connection_settings


def build_options_defaults(
    entry_data: dict[str, Any],
    entry_options: dict[str, Any],
) -> dict[str, Any]:
    """Build normalized defaults used in options flow forms/placeholders."""
    return {
        CONF_SCAN_INTERVAL: entry_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        CONF_TIMEOUT: entry_options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        CONF_RETRY: entry_options.get(CONF_RETRY, DEFAULT_RETRY),
        CONF_FORCE_FULL_REGISTER_LIST: entry_options.get(CONF_FORCE_FULL_REGISTER_LIST, False),
        CONF_SCAN_UART_SETTINGS: entry_options.get(CONF_SCAN_UART_SETTINGS, DEFAULT_SCAN_UART_SETTINGS),
        CONF_SKIP_MISSING_REGISTERS: entry_options.get(
            CONF_SKIP_MISSING_REGISTERS, DEFAULT_SKIP_MISSING_REGISTERS
        ),
        CONF_ENABLE_DEVICE_SCAN: entry_options.get(CONF_ENABLE_DEVICE_SCAN, DEFAULT_ENABLE_DEVICE_SCAN),
        CONF_AIRFLOW_UNIT: entry_options.get(CONF_AIRFLOW_UNIT, DEFAULT_AIRFLOW_UNIT),
        CONF_DEEP_SCAN: entry_options.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN),
        CONF_MAX_REGISTERS_PER_REQUEST: entry_options.get(
            CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
        ),
        CONF_SAFE_SCAN: entry_options.get(CONF_SAFE_SCAN, DEFAULT_SAFE_SCAN),
        CONF_LOG_LEVEL: entry_options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        CONF_CONNECTION_TYPE: entry_data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE),
        CONF_CONNECTION_MODE: entry_options.get(
            CONF_CONNECTION_MODE, entry_data.get(CONF_CONNECTION_MODE)
        ),
        "entry_port": entry_data.get(CONF_PORT, DEFAULT_PORT),
        "entry_serial_port": entry_data.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT),
        "entry_baud_rate": entry_data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE),
        "entry_parity": entry_data.get(CONF_PARITY, DEFAULT_PARITY),
        "entry_stop_bits": entry_data.get(CONF_STOP_BITS, DEFAULT_STOP_BITS),
    }


def build_transport_description(values: dict[str, Any]) -> tuple[str, str]:
    """Build transport label/details placeholders for options flow description."""
    normalized_type, resolved_mode = resolve_connection_settings(
        values[CONF_CONNECTION_TYPE],
        values[CONF_CONNECTION_MODE],
        values["entry_port"],
    )

    if normalized_type == CONNECTION_TYPE_RTU:
        transport_label = "Modbus RTU"
        transport_details = (
            " ("
            f"port: {values['entry_serial_port'] or 'n/a'}, "
            f"baud: {values['entry_baud_rate']}, "
            f"parity: {values['entry_parity']}, "
            f"stop bits: {values['entry_stop_bits']})"
        )
        return transport_label, transport_details

    if resolved_mode == CONNECTION_MODE_TCP_RTU:
        return "Modbus TCP RTU", ""

    transport_label = "Modbus TCP"
    if resolved_mode == CONNECTION_MODE_AUTO:
        transport_label = "Modbus TCP (Auto)"
    return transport_label, ""


def build_options_schema(values: dict[str, Any]) -> vol.Schema:
    """Build options flow schema from normalized defaults."""
    return vol.Schema(
        {
            vol.Optional(CONF_SCAN_INTERVAL, default=values[CONF_SCAN_INTERVAL]): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=300)
            ),
            vol.Optional(CONF_TIMEOUT, default=values[CONF_TIMEOUT]): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=60)
            ),
            vol.Optional(CONF_RETRY, default=values[CONF_RETRY]): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=5)
            ),
            vol.Optional(
                CONF_FORCE_FULL_REGISTER_LIST,
                default=values[CONF_FORCE_FULL_REGISTER_LIST],
            ): bool,
            vol.Optional(CONF_ENABLE_DEVICE_SCAN, default=values[CONF_ENABLE_DEVICE_SCAN]): bool,
            vol.Optional(
                CONF_LOG_LEVEL,
                default=values[CONF_LOG_LEVEL],
                description={
                    "selector": {
                        "select": {
                            "options": [
                                {"value": level, "label": f"{DOMAIN}.log_level_{level}"}
                                for level in ("debug", "info", "warning", "error")
                            ]
                        }
                    }
                },
            ): vol.In({"debug", "info", "warning", "error"}),
            vol.Optional(CONF_SCAN_UART_SETTINGS, default=values[CONF_SCAN_UART_SETTINGS]): bool,
            vol.Optional(
                CONF_SKIP_MISSING_REGISTERS, default=values[CONF_SKIP_MISSING_REGISTERS]
            ): bool,
            vol.Optional(CONF_SAFE_SCAN, default=values[CONF_SAFE_SCAN], description={"advanced": True}): bool,
            vol.Optional(CONF_AIRFLOW_UNIT, default=values[CONF_AIRFLOW_UNIT]): vol.In(
                [AIRFLOW_UNIT_M3H, AIRFLOW_UNIT_PERCENTAGE]
            ),
            vol.Optional(
                CONF_DEEP_SCAN,
                default=values[CONF_DEEP_SCAN],
                description={"advanced": True},
            ): bool,
            vol.Optional(
                CONF_MAX_REGISTERS_PER_REQUEST,
                default=values[CONF_MAX_REGISTERS_PER_REQUEST],
                description={
                    "advanced": True,
                    "selector": {"number": {"min": 1, "max": MAX_BATCH_REGISTERS, "step": 1}},
                },
            ): int,
        }
    )


def build_options_description_placeholders(
    values: dict[str, Any],
    *,
    transport_label: str,
    transport_details: str,
) -> dict[str, str]:
    """Build placeholder mapping for options step description."""
    return {
        "current_scan_interval": str(values[CONF_SCAN_INTERVAL]),
        "current_timeout": str(values[CONF_TIMEOUT]),
        "current_retry": str(values[CONF_RETRY]),
        "force_full_enabled": "Yes" if values[CONF_FORCE_FULL_REGISTER_LIST] else "No",
        "scan_uart_enabled": "Yes" if values[CONF_SCAN_UART_SETTINGS] else "No",
        "skip_missing_enabled": "Yes" if values[CONF_SKIP_MISSING_REGISTERS] else "No",
        "device_scan_enabled": "Yes" if values[CONF_ENABLE_DEVICE_SCAN] else "No",
        "current_airflow_unit": values[CONF_AIRFLOW_UNIT],
        "deep_scan_enabled": "Yes" if values[CONF_DEEP_SCAN] else "No",
        "current_max_registers_per_request": str(values[CONF_MAX_REGISTERS_PER_REQUEST]),
        "safe_scan_enabled": "Yes" if values[CONF_SAFE_SCAN] else "No",
        "current_log_level": values[CONF_LOG_LEVEL],
        "transport_label": transport_label,
        "transport_details": transport_details,
    }
