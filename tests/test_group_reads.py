"""Tests for group_reads utility."""

import custom_components.thessla_green_modbus.registers.loader as loader
from custom_components.thessla_green_modbus.registers import ReadPlan, Register, group_reads


def test_group_reads_merges_consecutive_addresses(monkeypatch):
    regs = [Register("input", addr, "r") for addr in [0, 1, 2, 3, 10, 11, 12]]
    monkeypatch.setattr(loader, "_load_registers", lambda: regs)
    assert group_reads() == [ReadPlan("input", 0, 4), ReadPlan("input", 10, 3)]


def test_group_reads_respects_max_block_size(monkeypatch):
    regs = [Register("input", addr, "r") for addr in range(70)]
    monkeypatch.setattr(loader, "_load_registers", lambda: regs)
    assert group_reads(max_block_size=64) == [ReadPlan("input", 0, 64), ReadPlan("input", 64, 6)]
