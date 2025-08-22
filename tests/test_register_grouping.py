from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.registers import get_registers_by_function
from custom_components.thessla_green_modbus.registers.loader import Register, group_reads

INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function("04")}


def test_group_registers_split_known_missing():
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


def test_group_reads_from_json():
    """Group consecutive registers based on JSON definitions."""
    plans = [p for p in group_reads(max_block_size=64) if p.function == "04"]
    assert (plans[0].address, plans[0].length) == (0, 5)
    assert (plans[1].address, plans[1].length) == (14, 9)
    assert (plans[2].address, plans[2].length) == (24, 6)


def test_group_reads_splits_large_block(monkeypatch):
    """A long list of consecutive addresses is split into multiple blocks."""

    regs = [Register(function="04", address=i, name=f"r{i}", access="ro") for i in range(100)]

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._load_registers",
        lambda: regs,
    )

    plans = [p for p in group_reads(max_block_size=16) if p.function == "04"]

    assert [(p.address, p.length) for p in plans] == [
        (0, 16),
        (16, 16),
        (32, 16),
        (48, 16),
        (64, 16),
        (80, 16),
        (96, 4),
    ]
