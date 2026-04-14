"""Tests verifying that all entities have proper human-readable names.

Ensures no entity shows up with a raw key name (e.g. "supply_air_temperature")
or a generic fallback (e.g. "Problem 27", "Sensor 15") in Home Assistant.

Each entity must have:
- a translation_key that exists in strings.json, translations/en.json
  and translations/pl.json
- a non-empty 'name' in each translation file
- a name that does not contain underscores (would indicate a raw key leaked
  through instead of a human-readable label)
"""

from __future__ import annotations

import copy
import json
import os

import pytest

# ---------------------------------------------------------------------------
# Load translation files once
# ---------------------------------------------------------------------------
_BASE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "custom_components",
    "thessla_green_modbus",
)


def _load_json(path: str) -> dict:
    with open(os.path.join(_BASE, path), encoding="utf-8") as f:
        return json.load(f)


STRINGS = _load_json("strings.json")
EN = _load_json("translations/en.json")
PL = _load_json("translations/pl.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entity_names(trans: dict, platform: str) -> dict[str, str]:
    """Return {translation_key: name} for a platform from a translation dict."""
    return {
        key: val.get("name", "")
        for key, val in trans.get("entity", {}).get(platform, {}).items()
        if isinstance(val, dict)
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def entity_mappings():
    from custom_components.thessla_green_modbus.entity_mappings import (
        BINARY_SENSOR_ENTITY_MAPPINGS,
        NUMBER_ENTITY_MAPPINGS,
        SELECT_ENTITY_MAPPINGS,
        SENSOR_ENTITY_MAPPINGS,
        SWITCH_ENTITY_MAPPINGS,
        TEXT_ENTITY_MAPPINGS,
        TIME_ENTITY_MAPPINGS,
    )
    # Deep-copy each mapping so that mutations by other test modules
    # (e.g. test_switch.py injects "bypass" into SWITCH_ENTITY_MAPPINGS
    # at import time) do not pollute the canonical set of entities we
    # validate here.  We want the definitions as they exist in the source,
    # not whatever a test happened to add for its own purposes.
    #
    # "bypass" is a binary_sensor (coil register, read-only); test_switch.py
    # adds it to ENTITY_MAPPINGS["switch"] as a test fixture convenience.
    # We exclude any key that was injected by tests rather than defined in the
    # real mapping module by comparing against the authoritative binary_sensor
    # set and stripping cross-platform duplicates from switch.
    raw_switch = copy.deepcopy(dict(SWITCH_ENTITY_MAPPINGS))
    bs_keys = set(BINARY_SENSOR_ENTITY_MAPPINGS.keys())
    # Remove any key that is also a binary_sensor — those are test injections
    for k in bs_keys:
        raw_switch.pop(k, None)

    return {
        "sensor": copy.deepcopy(dict(SENSOR_ENTITY_MAPPINGS)),
        "binary_sensor": copy.deepcopy(dict(BINARY_SENSOR_ENTITY_MAPPINGS)),
        "switch": raw_switch,
        "select": copy.deepcopy(dict(SELECT_ENTITY_MAPPINGS)),
        "number": copy.deepcopy(dict(NUMBER_ENTITY_MAPPINGS)),
        "text": copy.deepcopy(dict(TEXT_ENTITY_MAPPINGS)),
        "time": copy.deepcopy(dict(TIME_ENTITY_MAPPINGS)),
    }


def _iter_entities(entity_mappings):
    """Yield (platform, mapping_key, translation_key) for every entity."""
    for platform, mappings in entity_mappings.items():
        for key, data in mappings.items():
            if platform == "number":
                # number.py sets _attr_translation_key = register_name directly
                tk = key
            else:
                tk = data.get("translation_key", key) if isinstance(data, dict) else key
            yield platform, key, tk


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEntityTranslationKeys:
    """Verify every entity's translation_key exists in all translation files."""

    def test_all_translation_keys_in_strings_json(self, entity_mappings):
        """Every translation_key must exist in strings.json."""
        missing = []
        for platform, key, tk in _iter_entities(entity_mappings):
            keys = set(STRINGS.get("entity", {}).get(platform, {}).keys())
            if tk not in keys:
                missing.append(f"[{platform}] {key} → translation_key='{tk}'")
        assert not missing, (
            f"{len(missing)} encje bez klucza w strings.json:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_all_translation_keys_in_en_json(self, entity_mappings):
        """Every translation_key must exist in translations/en.json."""
        missing = []
        for platform, key, tk in _iter_entities(entity_mappings):
            keys = set(EN.get("entity", {}).get(platform, {}).keys())
            if tk not in keys:
                missing.append(f"[{platform}] {key} → translation_key='{tk}'")
        assert not missing, (
            f"{len(missing)} encje bez klucza w en.json:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_all_translation_keys_in_pl_json(self, entity_mappings):
        """Every translation_key must exist in translations/pl.json."""
        missing = []
        for platform, key, tk in _iter_entities(entity_mappings):
            keys = set(PL.get("entity", {}).get(platform, {}).keys())
            if tk not in keys:
                missing.append(f"[{platform}] {key} → translation_key='{tk}'")
        assert not missing, (
            f"{len(missing)} encje bez klucza w pl.json:\n"
            + "\n".join(f"  {m}" for m in missing)
        )


class TestEntityNames:
    """Verify all entity names are human-readable, not raw keys or generics."""

    def test_no_empty_names_in_en(self, entity_mappings):
        """Every entity must have a non-empty name in en.json."""
        missing = []
        for platform, key, tk in _iter_entities(entity_mappings):
            en_ents = EN.get("entity", {}).get(platform, {})
            name = en_ents.get(tk, {}).get("name", "") if tk in en_ents else ""
            if not name:
                missing.append(f"[{platform}] {key} (tk='{tk}'): pusta nazwa EN")
        assert not missing, (
            f"{len(missing)} encji z pustą nazwą EN:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_no_empty_names_in_pl(self, entity_mappings):
        """Every entity must have a non-empty name in pl.json."""
        missing = []
        for platform, key, tk in _iter_entities(entity_mappings):
            pl_ents = PL.get("entity", {}).get(platform, {})
            name = pl_ents.get(tk, {}).get("name", "") if tk in pl_ents else ""
            if not name:
                missing.append(f"[{platform}] {key} (tk='{tk}'): pusta nazwa PL")
        assert not missing, (
            f"{len(missing)} encji z pustą nazwą PL:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_no_names_with_underscores_in_en(self, entity_mappings):
        """Entity names must be human-readable, not raw keys with underscores.

        A name like 'supply_air_temperature' indicates the translation key
        leaked through instead of a proper label like 'Supply Air Temperature'.
        """
        bad = []
        for platform, key, tk in _iter_entities(entity_mappings):
            en_ents = EN.get("entity", {}).get(platform, {})
            name = en_ents.get(tk, {}).get("name", "") if tk in en_ents else ""
            if "_" in name:
                bad.append(f"[{platform}] {key}: nazwa='{name}' (zawiera podkreślenie)")
        assert not bad, (
            f"{len(bad)} encji z podkreśleniem w nazwie (surowy klucz?):\n"
            + "\n".join(f"  {m}" for m in bad)
        )

    def test_no_generic_fallback_names(self, entity_mappings):
        """Names must not be generic fallbacks like 'Problem 27' or 'Sensor 15'.

        Such names appear when HA cannot resolve the translation and falls back
        to using the device class + entity number.
        """
        import re
        generic_pattern = re.compile(
            r"^(problem|sensor|switch|select|number|binary sensor|text|time)\s+\d+$",
            re.IGNORECASE,
        )
        bad = []
        for platform, key, tk in _iter_entities(entity_mappings):
            for lang, trans in [("EN", EN), ("PL", PL)]:
                ents = trans.get("entity", {}).get(platform, {})
                name = ents.get(tk, {}).get("name", "") if tk in ents else ""
                if name and generic_pattern.match(name.strip()):
                    bad.append(f"[{lang}][{platform}] {key}: nazwa='{name}'")
        assert not bad, (
            f"{len(bad)} encji z generyczną nazwą:\n"
            + "\n".join(f"  {m}" for m in bad)
        )

    def test_no_orphaned_sensor_translations(self, entity_mappings):
        """All sensor translation keys in en.json must be referenced by an entity.

        Accounts for special sensor classes outside entity_mappings:
        - 'error_codes': ThesslaGreenErrorCodesSensor
        - 'active_errors': ThesslaGreenActiveErrorsSensor (uses _attr_name, no tk)
        """
        # Translation keys used via SENSOR_ENTITY_MAPPINGS (may differ from mapping key)
        mapping_tks = {
            data.get("translation_key", key) if isinstance(data, dict) else key
            for key, data in entity_mappings["sensor"].items()
        }
        # Known special sensor classes with their translation keys
        special_sensor_tks = {"error_codes"}

        valid_tks = mapping_tks | special_sensor_tks
        en_sensor_tks = set(EN.get("entity", {}).get("sensor", {}).keys())

        orphaned = en_sensor_tks - valid_tks
        assert not orphaned, (
            "Osierocone klucze w entity.sensor en.json (żadna encja ich nie używa):\n"
            + "\n".join(f"  '{k}'" for k in sorted(orphaned))
        )


class TestSelectStateTranslations:
    """Verify select entity options have translations for all states."""

    def test_select_states_match_en_and_pl(self):
        """All select states in en.json must also exist in pl.json."""
        en_selects = EN.get("entity", {}).get("select", {})
        pl_selects = PL.get("entity", {}).get("select", {})

        missing = []
        for key, val in en_selects.items():
            en_states = set(val.get("state", {}).keys())
            pl_states = set(pl_selects.get(key, {}).get("state", {}).keys())
            diff = en_states - pl_states
            if diff:
                missing.append(f"select.{key}: brak stanów PL: {sorted(diff)}")

        assert not missing, (
            f"{len(missing)} select bez pełnych tłumaczeń PL:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_binary_sensor_states_match_en_and_pl(self):
        """All binary_sensor states in en.json must also exist in pl.json."""
        en_bs = EN.get("entity", {}).get("binary_sensor", {})
        pl_bs = PL.get("entity", {}).get("binary_sensor", {})

        missing = []
        for key, val in en_bs.items():
            en_states = set(val.get("state", {}).keys())
            pl_states = set(pl_bs.get(key, {}).get("state", {}).keys())
            diff = en_states - pl_states
            if diff:
                missing.append(f"binary_sensor.{key}: brak stanów PL: {sorted(diff)}")

        assert not missing, (
            f"{len(missing)} binary_sensor bez pełnych tłumaczeń PL:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_sensor_states_match_en_and_pl(self):
        """All sensor states in en.json must also exist in pl.json."""
        en_s = EN.get("entity", {}).get("sensor", {})
        pl_s = PL.get("entity", {}).get("sensor", {})

        missing = []
        for key, val in en_s.items():
            en_states = set(val.get("state", {}).keys())
            pl_states = set(pl_s.get(key, {}).get("state", {}).keys())
            diff = en_states - pl_states
            if diff:
                missing.append(f"sensor.{key}: brak stanów PL: {sorted(diff)}")

        assert not missing, (
            f"{len(missing)} sensor bez pełnych tłumaczeń PL:\n"
            + "\n".join(f"  {m}" for m in missing)
        )
