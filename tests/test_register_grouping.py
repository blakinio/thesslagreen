from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.modbus_helpers import group_reads
from custom_components.thessla_green_modbus.registers.loader import (
    Register,
    get_registers_by_function,
    plan_group_reads,
)
from custom_components.thessla_green_modbus.const import MAX_BATCH_REGISTERS

INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function("04")}


def _expanded_addresses(fn: str) -> list[int]:
    plans = [p for p in plan_group_reads(max_block_size=32) if p.function == fn]
    return [addr for plan in plans for addr in range(plan.address, plan.address + plan.length)]


def test_plan_group_reads_coalesces_per_function() -> None:
    """plan_group_reads covers all registers for each function code."""

    for fn in ("01", "02", "03", "04"):
        regs = get_registers_by_function(fn)
        expected = sorted({addr for r in regs for addr in range(r.address, r.address + r.length)})
        assert _expanded_addresses(fn) == expected


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


def test_plan_group_reads_from_json():
    """Group consecutive registers based on JSON definitions."""
    regs = get_registers_by_function("04")
    addresses: list[int] = []
    for reg in regs:
        addresses.extend(range(reg.address, reg.address + reg.length))
    expected = group_reads(addresses, max_block_size=64)
    plans = [p for p in plan_group_reads(max_block_size=64) if p.function == "04"]
    assert [(p.address, p.length) for p in plans] == expected


def test_plan_group_reads_splits_large_block(monkeypatch):
    """A long list of consecutive addresses is split into multiple blocks."""

    regs = [Register(function="04", address=i, name=f"r{i}", access="ro") for i in range(100)]

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader.load_registers",
        lambda: regs,
    )

    addresses = [r.address for r in regs]
    expected = group_reads(addresses, max_block_size=MAX_BATCH_REGISTERS)
    plans = [
        p
        for p in plan_group_reads(max_block_size=MAX_BATCH_REGISTERS)
        if p.function == "04"
    ]

    assert [(p.address, p.length) for p in plans] == expected


def test_plan_group_reads_handles_gaps_and_block_size(monkeypatch):
    """Gaps and block size limits both trigger new read plans."""

    # Two ranges of consecutive registers separated by a gap
    first = list(range(32))
    second = list(range(40, 80))
    regs = [
        Register(function="04", address=i, name=f"r{i}", access="ro")
        for i in first + second
    ]

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader.load_registers",
        lambda: regs,
    )

    addresses = [r.address for r in regs]
    expected = group_reads(addresses, max_block_size=MAX_BATCH_REGISTERS)
    plans = [
        p
        for p in plan_group_reads(max_block_size=MAX_BATCH_REGISTERS)
        if p.function == "04"
    ]

    assert [(p.address, p.length) for p in plans] == expected
