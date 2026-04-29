"""Initialization helpers for coordinator."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from .const import CONNECTION_MODE_AUTO
from .coordinator.models import CoordinatorConfig


def normalize_runtime_config(
    cfg: CoordinatorConfig,
    *,
    normalize_scan_interval: Callable[[timedelta | int], float],
    resolve_connection_settings: Callable[[str | None, str | None, int | None], tuple[str, str | None]],
    normalize_serial_settings: Callable[[str, int, str, int], tuple[str, int, str, int]],
) -> tuple[CoordinatorConfig, str | None, float]:
    """Return normalized config and precomputed connection mode for runtime."""

    interval_seconds = normalize_scan_interval(cfg.scan_interval)
    resolved_type, resolved_mode = resolve_connection_settings(
        cfg.connection_type,
        cfg.connection_mode,
        cfg.port,
    )
    normalized_serial_port, normalized_baud_rate, parity_norm, normalized_stop_bits = (
        normalize_serial_settings(
            cfg.serial_port,
            cfg.baud_rate,
            cfg.parity,
            cfg.stop_bits,
        )
    )

    normalized_cfg = CoordinatorConfig(
        host=cfg.host,
        port=cfg.port,
        slave_id=cfg.slave_id,
        name=cfg.name,
        scan_interval=cfg.scan_interval,
        timeout=cfg.timeout,
        retry=cfg.retry,
        backoff=cfg.backoff,
        backoff_jitter=cfg.backoff_jitter,
        force_full_register_list=cfg.force_full_register_list,
        scan_uart_settings=cfg.scan_uart_settings,
        deep_scan=cfg.deep_scan,
        safe_scan=cfg.safe_scan,
        max_registers_per_request=cfg.max_registers_per_request,
        skip_missing_registers=cfg.skip_missing_registers,
        connection_type=resolved_type,
        connection_mode=resolved_mode,
        serial_port=normalized_serial_port,
        baud_rate=normalized_baud_rate,
        parity=parity_norm,
        stop_bits=normalized_stop_bits,
    )
    resolved_connection_mode = resolved_mode if resolved_mode != CONNECTION_MODE_AUTO else None
    return normalized_cfg, resolved_connection_mode, interval_seconds
