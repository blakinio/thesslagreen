"""Tests for ``plan_group_reads`` utility."""

import pytest

from custom_components.thessla_green_modbus.modbus_helpers import group_reads
import custom_components.thessla_green_modbus.registers.loader as loader
from custom_components.thessla_green_modbus.registers import (
    ReadPlan,
    Register,
    plan_group_reads,
)
from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner


def test_group_reads_merges_consecutive_addresses():
    addresses = [0, 1, 2, 3, 10, 11, 12]
    assert group_reads(addresses) == [(0, 4), (10, 3)]


def test_group_reads_respects_max_block_size():
    addresses = list(range(70))
    assert group_reads(addresses, max_block_size=64) == [(0, 64), (64, 6)]
def test_plan_group_reads_merges_consecutive_addresses(monkeypatch):
    regs = [
        Register("input", addr, f"r{addr}", "r")
        for addr in [0, 1, 2, 3, 10, 11, 12]
    ]
    monkeypatch.setattr(loader, "_load_registers", lambda: regs)
    assert plan_group_reads() == [ReadPlan("input", 0, 4), ReadPlan("input", 10, 3)]


def test_plan_group_reads_respects_max_block_size(monkeypatch):
    regs = [Register("input", addr, f"r{addr}", "r") for addr in range(70)]
    monkeypatch.setattr(loader, "_load_registers", lambda: regs)
    assert plan_group_reads(max_block_size=64) == [
        ReadPlan("input", 0, 64),
        ReadPlan("input", 64, 6),
    ]


@pytest.mark.parametrize("limit", [1, 8, 16, 20])
def test_scanner_respects_max_registers_per_request(limit):
    scanner = ThesslaGreenDeviceScanner("host", 502, max_registers_per_request=limit)
    addresses = list(range(40))
    step = min(limit, 16)
    expected = [
        (start, min(step, 40 - start))
        for start in range(0, 40, step)
    ]
    assert scanner._group_registers_for_batch_read(addresses) == expected
