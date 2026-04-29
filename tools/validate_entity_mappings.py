"""Validate consistency between entity mappings, translations and register definitions."""

from __future__ import annotations

import json
import sys
import types
from contextlib import suppress
from enum import StrEnum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CC_ROOT = ROOT / "custom_components" / "thessla_green_modbus"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _iter_mapping_entries(entity_mappings: dict[str, dict[str, dict[str, Any]]]):
    for domain, entries in entity_mappings.items():
        for key, definition in entries.items():
            yield domain, key, definition


def _ensure_homeassistant_importable() -> None:
    try:
        import homeassistant.const  # noqa: F401
        return
    except ModuleNotFoundError:
        with suppress(Exception):
            from tests.platform_stubs import install_common_ha_stubs

            install_common_ha_stubs()

    if "homeassistant.const" not in sys.modules:
        sys.modules["homeassistant.const"] = types.ModuleType("homeassistant.const")

    class _Platform(StrEnum):
        BINARY_SENSOR = "binary_sensor"
        CLIMATE = "climate"
        FAN = "fan"
        NUMBER = "number"
        SELECT = "select"
        SENSOR = "sensor"
        SWITCH = "switch"
        TEXT = "text"
        TIME = "time"

    ha_mod = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    ha_const_mod = sys.modules["homeassistant.const"]
    ha_const_mod.Platform = getattr(ha_const_mod, "Platform", _Platform)
    ha_const_mod.CONF_NAME = getattr(ha_const_mod, "CONF_NAME", "name")
    ha_const_mod.PERCENTAGE = getattr(ha_const_mod, "PERCENTAGE", "%")
    ha_mod.const = ha_const_mod
    sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
    ha_helpers_entity = sys.modules.setdefault(
        "homeassistant.helpers.entity", types.ModuleType("homeassistant.helpers.entity")
    )
    if not hasattr(ha_helpers_entity, "EntityCategory"):

        class _EntityCategory(StrEnum):
            CONFIG = "config"
            DIAGNOSTIC = "diagnostic"

        ha_helpers_entity.EntityCategory = _EntityCategory


