from types import SimpleNamespace

import pytest
from custom_components.thessla_green_modbus.scanner import custom_scan
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.scanner_device_info import (
    DeviceCapabilities,
    ScannerDeviceInfo,
)


def test_uses_custom_scan_impl_detects_bound_override() -> None:
    scanner = SimpleNamespace()

    async def fake_scan() -> dict[str, str]:
        return {"ok": "yes"}

    scanner.scan = fake_scan
    assert custom_scan.uses_custom_scan_impl(scanner) is True


def test_normalize_custom_scan_result_tuple_shape() -> None:
    scanner = SimpleNamespace(
        available_registers={
            "input_registers": {"outside_temperature"},
            "holding_registers": {"mode"},
        }
    )
    device = ScannerDeviceInfo(model="AirPack")
    caps = DeviceCapabilities(basic_control=True)

    result = custom_scan.normalize_custom_scan_result(
        scanner,
        (device, caps, {"input_registers": {10: 1}}),
    )

    assert result["register_count"] == 2
    assert result["capabilities"]["basic_control"] is True


@pytest.mark.asyncio
async def test_run_custom_scan_awaits_coroutine() -> None:
    async def fake_scan() -> dict[str, str]:
        return {"ready": "ok"}

    scanner = SimpleNamespace(scan=fake_scan)
    result = await custom_scan.run_custom_scan(scanner)
    assert result == {"ready": "ok"}


def test_uses_custom_scan_impl_false_for_core_impl() -> None:
    scanner = ThesslaGreenDeviceScanner("127.0.0.1", 502, registers_ready=True)
    assert custom_scan.uses_custom_scan_impl(scanner) is False
