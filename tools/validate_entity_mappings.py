"""Validate consistency between entity mappings, translations and register definitions."""

from __future__ import annotations

import json
import sys
from contextlib import suppress
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


def main() -> int:
    if "homeassistant" not in sys.modules:
        with suppress(Exception):
            import tests.conftest  # noqa: F401

    from custom_components.thessla_green_modbus import entity_mappings as mappings_mod

    ENTITY_MAPPINGS = mappings_mod.ENTITY_MAPPINGS
    LEGACY_ENTITY_ID_ALIASES = mappings_mod.LEGACY_ENTITY_ID_ALIASES
    LEGACY_ENTITY_ID_OBJECT_ALIASES = mappings_mod.LEGACY_ENTITY_ID_OBJECT_ALIASES
    map_legacy_entity_id = mappings_mod.map_legacy_entity_id
    if hasattr(mappings_mod, "_alias_warning_logged"):
        mappings_mod._alias_warning_logged = True

    en = _load_json(CC_ROOT / "translations" / "en.json")
    pl = _load_json(CC_ROOT / "translations" / "pl.json")
    _ = _load_json(CC_ROOT / "strings.json")
    registers_data = _load_json(CC_ROOT / "registers" / "thessla_green_registers_full.json")

    en_entities: dict[str, dict[str, Any]] = en.get("entity", {})
    pl_entities: dict[str, dict[str, Any]] = pl.get("entity", {})

    register_names = {
        item.get("name")
        for item in registers_data.get("registers", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }

    errors: list[str] = []
    domain_keys: dict[str, set[str]] = {}
    for domain, entries in ENTITY_MAPPINGS.items():
        keys: set[str] = set()
        for key, definition in entries.items():
            tkey = str(definition.get("translation_key", key))
            keys.add(str(key))
            keys.add(tkey)
            keys.add(f"rekuperator_{key}")
            keys.add(f"rekuperator_{tkey}")
        domain_keys[domain] = keys

    ignored_orphan_translations = {("sensor", "error_codes")}
    synthetic_registers = {
        "device_clock",
        "heat_recovery_efficiency",
        "heat_recovery_power",
        "electrical_power",
    }

    # 1) Every mapping key has translation in pl + en
    for domain, key, definition in _iter_mapping_entries(ENTITY_MAPPINGS):
        tkey = definition.get("translation_key", key)
        if tkey not in en_entities.get(domain, {}):
            errors.append(
                f"ERROR: entity '{domain}.{tkey}' in entity_mappings missing from en.json"
            )
        if tkey not in pl_entities.get(domain, {}):
            errors.append(
                f"ERROR: entity '{domain}.{tkey}' in entity_mappings missing from pl.json"
            )

    # 2) No translation points to non-existing mapping entity
    for lang, entities in (("en", en_entities), ("pl", pl_entities)):
        for domain, domain_map in entities.items():
            if domain not in ENTITY_MAPPINGS:
                continue
            for tkey in domain_map:
                has_match = any(
                    definition.get("translation_key", key) == tkey
                    for key, definition in ENTITY_MAPPINGS[domain].items()
                )
                if not tkey.startswith("rekuperator_"):
                    continue
                if not has_match and (domain, tkey) not in ignored_orphan_translations:
                    errors.append(
                        f"ERROR: entity '{domain}.{tkey}' in {lang}.json missing from entity_mappings"
                    )

    # 3) Every register_name in mappings exists in register JSON
    for domain, key, definition in _iter_mapping_entries(ENTITY_MAPPINGS):
        register_name = definition.get("register", key)
        if (
            isinstance(register_name, str)
            and register_name not in register_names
            and register_name not in synthetic_registers
        ):
            errors.append(
                f"ERROR: register '{register_name}' used by '{domain}.{key}' missing from register schema"
            )

    # 3b) Include standalone *_MAPPING dictionaries as well.
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
            if domain:
                standalone_mapping_keys.add((domain, key))
                if key not in en_entities.get(domain, {}):
                    errors.append(
                        f"ERROR: entity '{domain}.{key}' in {var_name} missing from en.json"
                    )
                if key not in pl_entities.get(domain, {}):
                    errors.append(
                        f"ERROR: entity '{domain}.{key}' in {var_name} missing from pl.json"
                    )
                register_name = value.get("register", key)
                if (
                    isinstance(register_name, str)
                    and register_name not in register_names
                    and register_name not in synthetic_registers
                ):
                    errors.append(
                        f"ERROR: register '{register_name}' used by '{domain}.{key}' missing from register schema"
                    )

    # 4) Verify legacy aliases map to current entities
    def _verify_alias(alias_entity_id: str) -> None:
        mapped = map_legacy_entity_id(alias_entity_id)
        if mapped == alias_entity_id:
            domain, object_id = alias_entity_id.split(".", 1)
            if object_id in domain_keys.get(domain, set()):
                return
            errors.append(f"ERROR: legacy alias '{alias_entity_id}' has no valid mapping target")
            return
        if "." not in mapped:
            errors.append(
                f"ERROR: legacy alias '{alias_entity_id}' mapped to invalid entity id '{mapped}'"
            )
            return
        domain, object_id = mapped.split(".", 1)
        if domain not in domain_keys:
            return
        if object_id not in domain_keys[domain]:
            return

    for object_id in LEGACY_ENTITY_ID_OBJECT_ALIASES:
        _verify_alias(f"sensor.{object_id}")

    for suffix in LEGACY_ENTITY_ID_ALIASES:
        _verify_alias(f"sensor.legacy_{suffix}")

    # 5) Unique IDs must be unique within each domain.
    unique_ids_by_domain: dict[str, dict[str, str]] = {}
    for domain, key, definition in _iter_mapping_entries(ENTITY_MAPPINGS):
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

    if errors:
        for err in errors:
            print(err)
        return 1

    validated_count = sum(len(entries) for entries in ENTITY_MAPPINGS.values()) + len(
        standalone_mapping_keys
    )
    print(f"OK: {validated_count} entities validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
