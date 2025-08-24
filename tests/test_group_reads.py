"""Tests for ``plan_group_reads`` utility."""

from custom_components.thessla_green_modbus.modbus_helpers import group_reads
import custom_components.thessla_green_modbus.registers.loader as loader
from custom_components.thessla_green_modbus.registers.loader import (
    ReadPlan,
    Register,
    plan_group_reads,
)
from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.scanner_helpers import MAX_BATCH_REGISTERS


def test_group_reads_merges_consecutive_addresses():
    addresses = [0, 1, 2, 3, 10, 11, 12]
    assert group_reads(addresses) == [(0, 4), (10, 3)]


def test_group_reads_respects_max_block_size():
    addresses = list(range(22))
    assert group_reads(addresses, max_block_size=16) == [(0, 16), (16, 6)]
def test_plan_group_reads_merges_consecutive_addresses(monkeypatch):
    regs = [
        Register("input", addr, f"r{addr}", "r")
        for addr in [0, 1, 2, 3, 10, 11, 12]
    ]
    monkeypatch.setattr(loader, "load_registers", lambda: regs)
    assert plan_group_reads() == [ReadPlan("input", 0, 4), ReadPlan("input", 10, 3)]


def test_plan_group_reads_respects_max_block_size(monkeypatch):
    regs = [Register("input", addr, f"r{addr}", "r") for addr in range(22)]
    monkeypatch.setattr(loader, "load_registers", lambda: regs)
    assert plan_group_reads(max_block_size=16) == [
        ReadPlan("input", 0, 16),
        ReadPlan("input", 16, 6),
    ]


def test_scanner_respects_default_max_block_size():
    scanner = ThesslaGreenDeviceScanner("host", 502)
    addresses = list(range(MAX_BATCH_REGISTERS + 6))
    assert scanner._group_registers_for_batch_read(addresses) == [
        (0, 14),
        (14, 1),
        (15, MAX_BATCH_REGISTERS - 15),
        (MAX_BATCH_REGISTERS, 6),
    ]
