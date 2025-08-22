"""Tests for group_reads utility."""

from custom_components.thessla_green_modbus.loader import group_reads


def test_group_reads_merges_consecutive_addresses():
    addresses = [0, 1, 2, 3, 10, 11, 12]
    assert group_reads(addresses) == [(0, 4), (10, 3)]


def test_group_reads_respects_max_block_size():
    addresses = list(range(70))
    assert group_reads(addresses, max_block_size=64) == [(0, 64), (64, 6)]
