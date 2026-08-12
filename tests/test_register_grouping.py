from types import SimpleNamespace
from unittest.mock import Mock

from custom_components.thessla_green_modbus.const import MAX_BATCH_REGISTERS
from custom_components.thessla_green_modbus.core.register_groups import compute_register_groups
from custom_components.thessla_green_modbus.registers.loader import (
    RegisterDef as Register,
)
from custom_components.thessla_green_modbus.registers.loader import (
    get_registers_by_function,
    plan_group_reads,
)
from custom_components.thessla_green_modbus.registers.read_planner import group_reads
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function("04")}


def _expanded_addresses(fn: str) -> list[int]:
    plans = [p for p in plan_group_reads(max_block_size=32) if p.function == int(fn)]
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

    # compilation_seconds (missing_addr + 1 = 15) is also in KNOWN_MISSING_REGISTERS,
    # so both addr 14 and 15 are isolated; addr 16 forms its own single-item group.
    assert groups == [
        (missing_addr - 2, 2),
        (missing_addr, 1),
        (missing_addr + 1, 1),
        (missing_addr + 2, 1),
    ]  # nosec B101


def test_plan_group_reads_from_json():
    """Group consecutive registers based on JSON definitions."""
    regs = get_registers_by_function("04")
    addresses: list[int] = []
    for reg in regs:
        addresses.extend(range(reg.address, reg.address + reg.length))
    expected = group_reads(addresses, max_block_size=MAX_BATCH_REGISTERS)
    plans = [p for p in plan_group_reads() if p.function == 4]
    assert [(p.address, p.length) for p in plans] == expected


def test_plan_group_reads_splits_large_block(monkeypatch):
    """A long list of consecutive addresses is split into multiple blocks."""

    regs = [Register(function=4, address=i, name=f"r{i}", access="ro") for i in range(100)]

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader.load_registers",
        lambda: regs,
    )

    addresses = [r.address for r in regs]
    expected = group_reads(addresses, max_block_size=MAX_BATCH_REGISTERS)
    plans = [p for p in plan_group_reads(max_block_size=MAX_BATCH_REGISTERS) if p.function == 4]

    assert [(p.address, p.length) for p in plans] == expected


def test_plan_group_reads_handles_gaps_and_block_size(monkeypatch):
    """Gaps and block size limits both trigger new read plans."""

    # Two ranges of consecutive registers separated by a gap
    first = list(range(32))
    second = list(range(40, 80))
    regs = [Register(function=4, address=i, name=f"r{i}", access="ro") for i in first + second]

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader.load_registers",
        lambda: regs,
    )

    addresses = [r.address for r in regs]
    expected = group_reads(addresses, max_block_size=MAX_BATCH_REGISTERS)
    plans = [p for p in plan_group_reads(max_block_size=MAX_BATCH_REGISTERS) if p.function == 4]

    assert [(p.address, p.length) for p in plans] == expected


def test_compute_register_groups_falls_back_on_unexpected_definition_errors() -> None:
    """Unexpected definition failures use one-register reads in both scan modes."""

    def fail_definition(_name: str) -> None:
        raise RuntimeError("definition unavailable")

    boundaries = frozenset({101})
    for safe_scan in (True, False):
        client = SimpleNamespace(
            _register_groups={"stale": [(1, 1)]},
            available_registers={"holding_registers": {"broken"}},
            _register_maps={"holding_registers": {"broken": 100}},
            safe_scan=safe_scan,
            effective_batch=8,
        )
        grouped = Mock(return_value=[(100, 1)])

        compute_register_groups(
            client,
            get_register_definition=fail_definition,
            group_reads=grouped,
            holding_batch_boundaries=boundaries,
        )

        assert client._register_groups["holding_registers"] == [(100, 1)]
        assert "stale" not in client._register_groups
        if safe_scan:
            grouped.assert_not_called()
        else:
            grouped.assert_called_once_with(
                [100],
                max_block_size=8,
                boundaries=boundaries,
            )


def test_compute_register_groups_falls_back_on_missing_definitions() -> None:
    """Missing definitions use one-register reads in both scan modes."""

    def missing_definition(_name: str) -> None:
        raise KeyError("missing definition")

    boundaries = frozenset({101})
    for safe_scan in (True, False):
        client = SimpleNamespace(
            _register_groups={},
            available_registers={"holding_registers": {"missing"}},
            _register_maps={"holding_registers": {"missing": 100}},
            safe_scan=safe_scan,
            effective_batch=8,
        )
        grouped = Mock(return_value=[(100, 1)])

        compute_register_groups(
            client,
            get_register_definition=missing_definition,
            group_reads=grouped,
            holding_batch_boundaries=boundaries,
        )

        assert client._register_groups["holding_registers"] == [(100, 1)]
        if safe_scan:
            grouped.assert_not_called()
        else:
            grouped.assert_called_once_with(
                [100],
                max_block_size=8,
                boundaries=boundaries,
            )
