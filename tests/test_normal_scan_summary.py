"""Tests for normal config-flow scan Modbus error summary correctness.

Covers the four scenarios described in the audit task:
  1. Recovered input batch failure  → no Modbus error in popup.
  2. Expected optional input register → no Modbus error in popup.
  3. Known-missing input register → missing summary only, not Modbus error.
  4. True unrecovered named input register → counted and identifiable.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus._config_flow.confirm import (
    _summarize_address_dict,
    build_confirmation_placeholders,
)
from custom_components.thessla_green_modbus.scanner.device_info import (
    DeviceCapabilities,
    ScannerDeviceInfo,
)
from custom_components.thessla_green_modbus.scanner.registers import (
    scan_named_input,
    scan_register_batch,
)
from custom_components.thessla_green_modbus.scanner.scan_runtime import (
    _collect_unrecovered_modbus_errors,
    build_scan_result,
)

_N_A = "—"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scanner() -> MagicMock:
    """Minimal scanner mock with the failed_addresses structure used by scan_register_batch."""
    scanner = MagicMock()
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    scanner.failed_addresses = {
        "modbus_exceptions": {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
        "invalid_values": {
            "input_registers": set(),
            "holding_registers": set(),
        },
        "batch_failures": {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
        "deep_scan_raw_failures": {},
    }
    scanner._is_valid_register_value = MagicMock(return_value=True)
    scanner._log_invalid_value = MagicMock()
    scanner._transport = None
    scanner._client = None

    def _group(addresses, boundaries=None):
        if not addresses:
            return []
        return [(min(addresses), max(addresses) - min(addresses) + 1)]

    scanner._group_registers_for_batch_read = _group
    return scanner


# ---------------------------------------------------------------------------
# Test 1: Recovered input batch failure → no Modbus error in popup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovered_input_batch_clears_from_modbus_exceptions():
    """Pre-populated modbus_exceptions entry is cleared when the fallback probe succeeds.

    Simulates the real scenario where read_input's cache-skip path
    (mark_failed_addresses) pre-adds addresses to modbus_exceptions before
    scan_register_batch runs its individual fallback probes.
    """
    scanner = _make_scanner()
    # Simulate what read_input does when it finds addresses in a cached unsupported range
    scanner.failed_addresses["modbus_exceptions"]["input_registers"].update({0, 1, 2, 3})

    addr_to_names = {
        0: {"version_major"},
        1: {"version_minor"},
        2: {"day_of_week"},
        3: {"period"},
    }
    addresses = [0, 1, 2, 3]

    async def read_fn(start, count, *, skip_cache=False):
        if not skip_cache:
            return None  # batch read short-circuits (cached unsupported range)
        return [42]  # individual fallback probe succeeds

    await scan_register_batch(scanner, "input_registers", addr_to_names, addresses, read_fn)

    # Recovered addresses must be removed from modbus_exceptions
    assert not scanner.failed_addresses["modbus_exceptions"]["input_registers"], (
        "Recovered batch failures must not appear in modbus_exceptions"
    )
    # batch_failures records the event for diagnostics
    assert scanner.failed_addresses["batch_failures"]["input_registers"] == {0, 1, 2, 3}
    # Register names are available
    assert {"version_major", "version_minor", "day_of_week", "period"}.issubset(
        scanner.available_registers["input_registers"]
    )


@pytest.mark.asyncio
async def test_recovered_input_batch_summary_shows_no_modbus_error():
    """End-to-end: recovered batch failure → modbus_failed_summary is N/A."""
    # Build a scan_result where modbus_exceptions is empty (all recovered)
    scan_result: dict = {
        "register_count": 10,
        "failed_addresses": {
            "modbus_exceptions": {},
            "invalid_values": {},
            "expected_optional": {},
            "batch_failures": {"input_registers": [0, 1, 2, 3]},
            "deep_scan_raw_failures": {},
        },
        "missing_registers": {},
        "scan_mode": "named",
        "scan_stats": {"total_attempts": 0, "successful_reads": 10, "scan_duration": 0.1},
        "capabilities": {},
        "available_registers": {"input_registers": {"version_major"}},
    }

    hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    data = {"host": "192.168.1.1", "port": 502, "slave_id": 1}
    device_info: dict = {}

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        placeholders = await build_confirmation_placeholders(
            hass=hass,
            data=data,
            device_info=device_info,
            scan_result=scan_result,
            cap_cls=DeviceCapabilities,
            caps_to_dict=lambda c: {},
        )

    assert placeholders["modbus_failed_summary"] == _N_A


# ---------------------------------------------------------------------------
# Test 2: Expected optional input register → no Modbus error in popup
# ---------------------------------------------------------------------------


def test_expected_optional_addresses_excluded_from_modbus_summary():
    """Expected-optional firmware register addresses are excluded from the Modbus error count."""
    # Addresses 4-15 are firmware-version metadata: absent on some FW versions.
    optional_addrs = list(range(4, 16))  # [4, 5, ..., 15]
    modbus_exceptions = {"input_registers": optional_addrs}
    expected_optional = {"input_registers": optional_addrs}

    summary = _summarize_address_dict(modbus_exceptions, exclude=expected_optional)

    assert summary == _N_A, (
        "Expected-optional addresses must not appear in the user-facing Modbus error summary"
    )


def test_expected_optional_partial_exclusion():
    """Only the expected-optional subset is excluded; real failures remain visible."""
    modbus_exceptions = {"input_registers": [4, 5, 271]}
    expected_optional = {"input_registers": [4, 5]}

    summary = _summarize_address_dict(modbus_exceptions, exclude=expected_optional)

    assert summary == "input_registers: 1"


# ---------------------------------------------------------------------------
# Test 3: Known-missing input register → missing summary only, not Modbus error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_known_missing_input_excluded_from_scan():
    """Registers in KNOWN_MISSING_REGISTERS are skipped: they do not appear in
    modbus_exceptions even if the device would reject their addresses."""
    scanner = _make_scanner()
    scanner._known_missing_registers = {}

    known_missing_name = "version_patch"  # addr 4 in KNOWN_MISSING_REGISTERS
    input_registers_map = {4: known_missing_name, 0: "version_major"}

    read_calls: list[tuple[int, int]] = []

    async def read_fn(start, count, *, skip_cache=False):
        read_calls.append((start, count))
        return [100] * count

    with patch(
        "custom_components.thessla_green_modbus.scanner.registers.KNOWN_MISSING_REGISTERS",
        {"input_registers": {known_missing_name}},
    ):
        await scan_named_input(scanner, input_registers_map)

    # version_patch (addr 4) must never have been probed
    all_addrs_probed = {s for s, _ in read_calls} | {s + i for s, c in read_calls for i in range(c)}
    assert 4 not in all_addrs_probed, "Known-missing register addr must not be probed"

    # addr 4 must not appear in modbus_exceptions
    assert 4 not in scanner.failed_addresses["modbus_exceptions"]["input_registers"]


def test_missing_register_address_excluded_from_modbus_summary():
    """A named register that truly failed (in both missing_registers and modbus_exceptions)
    is shown only in the 'Brakujące' row, not double-counted as a Modbus error."""
    # Suppose constant_flow_active (addr 271) failed — it is in both dicts.
    modbus_exceptions = {"input_registers": [271]}
    missing_registers = {"input_registers": {"constant_flow_active": 271}}
    scan_result: dict = {
        "register_count": 5,
        "failed_addresses": {
            "modbus_exceptions": modbus_exceptions,
            "invalid_values": {},
            "expected_optional": {},
        },
        "missing_registers": missing_registers,
    }

    # _summarize_address_dict with combined_exclude (as built by confirm.py)
    combined_exclude: dict[str, list[int]] = {
        reg_type: list(regs.values())
        for reg_type, regs in missing_registers.items()
        if isinstance(regs, dict)
    }
    summary = _summarize_address_dict(
        scan_result["failed_addresses"]["modbus_exceptions"],
        exclude=combined_exclude,
    )

    assert summary == _N_A, (
        "Truly-absent named register must not appear in Modbus error summary "
        "(it is already captured in missing_registers)"
    )


# ---------------------------------------------------------------------------
# Test 4: True unrecovered named input register → counted and identifiable
# ---------------------------------------------------------------------------


def test_true_unrecovered_input_error_identifiable():
    """A genuinely unrecovered Modbus failure appears in unrecovered_modbus_errors
    with its register name, enabling diagnostic identification."""
    scanner = SimpleNamespace(
        failed_addresses={
            "modbus_exceptions": {"input_registers": {271}},
            "invalid_values": {"input_registers": set()},
            "batch_failures": {},
            "deep_scan_raw_failures": {},
        },
        _resolved_connection_mode="tcp",
        deep_scan=False,
        _registers={4: {271: "constant_flow_active"}},
        _unsupported_input_ranges={},
    )

    device = ScannerDeviceInfo()
    caps = DeviceCapabilities()
    result = build_scan_result(
        scanner,
        device=device,
        caps=caps,
        available_registers={"input_registers": set()},
        unknown_registers={},
        scanned_registers={},
        scan_blocks={},
        missing_registers={},
        scan_started=0.0,
        raw_registers={},
    )

    unrecovered = result["failed_addresses"]["unrecovered_modbus_errors"]
    assert "input_registers" in unrecovered
    entry = unrecovered["input_registers"][0]
    assert entry["addr"] == 271
    assert entry["name"] == "constant_flow_active"

    # Verify it is also visible in the Modbus error count
    modbus_summary = _summarize_address_dict(result["failed_addresses"]["modbus_exceptions"])
    assert modbus_summary == "input_registers: 1"


def test_unrecovered_modbus_errors_unnamed_address():
    """An unnamed address in modbus_exceptions has name=None in the diagnostic."""
    scanner = SimpleNamespace(
        failed_addresses={
            "modbus_exceptions": {"input_registers": {99}},
        },
        _registers={},
    )

    result = _collect_unrecovered_modbus_errors(scanner)

    assert "input_registers" in result
    entry = result["input_registers"][0]
    assert entry["addr"] == 99
    assert entry["name"] is None
