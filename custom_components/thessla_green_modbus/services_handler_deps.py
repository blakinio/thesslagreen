"""Shared dependency contract for service handler registration helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .protocols import (
    ClampAirflowRate,
    CreateLogLevelManager,
    DateTimeNow,
    IterTargetCoordinators,
    NormalizeOption,
    ScannerFactory,
    WriteRegister,
)


@dataclass(slots=True)
class ServiceHandlerDeps:
    """Dependencies injected by ``services.py`` to keep handlers test-friendly."""

    domain: str
    logger: logging.Logger
    special_function_map: dict[str, int]
    day_to_device_key: dict[str, str]
    air_quality_register_map: dict[str, str]
    iter_target_coordinators: IterTargetCoordinators
    normalize_option: NormalizeOption
    clamp_airflow_rate: ClampAirflowRate
    write_register: WriteRegister
    create_log_level_manager: CreateLogLevelManager
    dt_now: DateTimeNow
    scanner_create: ScannerFactory
