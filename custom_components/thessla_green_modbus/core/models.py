"""Data models for the device-domain layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

from ..const import (
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
)


@dataclass(slots=True)
class CoordinatorConfig:
    """Normalized coordinator configuration payload."""

    host: str
    port: int
    slave_id: int
    name: str = DEFAULT_NAME
    scan_interval: timedelta | int = DEFAULT_SCAN_INTERVAL
    timeout: int = 10
    retry: int = 3
    backoff: float = DEFAULT_BACKOFF
    backoff_jitter: float | tuple[float, float] | None = DEFAULT_BACKOFF_JITTER
    force_full_register_list: bool = False
    scan_uart_settings: bool = DEFAULT_SCAN_UART_SETTINGS
    deep_scan: bool = False
    safe_scan: bool = False
    max_registers_per_request: int = DEFAULT_MAX_REGISTERS_PER_REQUEST
    skip_missing_registers: bool = False
    connection_type: str = DEFAULT_CONNECTION_TYPE
    connection_mode: str | None = None
    serial_port: str = DEFAULT_SERIAL_PORT
    baud_rate: int = DEFAULT_BAUD_RATE
    parity: str = DEFAULT_PARITY
    stop_bits: int = DEFAULT_STOP_BITS

    @classmethod
    def from_entry(cls, entry: ConfigEntry | Any) -> CoordinatorConfig:
        """Build a CoordinatorConfig from a Home Assistant config entry."""
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
            scan_uart_settings=bool(
                options.get(CONF_SCAN_UART_SETTINGS, DEFAULT_SCAN_UART_SETTINGS)
            ),
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
