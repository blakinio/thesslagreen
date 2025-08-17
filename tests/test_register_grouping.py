import pytest

from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.registers import INPUT_REGISTERS


@pytest.mark.asyncio
async def test_group_registers_split_known_missing():
    """Known missing input registers are split into individual groups."""
    scanner = ThesslaGreenDeviceScanner("host", 502)
    missing_addr = INPUT_REGISTERS["compilation_days"]
    addresses = [
        missing_addr - 2,
        missing_addr - 1,
        missing_addr,
        missing_addr + 1,
        missing_addr + 2,
    ]

    groups = scanner._group_registers_for_batch_read(addresses)

    assert groups == [
        (missing_addr - 2, 2),
        (missing_addr, 1),
        (missing_addr + 1, 2),
    ]  # nosec B101
