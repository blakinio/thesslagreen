"""Selection/grouping device scanner tests."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP, SENSOR_UNAVAILABLE
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.scanner.core import (
    DeviceCapabilities,
    ThesslaGreenDeviceScanner,
)

INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function(4)}

pytestmark = pytest.mark.asyncio


async def test_scan_excludes_unavailable_temperature():
    """Temperature register with SENSOR_UNAVAILABLE should be included (sensor disconnected, register exists)."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count, **kwargs):
        data = [1] * count
        if address == 0:
            data[0:3] = [4, 85, 0]
        temp_addr = INPUT_REGISTERS["outside_temperature"]
        if address <= temp_addr < address + count:
            data[temp_addr - address] = SENSOR_UNAVAILABLE
        return data

    async def fake_read_holding(client, address, count, **kwargs):
        return [1] * count

    async def fake_read_coil(client, address, count, **kwargs):
        return [False] * count

    async def fake_read_discrete(client, address, count, **kwargs):
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

    assert "outside_temperature" in result["available_registers"]["input_registers"]

async def test_deep_scan_collects_raw_registers():
    """Deep scan returns raw register values."""

    class DummyClient:
        async def connect(self):
            return True

        async def close(self):
            pass

    async def fake_read_input(self, client, address, count, *, skip_cache=False):
        return list(range(address, address + count))

    async def fake_read_holding(self, client, address, count, *, skip_cache=False):
        return [0] * count

    async def fake_read_coil(self, client, address, count):
        return [0] * count

    async def fake_read_discrete(self, client, address, count):
        return [0] * count

    with (
        patch(
            "pymodbus.client.AsyncModbusTcpClient",
            return_value=DummyClient(),
        ),
        patch.object(ThesslaGreenDeviceScanner, "_read_input", fake_read_input),
        patch.object(ThesslaGreenDeviceScanner, "_read_holding", fake_read_holding),
        patch.object(ThesslaGreenDeviceScanner, "_read_coil", fake_read_coil),
        patch.object(ThesslaGreenDeviceScanner, "_read_discrete", fake_read_discrete),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10, deep_scan=True)
        scanner.connection_mode = CONNECTION_MODE_TCP
        result = await scanner.scan_device()

    expected = 300 - 14 + 1
    assert len(result["raw_registers"]) == expected
    assert result["total_addresses_scanned"] == expected

async def test_scan_logs_missing_expected_registers(caplog):
    """Scanner warns when expected registers are not found."""

    input_regs = {
        "version_major": 0,
        "version_minor": 1,
        "version_patch": 2,
        "serial_number": 3,
        "reg_a": 4,
    }

    async def fake_read_input(client, address, count, **kwargs):
        data = [0] * count
        if address <= 4 < address + count:
            data[4 - address] = SENSOR_UNAVAILABLE
        return data

    scanner = ThesslaGreenDeviceScanner("host", 502)
    scanner._input_register_map = input_regs
    scanner._holding_register_map = {}
    scanner._coil_register_map = {}
    scanner._discrete_input_register_map = {}
    scanner._known_missing_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    scanner._update_known_missing_addresses()

    scanner._client = object()
    with (
        patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
        patch.object(scanner, "_is_valid_register_value", side_effect=lambda n, v: n != "reg_a"),
        caplog.at_level(logging.WARNING),
    ):
        await scanner.scan()

    assert "reg_a=4" in caplog.text
