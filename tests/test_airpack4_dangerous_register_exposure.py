"""Tests: Dangerous AirPack4 registers are not newly exposed as writable entities.

These tests scan mapping source files as text to verify that certain dangerous or
action registers are not exposed as entity mapping keys. They do NOT require the
full HA stack — plain Python / filesystem access only.

Pre-existing intentional exposures (hard_reset_settings, hard_reset_schedule as
switches; configuration_mode, access_level, uart_0_baud/parity/stop,
uart_1_baud/parity/stop as selects; filter_change as select; lock_flag as switch)
are not checked here — they are covered by existing integration tests.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "thessla_green_modbus"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test: filterChange (vendor camelCase) must never appear in mapping files.
# The integration uses 'filter_change' (snake_case) for the filter-type select,
# which is pre-existing. The vendor name 'filterChange' (write=replace filter)
# must not appear.
# ---------------------------------------------------------------------------


def test_filter_change_vendor_name_not_in_mappings() -> None:
    """Vendor camelCase 'filterChange' must not appear in any mapping file."""
    discrete = _read(COMP / "mappings" / "_static_discrete.py")
    numbers = _read(COMP / "mappings" / "_static_numbers.py")
    assert "filterChange" not in discrete, "'filterChange' found in _static_discrete.py"
    assert "filterChange" not in numbers, "'filterChange' found in _static_numbers.py"


# ---------------------------------------------------------------------------
# Test: lockPass1 / lockPass2 (vendor names) must not appear in mapping files.
# ---------------------------------------------------------------------------


def test_lock_pass_vendor_names_not_in_mappings() -> None:
    """lockPass1 and lockPass2 must not appear in any mapping file."""
    for path in [
        COMP / "mappings" / "_static_discrete.py",
        COMP / "mappings" / "_static_numbers.py",
        COMP / "mappings" / "_static_discrete_uart.py",
    ]:
        text = _read(path)
        assert "lockPass1" not in text, f"lockPass1 found in {path.name}"
        assert "lockPass2" not in text, f"lockPass2 found in {path.name}"


# ---------------------------------------------------------------------------
# Test: lockFlag (vendor camelCase) must not appear in mapping files.
# Note: 'lock_flag' (snake_case) IS a pre-existing switch entity — not tested here.
# ---------------------------------------------------------------------------


def test_lock_flag_vendor_name_not_in_mappings() -> None:
    """Vendor camelCase 'lockFlag' must not appear in any mapping file."""
    discrete = _read(COMP / "mappings" / "_static_discrete.py")
    numbers = _read(COMP / "mappings" / "_static_numbers.py")
    assert "lockFlag" not in discrete, "'lockFlag' found in _static_discrete.py"
    assert "lockFlag" not in numbers, "'lockFlag' found in _static_numbers.py"


# ---------------------------------------------------------------------------
# Test: uart_0_id / uart_1_id must not appear as select entity mapping keys.
# They ARE in NUMBER_OVERRIDES (for min/max metadata) but are not select entities.
# ---------------------------------------------------------------------------


def test_uart_id_not_in_select_mappings() -> None:
    """uart_0_id and uart_1_id must not appear in select entity mapping file."""
    text = _read(COMP / "mappings" / "_static_discrete.py")
    assert '"uart_0_id"' not in text, "'uart_0_id' found as select key in _static_discrete.py"
    assert '"uart_1_id"' not in text, "'uart_1_id' found as select key in _static_discrete.py"


def test_uart_id_vendor_names_not_in_mappings() -> None:
    """Vendor camelCase uart0Id / uart1Id must not appear in any mapping file."""
    for path in [
        COMP / "mappings" / "_static_discrete.py",
        COMP / "mappings" / "_static_numbers.py",
        COMP / "mappings" / "_static_discrete_uart.py",
    ]:
        text = _read(path)
        assert "uart0Id" not in text, f"uart0Id found in {path.name}"
        assert "uart1Id" not in text, f"uart1Id found in {path.name}"


# ---------------------------------------------------------------------------
# Test: deviceName* registers must not appear in any mapping file.
# ---------------------------------------------------------------------------


def test_device_name_not_in_entity_mappings() -> None:
    """deviceName* registers must not appear in any writable entity mapping file."""
    for path in [
        COMP / "mappings" / "_static_discrete.py",
        COMP / "mappings" / "_static_numbers.py",
        COMP / "mappings" / "_static_discrete_uart.py",
        COMP / "mappings" / "_static_discrete_diagnostics.py",
    ]:
        text = _read(path)
        assert "deviceName" not in text, f"deviceName found in {path.name}"


# ---------------------------------------------------------------------------
# Test: e_197 must not be in switch or number entity mapping files.
# E197 is an auto-reset alarm flag; it is read-only in practice and should
# only appear as a binary_sensor at most — never as a writable entity.
# ---------------------------------------------------------------------------


def test_e197_not_in_writable_entity_mappings() -> None:
    """e_197 must not appear in switch or number entity mapping files."""
    switch_text = _read(COMP / "mappings" / "_static_discrete.py")
    number_text = _read(COMP / "mappings" / "_static_numbers.py")
    assert "e_197" not in switch_text, "e_197 found in _static_discrete.py"
    assert "e_197" not in number_text, "e_197 found in _static_numbers.py"
