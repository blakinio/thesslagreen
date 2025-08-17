import pytest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner

pytestmark = pytest.mark.asyncio

async def test_input_range_read_after_block_failure():
    empty_regs = {"04": {}, "03": {}, "01": {}, "02": {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(empty_regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    regs = {f"reg_{addr:04X}": addr for addr in range(0x000E, 0x001E)}
    call_log = []

    async def fake_call_modbus(func, slave_id, address, *, count):
        call_log.append((address, count))
        if address == 0x0000 and count == 5:
            return SimpleNamespace(registers=[4, 85, 0, 0, 0], isError=lambda: False)
        if address == 0x0018 and count == 6:
            return SimpleNamespace(registers=[0] * 6, isError=lambda: False)
        if address == 0x000E and count == 16:
            return None
        if count == 1:
            return SimpleNamespace(registers=[1], isError=lambda: False)
        return None

    async def fake_read_holding(client, address, count):
        return [0]

    async def fake_read_coil(client, address, count):
        return [False]

    async def fake_read_discrete(client, address, count):
        return [False]

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS", regs),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS", {}),
        patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class,
    ):
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with (
            patch(
                "custom_components.thessla_green_modbus.device_scanner._call_modbus",
                side_effect=fake_call_modbus,
            ),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            result = await scanner.scan_device()

    assert set(result["available_registers"]["input_registers"]) == set(regs)
    assert (0x000E, 16) in call_log
    single_addresses = [addr for addr, cnt in call_log if cnt == 1]
    for addr in range(0x000E, 0x001E):
        assert addr in single_addresses
