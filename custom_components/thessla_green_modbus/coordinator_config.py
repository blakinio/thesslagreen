"""Configuration helpers for coordinator setup."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

from .const import (
    CONF_BACKOFF,
    CONF_BACKOFF_JITTER,
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_DEEP_SCAN,
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_PARITY,
    CONF_RETRY,
    CONF_SAFE_SCAN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_UART_SETTINGS,
    CONF_SERIAL_PORT,
    CONF_SKIP_MISSING_REGISTERS,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONF_TIMEOUT,
    DEFAULT_BACKOFF,
    DEFAULT_BACKOFF_JITTER,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_DEEP_SCAN,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_RETRY,
    DEFAULT_SAFE_SCAN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_SKIP_MISSING_REGISTERS,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOP_BITS,
    DEFAULT_TIMEOUT,
    MIN_SCAN_INTERVAL,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import CoordinatorConfig


def coordinator_config_from_entry(
    entry: ConfigEntry, cls: type[CoordinatorConfig]
) -> CoordinatorConfig:
    """Build coordinator config from a Home Assistant config entry."""
    data = entry.data
    options = entry.options
    return cls(
        host=str(data.get("host", "")),
        port=int(data.get("port", DEFAULT_PORT)),
        slave_id=int(data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)),
        name=str(data.get("name", DEFAULT_NAME)),
        scan_interval=int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        timeout=int(options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
        retry=int(options.get(CONF_RETRY, DEFAULT_RETRY)),
        backoff=float(options.get(CONF_BACKOFF, DEFAULT_BACKOFF)),
        backoff_jitter=options.get(CONF_BACKOFF_JITTER, DEFAULT_BACKOFF_JITTER),
        force_full_register_list=bool(options.get(CONF_FORCE_FULL_REGISTER_LIST, False)),
        scan_uart_settings=bool(options.get(CONF_SCAN_UART_SETTINGS, DEFAULT_SCAN_UART_SETTINGS)),
        deep_scan=bool(options.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN)),
        safe_scan=bool(options.get(CONF_SAFE_SCAN, DEFAULT_SAFE_SCAN)),
        max_registers_per_request=int(
            options.get(CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST)
        ),
        skip_missing_registers=bool(
            options.get(CONF_SKIP_MISSING_REGISTERS, DEFAULT_SKIP_MISSING_REGISTERS)
        ),
        connection_type=str(data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)),
        connection_mode=cast(str | None, data.get(CONF_CONNECTION_MODE)),
        serial_port=str(data.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT)),
        baud_rate=int(data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)),
        parity=str(data.get(CONF_PARITY, DEFAULT_PARITY)),
        stop_bits=int(data.get(CONF_STOP_BITS, DEFAULT_STOP_BITS)),
    )


def normalize_scan_interval(scan_interval: timedelta | int) -> int:
    """Normalize scan interval to integer seconds with lower bound."""
    if isinstance(scan_interval, timedelta):
        interval_seconds = int(scan_interval.total_seconds())
    else:
        interval_seconds = int(scan_interval)
    return max(interval_seconds, MIN_SCAN_INTERVAL)
