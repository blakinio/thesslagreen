"""Shared dependency contract for service handler registration helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ServiceHandlerDeps:
    """Dependencies injected by ``services.py`` to keep handlers test-friendly."""

    domain: str
    logger: logging.Logger
    special_function_map: dict[str, int]
    day_to_device_key: dict[str, str]
    air_quality_register_map: dict[str, str]
    iter_target_coordinators: Any
    normalize_option: Any
    clamp_airflow_rate: Any
    write_register: Any
    create_log_level_manager: Any
    dt_now: Any
    scanner_create: Any
