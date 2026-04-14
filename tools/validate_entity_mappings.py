"""Validate consistency between entity mappings, translations and register definitions."""

from __future__ import annotations

import json
import sys
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
        try:
            import tests.conftest  # noqa: F401
        except Exception:
            pass

    from custom_components.thessla_green_modbus.entity_mappings import (
        ENTITY_MAPPINGS,
        LEGACY_ENTITY_ID_ALIASES,
        LEGACY_ENTITY_ID_OBJECT_ALIASES,
        map_legacy_entity_id,
    )

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
    warnings: list[str] = []

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
            errors.append(f"Missing en translation: {domain}.{tkey} (mapping key: {key})")
        if tkey not in pl_entities.get(domain, {}):
            errors.append(f"Missing pl translation: {domain}.{tkey} (mapping key: {key})")

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
                if not has_match and (domain, tkey) not in ignored_orphan_translations:
                    errors.append(f"Orphan {lang} translation: {domain}.{tkey}")

    # 3) Every register_name in mappings exists in register JSON
    for domain, key, definition in _iter_mapping_entries(ENTITY_MAPPINGS):
        register_name = definition.get("register", key)
        if (
            isinstance(register_name, str)
            and register_name not in register_names
            and register_name not in synthetic_registers
        ):
            errors.append(
                f"Unknown register in mapping: domain={domain} key={key} register={register_name}"
            )

    # 4) Verify legacy aliases map to current entities
    def _verify_alias(alias_entity_id: str) -> None:
        mapped = map_legacy_entity_id(alias_entity_id)
        if mapped == alias_entity_id:
            domain, object_id = alias_entity_id.split(".", 1)
            if object_id in domain_keys.get(domain, set()):
                return
            errors.append(f"Legacy alias not mapped: {alias_entity_id}")
            return
        if "." not in mapped:
            errors.append(f"Legacy alias mapped to invalid id: {alias_entity_id} -> {mapped}")
            return
        domain, object_id = mapped.split(".", 1)
        if domain not in domain_keys:
            # Some aliases point to domains without mapping dictionaries
            # (e.g. fan/climate) and are validated elsewhere.
            warnings.append(f"LEGACY_TARGET_DOMAIN_UNCHECKED: {alias_entity_id} -> {mapped}")
            return
        if object_id not in domain_keys[domain]:
            errors.append(f"Legacy alias maps to missing entity: {alias_entity_id} -> {mapped}")

    for object_id in LEGACY_ENTITY_ID_OBJECT_ALIASES:
        warnings.append(f"LEGACY_OBJECT_ALIAS: {object_id}")
        _verify_alias(f"sensor.{object_id}")

    for suffix in LEGACY_ENTITY_ID_ALIASES:
        warnings.append(f"LEGACY_SUFFIX_ALIAS: {suffix}")
        _verify_alias(f"sensor.legacy_{suffix}")

    for warning in warnings:
        print(f"[LEGACY] {warning}")

    if errors:
        print("\nEntity mapping validation FAILED:\n")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Entity mapping validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
