from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
    _utcnow,
)


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


def test_status_overview_no_last_update():
    assert _make_coordinator().status_overview["last_successful_read"] is None


def test_status_overview_with_last_update_and_connected_transport():
    coord = _make_coordinator()
    coord.statistics["last_successful_update"] = _utcnow()
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    assert coord.status_overview["online"] is True


def test_status_overview_counts_all_errors():
    coord = _make_coordinator()
    coord.statistics["failed_reads"] = 2
    coord.statistics["connection_errors"] = 3
    coord.statistics["timeout_errors"] = 1
    assert coord.status_overview["error_count"] == 6


def test_performance_stats_structure():
    stats = _make_coordinator().performance_stats
    assert {"total_reads", "failed_reads", "success_rate", "avg_response_time"}.issubset(stats)


def test_performance_stats_success_rate():
    coord = _make_coordinator()
    coord.statistics["successful_reads"] = 10
    coord.statistics["failed_reads"] = 0
    assert coord.performance_stats["success_rate"] == 100.0


def test_get_diagnostic_data_structure():
    coord = _make_coordinator()
    coord.last_scan = _utcnow()
    coord.statistics["last_successful_update"] = _utcnow()
    data = coord.get_diagnostic_data()
    assert {"connection", "statistics", "performance", "status_overview"}.issubset(data)


def test_get_diagnostic_data_with_raw_registers():
    coord = _make_coordinator()
    coord.device_scan_result = {"raw_registers": {"0": 123}, "total_addresses_scanned": 100}
    assert "raw_registers" in coord.get_diagnostic_data()
