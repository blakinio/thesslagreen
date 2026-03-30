"""Smoke test using register loader with device scanner."""

from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner


def test_scanner_with_loader_addresses():
    """Ensure scanner can group addresses from the loader."""
    scanner = ThesslaGreenDeviceScanner("host", 502)
    addresses = [r.address for r in get_registers_by_function("input")[6:11]]
    groups = scanner._group_registers_for_batch_read(addresses)
    # compilation_seconds (addr=15) is now in KNOWN_MISSING_REGISTERS and gets
    # isolated; the remaining 4 addresses form a single batch.
    first = min(addresses)
    if any(a in scanner._known_missing_addresses for a in addresses):
        assert len(groups) > 1
        assert sum(c for _, c in groups) == len(addresses)
    else:
        assert groups == [(first, len(addresses))]
