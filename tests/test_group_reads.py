"""Tests for ``plan_group_reads`` utility."""

import importlib
import sys

import pytest
from custom_components.thessla_green_modbus.modbus_helpers import group_reads


@pytest.fixture()
def loader_mod():
    """Return the current loader module (fresh after any reloads)."""
    mod_name = "custom_components.thessla_green_modbus.registers.loader"
    return sys.modules.get(mod_name) or importlib.import_module(mod_name)

try:
    from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner
except Exception:  # pragma: no cover - scanner requires HA deps
    ThesslaGreenDeviceScanner = None
from custom_components.thessla_green_modbus.scanner_helpers import MAX_BATCH_REGISTERS


def test_group_reads_merges_consecutive_addresses():
    addresses = [0, 1, 2, 3, 10, 11, 12]
    assert group_reads(addresses) == [(0, 4), (10, 3)]


@pytest.mark.parametrize("size", [1, 8, MAX_BATCH_REGISTERS, 32])
def test_group_reads_respects_max_block_size(size):
    addresses = list(range(40))
    groups = group_reads(addresses, max_block_size=size)
    assert max(length for _, length in groups) <= min(size, MAX_BATCH_REGISTERS)
    if size > MAX_BATCH_REGISTERS:
        assert groups == group_reads(addresses, max_block_size=MAX_BATCH_REGISTERS)


def test_plan_group_reads_merges_consecutive_addresses(monkeypatch, loader_mod):
    _Register = loader_mod.Register
    _ReadPlan = loader_mod.ReadPlan
    _plan_group_reads = loader_mod.plan_group_reads
    regs = [_Register("input", addr, f"r{addr}", "r") for addr in [0, 1, 2, 3, 10, 11, 12]]
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader.load_registers",
        lambda: regs,
    )
    assert _plan_group_reads() == [_ReadPlan("input", 0, 4), _ReadPlan("input", 10, 3)]


def test_plan_group_reads_respects_max_block_size(monkeypatch, loader_mod):
    _Register = loader_mod.Register
    _ReadPlan = loader_mod.ReadPlan
    _plan_group_reads = loader_mod.plan_group_reads
    regs = [_Register("input", addr, f"r{addr}", "r") for addr in range(22)]
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader.load_registers",
        lambda: regs,
    )
    assert _plan_group_reads() == [
        _ReadPlan("input", 0, MAX_BATCH_REGISTERS),
        _ReadPlan("input", MAX_BATCH_REGISTERS, 6),
    ]


@pytest.mark.parametrize("size", [1, 4, MAX_BATCH_REGISTERS, 32])
def test_plan_group_reads_varied_block_sizes(monkeypatch, size, loader_mod):
    _Register = loader_mod.Register
    _ReadPlan = loader_mod.ReadPlan
    _plan_group_reads = loader_mod.plan_group_reads
    regs = [_Register("input", addr, f"r{addr}", "r") for addr in range(10)]
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader.load_registers",
        lambda: regs,
    )
    addresses = [r.address for r in regs]
    expected = [
        _ReadPlan("input", start, length)
        for start, length in group_reads(addresses, max_block_size=size)
    ]
    assert _plan_group_reads(max_block_size=size) == expected


@pytest.mark.skipif(ThesslaGreenDeviceScanner is None, reason="scanner unavailable")
def test_scanner_respects_default_max_block_size():
    scanner = ThesslaGreenDeviceScanner("host", 502)
    addresses = list(range(MAX_BATCH_REGISTERS + 6))
    # Known-missing input registers in range(22): version_patch=4,
    # compilation_days=14, compilation_seconds=15, duct_supply_temperature=20,
    # gwc_temperature=21 — each is isolated into a single-register group.
    assert scanner._group_registers_for_batch_read(addresses) == [
        (0, 4),
        (4, 1),
        (5, 9),
        (14, 1),
        (15, 1),
        (16, 4),
        (20, 1),
        (21, 1),
    ]
