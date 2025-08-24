from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.const import MAX_BATCH_REGISTERS


def test_group_reads_respects_max_block_size() -> None:
    """group_reads splits long address ranges based on ``max_block_size``."""

    addresses = list(range(40))
    scanner = ThesslaGreenDeviceScanner("host", 502)
    scanner._known_missing_addresses = set()
    assert scanner._group_registers_for_batch_read(addresses) == [
        (0, MAX_BATCH_REGISTERS),
        (MAX_BATCH_REGISTERS, MAX_BATCH_REGISTERS),
        (MAX_BATCH_REGISTERS * 2, 40 - 2 * MAX_BATCH_REGISTERS),
    ]
