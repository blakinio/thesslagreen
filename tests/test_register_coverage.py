from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

from custom_components.thessla_green_modbus.utils import _to_snake_case

from tests.platform_stubs import install_common_ha_stubs

INTENTIONAL_OMISSIONS = {
    "serial_number_2",
    "serial_number_3",
    "serial_number_4",
    "serial_number_5",
    "serial_number_6",
    # BCD-encoded date/time registers — not exposed as any entity platform
    "date_time",
    "date_time_ddtt",
    "date_time_ggmm",
    "date_time_sscc",
    # device_name_2..8 are sub-parts of the device name string decoded by the
    # scanner as a single combined string — no individual entity mappings needed.
    "device_name_2",
    "device_name_3",
    "device_name_4",
    "device_name_5",
    "device_name_6",
    "device_name_7",
    "device_name_8",
    "lock_pass_2",
}

# Minimal Home Assistant stubs required to import entity mappings
install_common_ha_stubs()


def test_all_registers_covered() -> None:
    """Ensure all registers are exposed or intentionally omitted."""

    json_file = (
        Path("custom_components/thessla_green_modbus/registers")
        / "thessla_green_registers_full.json"
    )
    registers = {
        _to_snake_case(r["name"])
        for r in json.loads(json_file.read_text(encoding="utf-8"))["registers"]
        if r.get("name")
    }

    entity_mod = importlib.import_module("custom_components.thessla_green_modbus.mappings")
    exposed: set[str] = set()
    for mapping in entity_mod.ENTITY_MAPPINGS.values():
        exposed.update(mapping.keys())

    diagnostic_regs = {
        n for n in registers if n in {"alarm", "error"} or re.match(r"[es](?:_|\d)", n)
    }

    missing = registers - exposed - diagnostic_regs - INTENTIONAL_OMISSIONS
    assert not missing, f"Unmapped registers: {sorted(missing)}"


def test_intentional_omissions_are_valid() -> None:
    """Every entry in INTENTIONAL_OMISSIONS must:
    1. Exist as a real register (no typos).
    2. NOT already have an entity mapping (no stale entries).
    """
    json_file = (
        Path("custom_components/thessla_green_modbus/registers")
        / "thessla_green_registers_full.json"
    )
    registers = {
        _to_snake_case(r["name"])
        for r in json.loads(json_file.read_text(encoding="utf-8"))["registers"]
        if r.get("name")
    }

    entity_mod = importlib.import_module("custom_components.thessla_green_modbus.mappings")
    exposed: set[str] = set()
    for mapping in entity_mod.ENTITY_MAPPINGS.values():
        exposed.update(mapping.keys())

    phantom = INTENTIONAL_OMISSIONS - registers
    assert not phantom, (
        f"INTENTIONAL_OMISSIONS zawiera nieistniejące rejestry (literówki?): {sorted(phantom)}"
    )

    stale = INTENTIONAL_OMISSIONS & exposed
    assert not stale, (
        f"INTENTIONAL_OMISSIONS zawiera rejestry które już mają encje (stale): {sorted(stale)}"
    )


def test_number_translations_match() -> None:
    """Ensure NUMBER_ENTITY_MAPPINGS keys match entity.number in translation files."""
    import json as _json
    from pathlib import Path as _Path

    entity_mod = importlib.import_module("custom_components.thessla_green_modbus.mappings")
    number_keys = set(entity_mod.NUMBER_ENTITY_MAPPINGS.keys())

    trans_root = _Path("custom_components/thessla_green_modbus/translations")
    for lang in ("en", "pl"):
        data = _json.loads((trans_root / f"{lang}.json").read_text(encoding="utf-8"))
        trans_keys = set(data.get("entity", {}).get("number", {}).keys())
        missing = number_keys - trans_keys
        extra = trans_keys - number_keys
        assert not missing, f"[{lang}] Missing number translations: {sorted(missing)}"
        assert not extra, f"[{lang}] Extra/unused number translations: {sorted(extra)}"
