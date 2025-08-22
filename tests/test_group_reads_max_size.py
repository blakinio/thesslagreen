from custom_components.thessla_green_modbus.loader import group_reads


def test_group_reads_respects_max_block_size() -> None:
    """group_reads splits long address ranges based on ``max_block_size``."""

    addresses = list(range(40))
    assert group_reads(addresses, max_block_size=16) == [
        (0, 16),
        (16, 16),
        (32, 8),
    ]
