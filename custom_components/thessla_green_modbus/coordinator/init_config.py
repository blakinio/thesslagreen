"""Initialization helpers for coordinator."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from ..const import CONNECTION_MODE_AUTO
from .models import CoordinatorConfig


def normalize_runtime_config(
    cfg: CoordinatorConfig,
    *,
    normalize_scan_interval: Callable[[timedelta | int], float],
    resolve_connection_settings: Callable[
        [str | None, str | None, int | None], tuple[str, str | None]
    ],
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


def apply_coordinator_config(
    coordinator: Any,
    normalized_cfg: CoordinatorConfig,
    resolved_connection_mode: str | None,
    entry: Any,
    *,
    normalize_backoff_fn: Callable[[float], float],
    parse_backoff_jitter_fn: Callable[[Any], float | tuple[float, float] | None],
    resolve_effective_batch_fn: Callable[[Any, int], int],
) -> None:
    """Assign normalized config attributes to a fresh coordinator instance."""
    coordinator._device_name = normalized_cfg.name
    coordinator.config = normalized_cfg
    coordinator._resolved_connection_mode = resolved_connection_mode
    coordinator.timeout = normalized_cfg.timeout
    coordinator.retry = normalized_cfg.retry
    coordinator.backoff = normalize_backoff_fn(normalized_cfg.backoff)
    coordinator.backoff_jitter = parse_backoff_jitter_fn(normalized_cfg.backoff_jitter)
    coordinator.force_full_register_list = normalized_cfg.force_full_register_list
    coordinator.scan_uart_settings = normalized_cfg.scan_uart_settings
    coordinator.deep_scan = normalized_cfg.deep_scan
    coordinator.safe_scan = normalized_cfg.safe_scan
    coordinator.entry = entry
    coordinator.skip_missing_registers = normalized_cfg.skip_missing_registers

    effective_batch = resolve_effective_batch_fn(entry, normalized_cfg.max_registers_per_request)
    coordinator.effective_batch = effective_batch
    coordinator.max_registers_per_request = effective_batch
    coordinator.config.max_registers_per_request = effective_batch
    coordinator.config.backoff = coordinator.backoff
    coordinator.config.backoff_jitter = coordinator.backoff_jitter