def _load_validation_inputs() -> tuple[object, dict[str, Any], dict[str, Any], set[str]]:
    from custom_components.thessla_green_modbus import mappings as mappings_mod

    en = _load_json(CC_ROOT / "translations" / "en.json")
    pl = _load_json(CC_ROOT / "translations" / "pl.json")
    _load_json(CC_ROOT / "strings.json")
    registers_data = _load_json(CC_ROOT / "registers" / "thessla_green_registers_full.json")
    register_names = {
        item.get("name")
        for item in registers_data.get("registers", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    return mappings_mod, en, pl, register_names


def _collect_domain_keys(entity_mappings: dict[str, dict[str, dict[str, Any]]]) -> dict[str, set[str]]:
    domain_keys: dict[str, set[str]] = {}
    for domain, entries in entity_mappings.items():
        keys: set[str] = set()
        for key, definition in entries.items():
            tkey = str(definition.get("translation_key", key))
            keys.add(str(key))
            keys.add(tkey)
            keys.add(f"rekuperator_{key}")
            keys.add(f"rekuperator_{tkey}")
        domain_keys[domain] = keys
    return domain_keys


def _validate_translations(
    entity_mappings: dict[str, dict[str, dict[str, Any]]],
    en_entities: dict[str, dict[str, Any]],
    pl_entities: dict[str, dict[str, Any]],
    ignored_orphan_translations: set[tuple[str, str]],
) -> list[str]:
    errors: list[str] = []
    for domain, key, definition in _iter_mapping_entries(entity_mappings):
        tkey = definition.get("translation_key", key)
        if tkey not in en_entities.get(domain, {}):
            errors.append(f"ERROR: entity '{domain}.{tkey}' in entity_mappings missing from en.json")
        if tkey not in pl_entities.get(domain, {}):
            errors.append(f"ERROR: entity '{domain}.{tkey}' in entity_mappings missing from pl.json")

    for lang, entities in (("en", en_entities), ("pl", pl_entities)):
        for domain, domain_map in entities.items():
            if domain not in entity_mappings:
                continue
            for tkey in domain_map:
                has_match = any(
                    definition.get("translation_key", key) == tkey
                    for key, definition in entity_mappings[domain].items()
                )
                if not tkey.startswith("rekuperator_"):
                    continue
                if not has_match and (domain, tkey) not in ignored_orphan_translations:
                    errors.append(
                        f"ERROR: entity '{domain}.{tkey}' in {lang}.json missing from entity_mappings"
                    )
    return errors


def _validate_register_references(
    entity_mappings: dict[str, dict[str, dict[str, Any]]], register_names: set[str], synthetic_registers: set[str]
) -> list[str]:
    errors: list[str] = []
    for domain, key, definition in _iter_mapping_entries(entity_mappings):
        register_name = definition.get("register", key)
        if (
            isinstance(register_name, str)
            and register_name not in register_names
            and register_name not in synthetic_registers
        ):
            errors.append(
                f"ERROR: register '{register_name}' used by '{domain}.{key}' missing from register schema"
            )
    return errors


def _validate_standalone_mappings(
    mappings_mod: object,
    en_entities: dict[str, dict[str, Any]],
    pl_entities: dict[str, dict[str, Any]],
    register_names: set[str],
    synthetic_registers: set[str],
) -> tuple[list[str], set[tuple[str, str]]]:
    errors: list[str] = []
    standalone_mapping_keys: set[tuple[str, str]] = set()
    for var_name, mapping in vars(mappings_mod).items():
        if not var_name.endswith("_MAPPING") or not isinstance(mapping, dict):
            continue
        if var_name == "ENTITY_MAPPINGS":
            continue
        for key, value in mapping.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            domain = str(value.get("domain", "")).strip()
            if not domain:
                continue
            standalone_mapping_keys.add((domain, key))
            if key not in en_entities.get(domain, {}):
                errors.append(f"ERROR: entity '{domain}.{key}' in {var_name} missing from en.json")
            if key not in pl_entities.get(domain, {}):
                errors.append(f"ERROR: entity '{domain}.{key}' in {var_name} missing from pl.json")
            register_name = value.get("register", key)
            if (
                isinstance(register_name, str)
                and register_name not in register_names
                and register_name not in synthetic_registers
            ):
                errors.append(
                    f"ERROR: register '{register_name}' used by '{domain}.{key}' missing from register schema"
                )
    return errors, standalone_mapping_keys


def _validate_unique_ids(entity_mappings: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    unique_ids_by_domain: dict[str, dict[str, str]] = {}
    for domain, key, definition in _iter_mapping_entries(entity_mappings):
        unique_id = definition.get("unique_id")
        if not isinstance(unique_id, str) or not unique_id:
            continue
        by_domain = unique_ids_by_domain.setdefault(domain, {})
        existing = by_domain.get(unique_id)
        if existing is not None:
            errors.append(
                f"ERROR: duplicate unique_id '{unique_id}' in domain '{domain}' for '{existing}' and '{key}'"
            )
        else:
            by_domain[unique_id] = key
    return errors


def _report_errors(errors: list[str]) -> int:
    if errors:
        for err in errors:
            print(err)
        return 1
    return 0


def main() -> int:
    _ensure_homeassistant_importable()
    mappings_mod, en, pl, register_names = _load_validation_inputs()
    entity_mappings = mappings_mod.ENTITY_MAPPINGS

    en_entities: dict[str, dict[str, Any]] = en.get("entity", {})
    pl_entities: dict[str, dict[str, Any]] = pl.get("entity", {})

    _collect_domain_keys(entity_mappings)
    ignored_orphan_translations = {("sensor", "error_codes")}
    synthetic_registers = {
        "device_clock",
        "heat_recovery_efficiency",
        "heat_recovery_power",
        "electrical_power",
    }

    errors: list[str] = []
    errors.extend(
        _validate_translations(entity_mappings, en_entities, pl_entities, ignored_orphan_translations)
    )
    errors.extend(_validate_register_references(entity_mappings, register_names, synthetic_registers))
    standalone_errors, standalone_mapping_keys = _validate_standalone_mappings(
        mappings_mod, en_entities, pl_entities, register_names, synthetic_registers
    )
    errors.extend(standalone_errors)
    errors.extend(_validate_unique_ids(entity_mappings))

    if _report_errors(errors):
        return 1

    validated_count = sum(len(entries) for entries in entity_mappings.values()) + len(standalone_mapping_keys)
    print(f"OK: {validated_count} entities validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
