"""Tests for group_reads utility."""

from custom_components.thessla_green_modbus.registers.loader import group_reads


def test_group_reads_groups_by_gap():
    addresses = [0, 1, 2, 3, 20, 21]
    assert group_reads(addresses, max_gap=5) == [(0, 4), (20, 2)]


def test_group_reads_respects_max_batch():
    addresses = list(range(70))
    assert group_reads(addresses, max_batch=64) == [(0, 64), (64, 6)]
