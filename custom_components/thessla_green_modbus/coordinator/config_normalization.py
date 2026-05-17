"""Configuration helpers for coordinator setup."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from ..const import MIN_SCAN_INTERVAL
from ..core.models import CoordinatorConfig

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


def coordinator_config_from_entry(
    entry: ConfigEntry, cls: type[CoordinatorConfig]
) -> CoordinatorConfig:
    """Build coordinator config from a Home Assistant config entry."""
    return CoordinatorConfig.from_entry(entry)


def normalize_scan_interval(scan_interval: timedelta | int) -> int:
    """Normalize scan interval to integer seconds with lower bound."""
    if isinstance(scan_interval, timedelta):
        interval_seconds = int(scan_interval.total_seconds())
    else:
        interval_seconds = int(scan_interval)
    return max(interval_seconds, MIN_SCAN_INTERVAL)
