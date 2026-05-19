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
        "timeout": coordinator.device_client.timeout,
        "retry": coordinator.device_client.retry,
        "backoff": coordinator.device_client.backoff,
        "backoff_jitter": coordinator.device_client.backoff_jitter,
        "scan_uart_settings": coordinator.device_client.scan_uart_settings,
        "skip_known_missing": coordinator.device_client.skip_missing_registers,
        "deep_scan": coordinator.device_client.deep_scan,
        "max_registers_per_request": coordinator.device_client.effective_batch,
        "safe_scan": coordinator.device_client.safe_scan,
        "connection_type": coordinator.config.connection_type,
        "connection_mode": resolved_connection_mode or coordinator.config.connection_mode,
        "serial_port": coordinator.config.serial_port,
        "baud_rate": coordinator.config.baud_rate,
        "parity": coordinator.config.parity,
        "stop_bits": coordinator.config.stop_bits,
        "hass": coordinator.hass,
    }
