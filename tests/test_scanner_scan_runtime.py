from __future__ import annotations

import logging
from types import SimpleNamespace

from custom_components.thessla_green_modbus.scanner import scan_runtime
from custom_components.thessla_green_modbus.scanner.device_info import (
    DeviceCapabilities,
    ScannerDeviceInfo,
)


def test_log_missing_registers_emits_warning(caplog) -> None:
    missing = {"input_registers": {"temp": 10, "rpm": 3}}

    with caplog.at_level(logging.WARNING):
        scan_runtime.log_missing_registers(missing)

    assert "input_registers: rpm=3, temp=10" in caplog.text


def test_build_scan_result_includes_deep_scan_payload() -> None:
    scanner = SimpleNamespace(
        failed_addresses={
            "modbus_exceptions": {"input_registers": {2}, "holding_registers": set()},
            "invalid_values": {"input_registers": {4}, "holding_registers": set()},
        },
        _resolved_connection_mode="tcp",
        deep_scan=True,
    )
    device = ScannerDeviceInfo()
    caps = DeviceCapabilities()

    result = scan_runtime.build_scan_result(
        scanner,
        device=device,
        caps=caps,
        available_registers={"input_registers": {"a"}, "holding_registers": set()},
        unknown_registers={"input_registers": {0: 7}},
        scanned_registers={"input_registers": 5},
        scan_blocks={"input_registers": [(0, 4)]},
        missing_registers={},
        scan_started=0.0,
        raw_registers={0: 1, 1: 2},
    )

    assert result["failed_addresses"]["modbus_exceptions"]["input_registers"] == [2]
    assert result["failed_addresses"]["invalid_values"]["input_registers"] == [4]
    assert result["resolved_connection_mode"] == "tcp"
    assert result["total_addresses_scanned"] == 2
    assert result["raw_registers"] == {0: 1, 1: 2}
    assert "deep_scan_raw_failures" in result["failed_addresses"]


def test_build_scan_result_includes_deep_scan_raw_failures() -> None:
    """deep_scan_raw_failures from the scanner are included in the result."""
    scanner = SimpleNamespace(
        failed_addresses={
            "modbus_exceptions": {"input_registers": set(), "holding_registers": set()},
            "invalid_values": {"input_registers": set(), "holding_registers": set()},
            "deep_scan_raw_failures": {"input_registers": {22, 23, 24}},
        },
        _resolved_connection_mode="tcp",
        deep_scan=True,
    )
    device = ScannerDeviceInfo()
    caps = DeviceCapabilities()

    result = scan_runtime.build_scan_result(
        scanner,
        device=device,
        caps=caps,
        available_registers={"input_registers": {"a"}, "holding_registers": set()},
        unknown_registers={},
        scanned_registers={"input_registers": 5},
        scan_blocks={"input_registers": [(0, 4)]},
        missing_registers={},
        scan_started=0.0,
        raw_registers={},
    )

    raw_failures = result["failed_addresses"]["deep_scan_raw_failures"]
    assert "input_registers" in raw_failures
    assert sorted(raw_failures["input_registers"]) == [22, 23, 24]
    # modbus_exceptions must remain clean — not contaminated by raw failures
    assert result["failed_addresses"]["modbus_exceptions"] == {}
