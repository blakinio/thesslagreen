"""Shared helpers for service handlers."""

from __future__ import annotations

from typing import Any


def clamp_airflow_rate(coordinator: Any, airflow_rate: int) -> int:
    """Clamp airflow_rate to the coordinator's reported min/max percentages."""
    data = getattr(coordinator, "data", {}) or {}
    min_pct = data.get("min_percentage")
    max_pct = data.get("max_percentage")
    try:
        min_val = int(min_pct) if min_pct is not None else 0
    except (TypeError, ValueError):
        min_val = 0
    try:
        max_val = int(max_pct) if max_pct is not None else 150
    except (TypeError, ValueError):
        max_val = 150
    min_val = max(0, min_val)
    max_val = min(150, max_val)
    if max_val < min_val:
        max_val = min_val
    return max(min_val, min(max_val, int(airflow_rate)))
