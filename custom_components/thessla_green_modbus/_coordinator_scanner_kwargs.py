"""Helpers for preparing coordinator scanner factory kwargs."""

from __future__ import annotations

from typing import Any


def build_scanner_kwargs(
    coordinator: Any,
    *,
    resolved_connection_mode: str | None,
) -> dict[str, Any]:
    """Return constructor kwargs shared by all scanner creation paths."""

    return {
        "host": coordinator.config.host,
        "port": coordinator.config.port,
        "slave_id": coordinator.config.slave_id,
        "timeout": coordinator.timeout,
        "retry": coordinator.retry,
        "backoff": coordinator.backoff,
        "backoff_jitter": coordinator.backoff_jitter,
        "scan_uart_settings": coordinator.scan_uart_settings,
        "skip_known_missing": coordinator.skip_missing_registers,
        "deep_scan": coordinator.deep_scan,
        "max_registers_per_request": coordinator.effective_batch,
        "safe_scan": coordinator.safe_scan,
        "connection_type": coordinator.config.connection_type,
        "connection_mode": resolved_connection_mode or coordinator.config.connection_mode,
        "serial_port": coordinator.config.serial_port,
        "baud_rate": coordinator.config.baud_rate,
        "parity": coordinator.config.parity,
        "stop_bits": coordinator.config.stop_bits,
        "hass": coordinator.hass,
    }
