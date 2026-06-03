"""Unit tests for coordinator/config_normalization.py."""

from __future__ import annotations

from datetime import timedelta

from custom_components.thessla_green_modbus.const import MIN_SCAN_INTERVAL
from custom_components.thessla_green_modbus.coordinator.config_normalization import (
    normalize_scan_interval,
)


def test_normalize_timedelta_returns_seconds() -> None:
    assert normalize_scan_interval(timedelta(seconds=30)) == 30


def test_normalize_timedelta_fractional_truncates() -> None:
    assert normalize_scan_interval(timedelta(seconds=30, milliseconds=500)) == 30


def test_normalize_timedelta_below_min_clamped() -> None:
    result = normalize_scan_interval(timedelta(seconds=MIN_SCAN_INTERVAL - 1))
    assert result == MIN_SCAN_INTERVAL


def test_normalize_timedelta_zero_clamped_to_min() -> None:
    assert normalize_scan_interval(timedelta(seconds=0)) == MIN_SCAN_INTERVAL


def test_normalize_int_above_min_passthrough() -> None:
    assert normalize_scan_interval(60) == 60


def test_normalize_int_at_min_boundary() -> None:
    assert normalize_scan_interval(MIN_SCAN_INTERVAL) == MIN_SCAN_INTERVAL


def test_normalize_int_below_min_clamped() -> None:
    result = normalize_scan_interval(MIN_SCAN_INTERVAL - 1)
    assert result == MIN_SCAN_INTERVAL


def test_normalize_int_zero_clamped_to_min() -> None:
    assert normalize_scan_interval(0) == MIN_SCAN_INTERVAL


def test_normalize_float_truncates_to_int() -> None:
    result = normalize_scan_interval(30.9)
    assert result == 30
    assert isinstance(result, int)


def test_normalize_float_below_min_clamped() -> None:
    result = normalize_scan_interval(float(MIN_SCAN_INTERVAL - 1))
    assert result == MIN_SCAN_INTERVAL


def test_normalize_large_value_passthrough() -> None:
    assert normalize_scan_interval(3600) == 3600


def test_normalize_result_is_always_int() -> None:
    result = normalize_scan_interval(timedelta(seconds=60))
    assert isinstance(result, int)
