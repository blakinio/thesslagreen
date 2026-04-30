"""Tests for coordinator update-cycle result shaping helper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from custom_components.thessla_green_modbus.coordinator.update_result import apply_success_result


def test_apply_success_result_updates_coordinator_state() -> None:
    """Successful result shaping should update counters, status and average latency."""
    now = datetime(2026, 4, 30, 12, 0, 5, tzinfo=UTC)
    start_time = now - timedelta(seconds=5)
    coordinator = SimpleNamespace(
        statistics={
            "successful_reads": 1,
            "last_successful_update": None,
            "average_response_time": 2.0,
        },
        _consecutive_failures=4,
        offline_state=True,
    )

    import custom_components.thessla_green_modbus.coordinator.update_result as update_result_module

    update_result_module._utcnow = lambda: now
    data = {"outside_temperature": 215}

    result = apply_success_result(coordinator, start_time=start_time, data=data)

    assert result == data
    assert coordinator.statistics["successful_reads"] == 2
    assert coordinator.statistics["last_successful_update"] == now
    assert coordinator._consecutive_failures == 0
    assert coordinator.offline_state is False
    assert coordinator.statistics["average_response_time"] == 3.5
