"""Tests for grouping register reads."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.thessla_green_modbus.registers import Register, group_reads
import custom_components.thessla_green_modbus.registers.loader as loader


def _make_regs(addresses: list[int]) -> list[Register]:
    return [Register(function="04", address=a, name=f"r{a}", access="ro") for a in addresses]


def test_group_reads_merges_consecutive_addresses(monkeypatch):
    regs = _make_regs([0, 1, 2, 3, 10, 11, 12])
    monkeypatch.setattr(loader, "get_all_registers", lambda: regs)
    plans = group_reads()
    assert [(p.address, p.length) for p in plans if p.function == "04"] == [(0, 4), (10, 3)]


def test_group_reads_respects_max_block_size(monkeypatch):
    regs = _make_regs(list(range(70)))
    monkeypatch.setattr(loader, "get_all_registers", lambda: regs)
    plans = group_reads(max_block_size=64)
    assert [(p.address, p.length) for p in plans if p.function == "04"] == [(0, 64), (64, 6)]
