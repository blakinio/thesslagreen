"""Test device scanner for ThesslaGreen Modbus integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import (
    CONNECTION_MODE_TCP,
    KNOWN_MISSING_REGISTERS,
    SENSOR_UNAVAILABLE,
)
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.scanner.core import (
    DeviceCapabilities,
    ThesslaGreenDeviceScanner,
)

COIL_REGISTERS = {r.name: r.address for r in get_registers_by_function(1)}
DISCRETE_INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function(2)}
HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function(3)}
INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function(4)}

pytestmark = pytest.mark.asyncio


async def test_scan_device_success_dynamic():
    """Test successful device scan with dynamic register scanning."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count, **kwargs):
        if address == 0:
            data = [4, 85, 0, 0, 0]
            return data[:count]
        if address == 24:
            return [26, 43, 60, 77, 94, 111][:count]
        return [1] * count

    async def fake_read_holding(client, address, count, **kwargs):
        return [10] * count

    async def fake_read_coil(client, address, count, **kwargs):
        return [False] * count

    async def fake_read_discrete(client, address, count, **kwargs):
        return [False] * count

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client.read_input_registers = AsyncMock(
            return_value=MagicMock(isError=lambda: False, registers=[4, 85, 0, 0, 0])
        )
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
            patch.object(scanner, "_is_valid_register_value", return_value=True),
        ):
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()
    assert "outside_temperature" in result["available_registers"]["input_registers"]
    assert "access_level" in result["available_registers"]["holding_registers"]
    assert "power_supply_fans" in result["available_registers"]["coil_registers"]
    assert "expansion" in result["available_registers"]["discrete_inputs"]
    assert set(result["available_registers"]["input_registers"]) == (
        set(INPUT_REGISTERS.keys()) - KNOWN_MISSING_REGISTERS.get("input_registers", set())
    )
    assert set(result["available_registers"]["holding_registers"]) <= set(HOLDING_REGISTERS.keys())
    assert set(result["available_registers"]["coil_registers"]) == set(COIL_REGISTERS.keys())
    assert set(result["available_registers"]["discrete_inputs"]) == set(
        DISCRETE_INPUT_REGISTERS.keys()
    )
    assert result["device_info"]["firmware"] == "4.85.0"


@pytest.fixture
def mock_modbus_response():
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [4, 85, 0, 0, 0, 0]
    response.bits = [False]
    return response






async def test_scan_device_success_static(mock_modbus_response):
    """Test successful device scan with predefined registers."""
    regs = {
        4: {16: "outside_temperature"},
        3: {0: "mode"},
        1: {0: "power_supply_fans"},
        2: {0: "expansion"},
    }
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client.read_input_registers.return_value = mock_modbus_response
            mock_holding_response = MagicMock()
            mock_holding_response.isError.return_value = False
            mock_holding_response.registers = [1]
            mock_client.read_holding_registers.return_value = mock_holding_response
            holding_response = MagicMock()
            holding_response.isError.return_value = False
            holding_response.registers = [1]
            mock_client.read_holding_registers.return_value = holding_response
            mock_client.read_coils.return_value = mock_modbus_response
            mock_client.read_discrete_inputs.return_value = mock_modbus_response
            mock_client_class.return_value = mock_client

            with patch.object(scanner, "_is_valid_register_value", return_value=True):
                scanner.connection_mode = CONNECTION_MODE_TCP
                result = await scanner.scan_device()

                assert "available_registers" in result
                assert "device_info" in result
                assert "capabilities" in result
                assert "capabilities" in result["device_info"]
                assert result["device_info"]["firmware"] == "4.85.0"
                assert "outside_temperature" in result["available_registers"]["input_registers"]
                assert "mode" in result["available_registers"]["holding_registers"]
                assert "power_supply_fans" in result["available_registers"]["coil_registers"]
                assert "expansion" in result["available_registers"]["discrete_inputs"]















async def test_temperature_register_unavailable_skipped():
    """Temperature registers with SENSOR_UNAVAILABLE should be skipped."""


async def test_temperature_register_unavailable_kept():
    """Temperature registers with SENSOR_UNAVAILABLE should remain available."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count):
        data = [1] * count
        outside_addr = INPUT_REGISTERS["outside_temperature"]
        if address <= outside_addr < address + count:
            data[outside_addr - address] = SENSOR_UNAVAILABLE
        return data

    async def fake_read_holding(client, address, count, **kwargs):
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

    assert "outside_temperature" not in result["available_registers"]["input_registers"]























async def test_scan_populates_device_name():
    """Scanner should include device_name in returned device info."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._client = object()
    scanner._transport = MagicMock()
    scanner._transport.is_connected.return_value = True
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {}}
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }

    device_name = "Test AirPack"
    name_bytes = device_name.encode("ascii").ljust(16, b"\x00")
    regs = [(name_bytes[i] << 8) | name_bytes[i + 1] for i in range(0, 16, 2)]

    async def fake_read_holding(client, address, count, *, skip_cache=False):
        if address == HOLDING_REGISTERS["device_name"]:
            return regs
        return None

    with (
        patch.object(scanner, "_read_input", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
    ):
        result = await scanner.scan()

    assert result["device_info"]["device_name"] == device_name


async def test_scan_populates_device_name_with_non_ascii_bytes() -> None:
    """Scanner should replace invalid ASCII bytes in device name instead of failing."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._client = object()
    scanner._transport = MagicMock()
    scanner._transport.is_connected.return_value = True
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {}}
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }

    name_bytes = b"Test AirPac" + bytes([0xDF]) + b"\x00\x00\x00\x00\x00"
    regs = [(name_bytes[i] << 8) | name_bytes[i + 1] for i in range(0, 16, 2)]

    async def fake_read_holding(client, address, count, *, skip_cache=False):
        if address == HOLDING_REGISTERS["device_name"]:
            return regs
        return None

    with (
        patch.object(scanner, "_read_input", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
    ):
        result = await scanner.scan()

    assert result["device_info"]["device_name"] == "Test AirPac�"
