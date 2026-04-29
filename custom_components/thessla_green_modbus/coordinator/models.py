"""Data models used by the Modbus coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry

from ..const import (
    DEFAULT_BACKOFF,
    DEFAULT_BACKOFF_JITTER,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_STOP_BITS,
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
    def from_entry(cls, entry: ConfigEntry) -> CoordinatorConfig:
        """Build coordinator config from a Home Assistant config entry."""
        from ..coordinator_config import coordinator_config_from_entry

        return coordinator_config_from_entry(entry, cls)
