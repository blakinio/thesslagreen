from custom_components.thessla_green_modbus.const import MAX_BATCH_REGISTERS
from custom_components.thessla_green_modbus.scanner_core import (
    ThesslaGreenDeviceScanner,
)

import pytest


@pytest.mark.parametrize("limit", [1, 8, MAX_BATCH_REGISTERS, 32])
def test_group_reads_respects_max_block_size(limit: int) -> None:
    """group_reads splits long address ranges based on ``max_block_size``.

    The scanner should respect the configured batch size while never
    exceeding the Modbus safe limit of ``MAX_BATCH_REGISTERS`` even when a
    higher value is requested by the user.
    """

    addresses = list(range(MAX_BATCH_REGISTERS + 8))
    scanner = ThesslaGreenDeviceScanner(
        "host", 502, max_registers_per_request=limit
    )
    scanner._known_missing_addresses = set()

    groups = scanner._group_registers_for_batch_read(addresses)

    # No group should exceed the effective batch size which is clamped to the
    # integration wide ``MAX_BATCH_REGISTERS`` constant.
    assert max(length for _start, length in groups) <= min(limit, MAX_BATCH_REGISTERS)

    # Requests larger than ``MAX_BATCH_REGISTERS`` are capped at the limit
    # rather than using the oversized value directly.
    if limit > MAX_BATCH_REGISTERS:
        assert groups == scanner._group_registers_for_batch_read(
            addresses, max_batch=MAX_BATCH_REGISTERS
        )

    # The scanner itself clamps the requested batch size to ``MAX_BATCH_REGISTERS``.
    assert scanner.effective_batch == min(limit, MAX_BATCH_REGISTERS)
