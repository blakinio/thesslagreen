"""Firmware-focused tests for ThesslaGreen device scanner."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.scanner.device_info import ScannerDeviceInfo
from custom_components.thessla_green_modbus.scanner.firmware import (
    _apply_firmware_version_to_device,
    _probe_missing_version_parts,
    scan_device_identity,
)
from custom_components.thessla_green_modbus.scanner.register_maps import (
    HOLDING_REGISTERS as SCANNER_HOLDING_REGISTERS,
)
from custom_components.thessla_green_modbus.scanner.register_maps import (
    INPUT_REGISTERS as SCANNER_INPUT_REGISTERS,
)
from custom_components.thessla_green_modbus.scanner.register_maps import REGISTER_DEFINITIONS

INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function(4)}

pytestmark = pytest.mark.asyncio


async def test_scan_device_firmware_unavailable(caplog):
    """Missing firmware registers should log warning and report unknown firmware."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(*args, skip_cache=False):
        if len(args) == 2:
            address, count = args
        else:
            _, address, count = args
        if address == 0 and count >= 16:
            return None
        if count == 1 and address in (
            INPUT_REGISTERS["version_major"],
            INPUT_REGISTERS["version_minor"],
            INPUT_REGISTERS["version_patch"],
        ):
            return None
        return [1] * count

    async def fake_read_holding(*args, **kwargs):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [1] * count

    async def fake_read_coil(*args):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [False] * count

    async def fake_read_discrete(*args):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [False] * count

    with patch(
        "custom_components.thessla_green_modbus.transport.tcp.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            caplog.set_level(logging.WARNING)
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    assert result["device_info"]["firmware"] == "Unknown"
    assert result["device_info"]["firmware_available"] is False
    assert "Failed to read firmware version registers" in caplog.text


async def test_scan_device_firmware_bulk_fallback():
    """Bulk firmware read failure should fall back to individual reads."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(*args, skip_cache=False):
        if len(args) == 2:
            address, count = args
        else:
            _, address, count = args
        if address == 0 and count >= 16:
            return None
        if count == 1 and address == INPUT_REGISTERS["version_major"]:
            return [4]
        if count == 1 and address == INPUT_REGISTERS["version_minor"]:
            return [85]
        if count == 1 and address == INPUT_REGISTERS["version_patch"]:
            return [0]
        return [1] * count

    async def fake_read_holding(*args, **kwargs):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [1] * count

    async def fake_read_coil(*args):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [False] * count

    async def fake_read_discrete(*args):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [False] * count

    with patch(
        "custom_components.thessla_green_modbus.transport.tcp.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    assert result["device_info"]["firmware"] == "4.85.0"
    assert result["device_info"]["firmware_available"] is True


async def test_scan_device_firmware_partial_bulk_fallback():
    """Partial firmware bulk read should fall back to individual reads."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(*args, skip_cache=False):
        if len(args) == 2:
            address, count = args
        else:
            _, address, count = args
        if address == 0 and count >= 16:
            return [4, 85]
        if address >= 16:
            return []
        if count == 1 and address == INPUT_REGISTERS["version_patch"]:
            return [0]
        if count == 1 and address == INPUT_REGISTERS["version_major"]:
            return [4]
        if count == 1 and address == INPUT_REGISTERS["version_minor"]:
            return [85]
        return [1] * count

    async def fake_read_holding(*args, **kwargs):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [1] * count

    async def fake_read_coil(*args):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [False] * count

    async def fake_read_discrete(*args):
        if len(args) == 2:
            _, count = args
        else:
            _, _, count = args
        return [False] * count

    with patch(
        "custom_components.thessla_green_modbus.transport.tcp.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    assert result["device_info"]["firmware"] == "4.85.0"


async def test_partial_firmware_without_patch_is_preserved(caplog):
    """An older unit without patch register should expose verified major.minor."""
    device = ScannerDeviceInfo()

    caplog.set_level(logging.DEBUG)
    _apply_firmware_version_to_device(device, 4, 85, None, None)

    assert device.firmware == "4.85"
    assert device.firmware_available is True
    assert "Firmware patch unavailable; using partial version 4.85" in caplog.text
    assert "Failed to read firmware version registers" not in caplog.text


async def test_partial_firmware_keeps_probe_error_as_debug_context(caplog):
    """Expected patch absence should stay usable even when probing reports an error."""
    device = ScannerDeviceInfo()

    caplog.set_level(logging.DEBUG)
    _apply_firmware_version_to_device(device, 4, 85, None, ValueError("unsupported register"))

    assert device.firmware == "4.85"
    assert device.firmware_available is True
    assert "unsupported register" in caplog.text


async def test_missing_major_or_minor_stays_unavailable(caplog):
    """Major/minor loss remains a real identity failure."""
    device = ScannerDeviceInfo()

    caplog.set_level(logging.WARNING)
    _apply_firmware_version_to_device(device, 4, None, 1, ValueError("bad minor"))

    assert device.firmware == "Unknown"
    assert device.firmware_available is False
    assert "Failed to read firmware version registers" in caplog.text
    assert "bad minor" in caplog.text


async def test_probe_missing_version_parts_supports_legacy_read_signature():
    """Probe should retry readers that do not accept the explicit client argument."""
    scanner = AsyncMock()
    scanner._client = object()

    async def legacy_reader(*args, **kwargs):
        if len(args) == 3:
            raise TypeError("legacy signature")
        address, count = args
        assert count == 1
        values = {
            SCANNER_INPUT_REGISTERS["version_major"]: [4],
            SCANNER_INPUT_REGISTERS["version_minor"]: [85],
            SCANNER_INPUT_REGISTERS["version_patch"]: [2],
        }
        return values[address]

    scanner._read_input = AsyncMock(side_effect=legacy_reader)
    result = await _probe_missing_version_parts(scanner, None, None, None, None)

    assert result[:3] == (4, 85, 2)
    assert result[3] is None


async def test_scan_device_identity_parses_serial_and_ascii_name():
    """Identity helper should decode serial words and device-name words."""
    serial_start = SCANNER_INPUT_REGISTERS["serial_number"]
    serial_length = REGISTER_DEFINITIONS["serial_number"].length
    info_regs = [0] * (serial_start + serial_length)
    serial_words = [0x1234 + index for index in range(serial_length)]
    info_regs[serial_start : serial_start + serial_length] = serial_words

    name = b"AirPack Test"
    if len(name) % 2:
        name += b"\x00"
    name_words = [(name[index] << 8) | name[index + 1] for index in range(0, len(name), 2)]
    expected_length = REGISTER_DEFINITIONS["device_name"].length
    name_words.extend([0] * max(0, expected_length - len(name_words)))

    scanner = AsyncMock()
    scanner._read_holding_block = AsyncMock(return_value=name_words[:expected_length])
    device = ScannerDeviceInfo()

    await scan_device_identity(scanner, info_regs, device)

    assert device.serial_number == "".join(f"{word:04X}" for word in serial_words)
    assert device.device_name == "AirPack Test"
    scanner._read_holding_block.assert_awaited_once_with(
        SCANNER_HOLDING_REGISTERS["device_name"], expected_length
    )
