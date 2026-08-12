# mypy: ignore-errors
"""Exercise remaining scanner firmware parse, probe, and identity fallbacks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.scanner import firmware
from custom_components.thessla_green_modbus.scanner.device_info import ScannerDeviceInfo


def test_parse_version_unexpected_access_error_is_recorded() -> None:
    class BadList(list):
        def __getitem__(self, index):
            raise RuntimeError("bad value")

    major, minor, patch_value, err = firmware._parse_version_from_info_regs(BadList([1] * 10))
    assert major is None
    assert minor is None
    assert patch_value is None
    assert isinstance(err, RuntimeError)


@pytest.mark.asyncio
async def test_probe_missing_version_parts_client_and_signature_fallbacks() -> None:
    scanner = SimpleNamespace(
        _client=object(),
        _read_input=AsyncMock(side_effect=[TypeError("old signature"), [4], [85], []]),
    )
    major, minor, patch_value, err = await firmware._probe_missing_version_parts(
        scanner, None, None, None, None
    )
    assert major == 4
    assert minor == 85
    assert patch_value is None
    assert err is None


@pytest.mark.asyncio
async def test_probe_missing_version_parts_expected_and_unexpected_errors() -> None:
    scanner = SimpleNamespace(
        _client=None,
        _read_input=AsyncMock(side_effect=[ValueError("bad"), RuntimeError("boom"), [3]]),
    )
    _major, _minor, patch_value, err = await firmware._probe_missing_version_parts(
        scanner, None, None, None, None
    )
    assert patch_value == 3
    assert isinstance(err, RuntimeError)


def test_apply_firmware_version_full_partial_and_unavailable() -> None:
    device = ScannerDeviceInfo()
    firmware._apply_firmware_version_to_device(device, 4, 85, 2, None)
    assert device.firmware == "4.85.2"
    assert device.firmware_available is True

    device = ScannerDeviceInfo()
    firmware._apply_firmware_version_to_device(device, 3, 11, None, ValueError("patch read"))
    assert device.firmware == "3.11"
    assert device.firmware_available is True

    device = ScannerDeviceInfo()
    firmware._apply_firmware_version_to_device(device, None, 11, None, ValueError("major read"))
    assert device.firmware_available is False


@pytest.mark.asyncio
async def test_scan_firmware_info_probes_only_when_parts_missing() -> None:
    device = ScannerDeviceInfo()
    with (
        patch.object(firmware, "_parse_version_from_info_regs", return_value=(4, 85, 2, None)),
        patch.object(firmware, "_probe_missing_version_parts", new=AsyncMock()) as probe,
    ):
        await firmware.scan_firmware_info(SimpleNamespace(), [], device)
    probe.assert_not_awaited()
    assert device.firmware == "4.85.2"

    device = ScannerDeviceInfo()
    with (
        patch.object(firmware, "_parse_version_from_info_regs", return_value=(4, 85, None, None)),
        patch.object(
            firmware,
            "_probe_missing_version_parts",
            new=AsyncMock(return_value=(4, 85, None, None)),
        ) as probe,
    ):
        await firmware.scan_firmware_info(SimpleNamespace(), [], device)
    probe.assert_awaited_once()
    assert device.firmware == "4.85"


@pytest.mark.asyncio
async def test_scan_device_identity_serial_and_device_name_success() -> None:
    device = ScannerDeviceInfo()
    scanner = SimpleNamespace(_read_holding_block=AsyncMock(return_value=[0x4142, 0x4300]))
    info = [0] * 64
    start = firmware.INPUT_REGISTERS["serial_number"]
    length = firmware.REGISTER_DEFINITIONS["serial_number"].length
    for offset in range(length):
        info[start + offset] = offset + 1

    await firmware.scan_device_identity(scanner, info, device)
    assert device.serial_number.startswith("0001")
    assert device.device_name == "ABC"


@pytest.mark.asyncio
async def test_scan_device_identity_expected_and_unexpected_error_paths() -> None:
    device = ScannerDeviceInfo()
    scanner = SimpleNamespace(_read_holding_block=AsyncMock(side_effect=RuntimeError("name")))
    with patch.object(
        firmware, "INPUT_REGISTERS", {**firmware.INPUT_REGISTERS, "serial_number": "bad"}
    ):
        await firmware.scan_device_identity(scanner, [], device)
    assert device.serial_number == "Unknown"

    device = ScannerDeviceInfo()
    scanner = SimpleNamespace(_read_holding_block=AsyncMock(return_value=[object()]))
    await firmware.scan_device_identity(scanner, [0] * 64, device)
    assert device.device_name == "Unknown"
