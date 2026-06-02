"""Configuration helpers for coordinator setup."""

from __future__ import annotations

from datetime import timedelta

from ..const import MIN_SCAN_INTERVAL


def normalize_scan_interval(scan_interval: timedelta | int) -> int:
    """Normalize scan interval to integer seconds with lower bound."""
    if isinstance(scan_interval, timedelta):
        interval_seconds = int(scan_interval.total_seconds())
    else:
        interval_seconds = int(scan_interval)
    return max(interval_seconds, MIN_SCAN_INTERVAL)
