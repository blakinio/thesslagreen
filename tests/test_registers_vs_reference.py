"""Verify integration registers match the vendor reference (airpack4_modbus.json)."""

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
def main_pairs() -> dict[tuple[int, int], dict]:
    data = json.loads(MAIN_PATH.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict] = {}
    for r in data["registers"]:
        fn = int(str(r["function"]))
        addr = r.get("address_dec")
        if addr is None:
            addr = int(str(r["address_hex"]), 16)
        result[(fn, int(addr))] = r
    return result


def test_all_reference_registers_present(reference_pairs, main_pairs):
    missing = set(reference_pairs) - set(main_pairs)
    assert not missing, (
        f"Registers in vendor reference but missing from integration: {sorted(missing)}"
    )


def test_extras_are_known(reference_pairs, main_pairs):
    extras = set(main_pairs) - set(reference_pairs)
    unknown_extras = []
    for pair in extras:
        entry = main_pairs[pair]
        name = entry.get("name") or ""
        if any(name.startswith(p) for p in KNOWN_EXTRA_PREFIXES):
            continue
        if pair in KNOWN_EXTRA_WHITELIST:
            continue
        unknown_extras.append((pair, name))

    assert not unknown_extras, (
        "Integration has registers not in reference and not whitelisted: "
        f"{unknown_extras}. Either add to KNOWN_EXTRA_WHITELIST with justification "
        "or remove from integration."
    )
