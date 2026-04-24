"""Factory helpers for coordinator construction."""

from __future__ import annotations

from datetime import timedelta

from .const import (
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
from .coordinator_models import CoordinatorConfig


def build_config_from_params(
    *,
    host: str,
    port: int,
    slave_id: int,
    name: str = DEFAULT_NAME,
    scan_interval: timedelta | int = DEFAULT_SCAN_INTERVAL,
    timeout: int = 10,
    retry: int = 3,
    backoff: float = DEFAULT_BACKOFF,
    backoff_jitter: float | tuple[float, float] | None = DEFAULT_BACKOFF_JITTER,
    force_full_register_list: bool = False,
    scan_uart_settings: bool = DEFAULT_SCAN_UART_SETTINGS,
    deep_scan: bool = False,
    safe_scan: bool = False,
    max_registers_per_request: int = DEFAULT_MAX_REGISTERS_PER_REQUEST,
    skip_missing_registers: bool = False,
    connection_type: str = DEFAULT_CONNECTION_TYPE,
    connection_mode: str | None = None,
    serial_port: str = DEFAULT_SERIAL_PORT,
    baud_rate: int = DEFAULT_BAUD_RATE,
    parity: str = DEFAULT_PARITY,
    stop_bits: int = DEFAULT_STOP_BITS,
) -> CoordinatorConfig:
    """Build CoordinatorConfig from explicit constructor parameters."""

    return CoordinatorConfig(
        host=host,
        port=port,
        slave_id=slave_id,
        name=name,
        scan_interval=scan_interval,
        timeout=timeout,
        retry=retry,
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        force_full_register_list=force_full_register_list,
        scan_uart_settings=scan_uart_settings,
        deep_scan=deep_scan,
        safe_scan=safe_scan,
        max_registers_per_request=max_registers_per_request,
        skip_missing_registers=skip_missing_registers,
        connection_type=connection_type,
        connection_mode=connection_mode,
        serial_port=serial_port,
        baud_rate=baud_rate,
        parity=parity,
        stop_bits=stop_bits,
    )
