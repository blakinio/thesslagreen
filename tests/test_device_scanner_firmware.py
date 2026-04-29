"""Firmware-focused tests for ThesslaGreen device scanner."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function(4)}

pytestmark = pytest.mark.asyncio


async def test_scan_device_firmware_unavailable(caplog):
    """Missing firmware registers should log info and report unknown firmware."""
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

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
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

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
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

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
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
