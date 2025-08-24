"""Tests for group_reads utility."""

from custom_components.thessla_green_modbus.modbus_helpers import group_reads
from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.scanner_helpers import MAX_BATCH_REGISTERS


def test_group_reads_merges_consecutive_addresses():
    addresses = [0, 1, 2, 3, 10, 11, 12]
    assert group_reads(addresses) == [(0, 4), (10, 3)]


def test_group_reads_respects_max_block_size():
    addresses = list(range(70))
    assert group_reads(addresses, max_block_size=64) == [(0, 64), (64, 6)]


def test_scanner_respects_default_max_block_size():
    scanner = ThesslaGreenDeviceScanner("host", 502)
    addresses = list(range(MAX_BATCH_REGISTERS + 6))
    assert scanner._group_registers_for_batch_read(addresses) == [
        (0, MAX_BATCH_REGISTERS),
        (MAX_BATCH_REGISTERS, 6),
    ]
