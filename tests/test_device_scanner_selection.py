"""Device scanner register/selection tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP
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

async def test_scan_blocks_propagated():
    """Ensure scan_device returns discovered register blocks."""
    # Avoid scanning full register set for test speed
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(empty_regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

        async def fake_read_input(client, address, count):
            return [1] * count

        async def fake_read_holding(client, address, count, **kwargs):
            return [1] * count

        async def fake_read_coil(client, address, count):
            return [False] * count

        async def fake_read_discrete(client, address, count):
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
            ):
                scanner.connection_mode = CONNECTION_MODE_TCP
                result = await scanner.scan_device()

    expected_blocks = {
        "input_registers": (
            min(INPUT_REGISTERS.values()),
            max(INPUT_REGISTERS.values()),
        ),
        "holding_registers": (
            min(HOLDING_REGISTERS.values()),
            max(HOLDING_REGISTERS.values()),
        ),
        "coil_registers": (
            min(COIL_REGISTERS.values()),
            max(COIL_REGISTERS.values()),
        ),
        "discrete_inputs": (
            min(DISCRETE_INPUT_REGISTERS.values()),
            max(DISCRETE_INPUT_REGISTERS.values()),
        ),
    }

    assert result["scan_blocks"] == expected_blocks


async def test_full_register_scan_collects_unknown_registers():
    """Ensure full register scan returns unknown registers and statistics."""
    reg_map = {4: {0: "ir0", 2: "ir2"}, 3: {0: "hr0", 2: "hr2"}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(reg_map, {}, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create(
            "192.168.1.1", 502, 10, full_register_scan=True
        )

        async def fake_read_input(client, address, count, **kwargs):
            return [address]

        async def fake_read_holding(client, address, count, **kwargs):
            return [address + 10]

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client.read_input_registers = AsyncMock(
                return_value=MagicMock(isError=lambda: False, registers=[0])
            )
            mock_client_class.return_value = mock_client

            with (
                patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
                patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
                patch.object(scanner, "_read_coil", AsyncMock(return_value=[False])),
                patch.object(scanner, "_read_discrete", AsyncMock(return_value=[False])),
                patch.object(scanner, "_is_valid_register_value", return_value=True),
            ):
                scanner.connection_mode = CONNECTION_MODE_TCP
                result = await scanner.scan_device()

    assert result["unknown_registers"]["input_registers"] == {1: 1}
    assert result["unknown_registers"]["holding_registers"] == {1: 11}
    assert result["scanned_registers"]["input_registers"] == 3
    assert result["scanned_registers"]["holding_registers"] == 3


async def test_scan_device_batch_fallback():
    """Batch read failures should fall back to single-register reads."""
    empty_regs = {4: {}, 3: {}, 1: {}, 2: {}}
    with patch.object(
        ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count, **kwargs):
        if address == 0 and count == 5:
            return [4, 85, 0, 0, 0]
        if count > 1:
            return None
        return [0]

    async def fake_read_holding(client, address, count, **kwargs):
        if count > 1:
            return None
        return [0]

    async def fake_read_coil(client, address, count, **kwargs):
        if count > 1:
            return None
        return [False]

    async def fake_read_discrete(client, address, count, **kwargs):
        if count > 1:
            return None
        return [False]

    scanner._input_register_map = {"ir1": 16, "ir2": 17}
    scanner._holding_register_map = {"hr1": 32, "hr2": 33}
    scanner._coil_register_map = {"cr1": 0, "cr2": 1}
    scanner._discrete_input_register_map = {"dr1": 0, "dr2": 1}
    scanner._known_missing_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    scanner._update_known_missing_addresses()

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client.read_input_registers = AsyncMock(
            return_value=MagicMock(isError=lambda: False, registers=[4, 85, 0, 0, 0])
        )
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)) as ri,
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            scanner.connection_mode = CONNECTION_MODE_TCP
            result = await scanner.scan_device()

    assert set(result["available_registers"]["input_registers"]) == {"ir1", "ir2"}
    assert set(result["available_registers"]["holding_registers"]) == {"hr1", "hr2"}
    assert set(result["available_registers"]["coil_registers"]) == {"cr1", "cr2"}
    assert set(result["available_registers"]["discrete_inputs"]) == {"dr1", "dr2"}

    # Ensure batch read was attempted and individual fallback reads occurred
    batch_calls = [call for call in ri.await_args_list if call.args[1] == 16]
    assert any(call.args[2] == 2 for call in batch_calls)

    single_calls = [call.args[1] for call in ri.await_args_list if call.args[2] == 1]
    assert single_calls.count(16) == 1
    assert single_calls.count(17) == 1


async def test_scan_falls_back_to_single_input_reads_after_failed_batch():
    """Input addresses should be recovered via single-register probes after batch failure."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._client = object()
    scanner._transport = MagicMock()
    scanner._transport.is_connected.return_value = True

    async def fake_read_input(address, count, *, skip_cache=False):
        if skip_cache and count == 1:
            values = {
                0: 3,
                1: 0,
                4: 11,
                16: 215,
                17: 220,
            }
            value = values.get(address)
            return [value] if value is not None else None
        if (address, count) == (16, 2):
            return None
        if (address, count) == (0, 2):
            return [3, 0]
        if (address, count) == (4, 1):
            return [11]
        return []

    with (
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.INPUT_REGISTERS",
            {
                "version_major": 0,
                "version_minor": 1,
                "version_patch": 4,
                "outside_temperature": 16,
                "supply_temperature": 17,
            },
            clear=True,
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.HOLDING_REGISTERS",
            {},
            clear=True,
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.COIL_REGISTERS",
            {},
            clear=True,
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.DISCRETE_INPUT_REGISTERS",
            {},
            clear=True,
        ),
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=[])),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
    ):
        result = await scanner.scan()

    assert "outside_temperature" in result["available_registers"]["input_registers"]
    assert "supply_temperature" in result["available_registers"]["input_registers"]


