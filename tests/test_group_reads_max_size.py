from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner


def test_group_reads_respects_max_block_size() -> None:
    """group_reads splits long address ranges based on ``max_block_size``."""

    addresses = list(range(40))
    scanner = ThesslaGreenDeviceScanner("host", 502)
    scanner._known_missing_addresses = set()
    assert scanner._group_registers_for_batch_read(addresses) == [
        (0, 16),
        (16, 16),
        (32, 8),
    ]
