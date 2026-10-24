from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

FILTER_WEAR_REGISTERS = {
    "cfgszf_fn_new": 4482,
    "cfgszf_fw_new": 4483,
    "filter_supply_date_limit_get": 4660,
    "filter_exhaust_date_limit_get": 4662,
}

pytestmark = pytest.mark.asyncio


def _start_count(args: tuple) -> tuple[int, int]:
    numbers = [arg for arg in args if isinstance(arg, int) and not isinstance(arg, bool)]
    return numbers[-2], numbers[-1]


class _FakeDevice:
    def __init__(self, firmware: tuple[int, int, int] | None) -> None:
        self._firmware = firmware
        self.holding_reads: set[int] = set()

    async def read_input_block(self, *args):
        start, count = _start_count(args)
        if self._firmware is None:
            return None
        block = [1] * (start + count)
        block[0], block[1], block[4] = self._firmware
        return block[start : start + count]

    async def read_input(self, *args, **kwargs):
        start, count = _start_count(args)
        if self._firmware is None and start <= 4:
            return None
        return [1] * count

    async def read_holding(self, *args, **kwargs):
        start, count = _start_count(args)
        self.holding_reads.update(range(start, start + count))
        return [1] * count

    async def read_bits(self, *args, **kwargs):
        _start, count = _start_count(args)
        return [False] * count


async def _scan(firmware: tuple[int, int, int] | None) -> tuple[dict, set[int]]:
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)
    scanner._client = AsyncMock()
    device = _FakeDevice(firmware)
    with (
        patch.object(scanner, "_read_input_block", AsyncMock(side_effect=device.read_input_block)),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(side_effect=device.read_input)),
        patch.object(scanner, "_read_holding", AsyncMock(side_effect=device.read_holding)),
        patch.object(scanner, "_read_coil", AsyncMock(side_effect=device.read_bits)),
        patch.object(scanner, "_read_discrete", AsyncMock(side_effect=device.read_bits)),
        patch.object(scanner, "_is_valid_register_value", return_value=True),
    ):
        result = await scanner.scan()
    return result, device.holding_reads


async def test_firmware_4_84_scans_filter_wear_registers():
    result, holding_reads = await _scan((4, 84, 2))

    assert result["device_info"]["firmware"] == "4.84.2"
    assert set(FILTER_WEAR_REGISTERS) <= set(result["available_registers"]["holding_registers"])
    assert set(FILTER_WEAR_REGISTERS.values()) <= holding_reads


@pytest.mark.parametrize(
    ("firmware", "reported"),
    [((3, 11, 0), "3.11.0"), ((4, 74, 9), "4.74.9")],
)
async def test_firmware_below_4_75_skips_filter_wear_registers(firmware, reported):
    result, holding_reads = await _scan(firmware)

    assert result["device_info"]["firmware"] == reported
    assert not set(FILTER_WEAR_REGISTERS) & set(result["available_registers"]["holding_registers"])
    assert not set(FILTER_WEAR_REGISTERS.values()) & holding_reads


async def test_unreadable_firmware_skips_filter_wear_registers():
    result, holding_reads = await _scan(None)

    assert result["device_info"]["firmware_available"] is False
    assert not set(FILTER_WEAR_REGISTERS) & set(result["available_registers"]["holding_registers"])
    assert not set(FILTER_WEAR_REGISTERS.values()) & holding_reads
