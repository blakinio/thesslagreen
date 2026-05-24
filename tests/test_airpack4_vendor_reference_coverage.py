"""Tests: AirPack4 vendor reference coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "airpack4_modbus.json"
MAIN_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)

KNOWN_EXTRA_PREFIXES = ("alarm", "error", "s_", "e_", "f_")
KNOWN_EXTRA_WHITELIST = {
    (4, 0x0017): "heating_temperature TH sensor, present on AirPack4 h/v units",
    (4, 0x012A): "water_removal_active HEWR procedure flag, series 4",
}


def _fc_num(key: str) -> int:
    return int(key[2:4])


@pytest.fixture(scope="module")
def reference_pairs() -> dict[tuple[int, int], dict]:
    data = json.loads(REF_PATH.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict] = {}
    for key in (
        "fc01_coils",
        "fc02_discrete_inputs",
        "fc03_holding_registers",
        "fc04_input_registers",
    ):
        fn = _fc_num(key)
        for entry in data[key]["registers"]:
            addr = entry.get("dec")
            if addr is None:
                addr = int(entry["hex"], 16)
            result[(fn, int(addr))] = entry
    return result


@pytest.fixture(scope="module")
def integration_pairs() -> dict[tuple[int, int], dict]:
    data = json.loads(MAIN_PATH.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict] = {}
    for r in data["registers"]:
        fn = int(str(r["function"]))
        addr = r.get("address_dec")
        if addr is None:
            addr = int(str(r["address_hex"]), 16)
        result[(fn, int(addr))] = r
    return result


def test_no_unclassified_missing_registers(
    reference_pairs: dict[tuple[int, int], dict],
    integration_pairs: dict[tuple[int, int], dict],
) -> None:
    """All vendor registers must be in integration OR explicitly deferred."""
    # These are deferred registers — documented in docs/airpack4_deferred_registers.md
    # Currently there are none deferred after adding E197.
    DEFERRED: set[tuple[int, int]] = set()
    missing = set(reference_pairs) - set(integration_pairs) - DEFERRED
    assert not missing, f"Unclassified missing vendor registers: {sorted(missing)}"


def test_extras_are_known(
    reference_pairs: dict[tuple[int, int], dict],
    integration_pairs: dict[tuple[int, int], dict],
) -> None:
    """Integration-only registers must be whitelisted or have a known prefix."""
    extras = set(integration_pairs) - set(reference_pairs)
    unknown = []
    for pair in extras:
        name = integration_pairs[pair].get("name") or ""
        if any(name.startswith(p) for p in KNOWN_EXTRA_PREFIXES):
            continue
        if pair in KNOWN_EXTRA_WHITELIST:
            continue
        unknown.append((pair, name))
    assert not unknown, f"Integration has unwhitelisted extra registers: {unknown}"


def test_e197_present_in_integration(
    integration_pairs: dict[tuple[int, int], dict],
) -> None:
    """E197 (FC03 0x20C7=8391) must be in integration register map."""
    assert (3, 8391) in integration_pairs, "E197 register missing from integration"
    reg = integration_pairs[(3, 8391)]
    assert reg["name"] == "e_197"


def test_vendor_file_counts() -> None:
    """Vendor reference must have expected register counts."""
    data = json.loads(REF_PATH.read_text(encoding="utf-8"))
    assert len(data["fc01_coils"]["registers"]) == 8
    assert len(data["fc02_discrete_inputs"]["registers"]) == 16
    assert len(data["fc03_holding_registers"]["registers"]) == 302
    assert len(data["fc04_input_registers"]["registers"]) == 27
