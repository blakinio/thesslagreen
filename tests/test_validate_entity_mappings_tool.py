"""Tests for tools.validate_entity_mappings helper validations."""

from tools import validate_entity_mappings as tool


def test_validate_unique_ids_detects_duplicates() -> None:
    entity_mappings = {
        "sensor": {
            "a": {"unique_id": "dup"},
            "b": {"unique_id": "dup"},
            "c": {"unique_id": "ok"},
        }
    }

    errors = tool._validate_unique_ids(entity_mappings)

    assert errors == [
        "ERROR: duplicate unique_id 'dup' in domain 'sensor' for 'a' and 'b'"
    ]


def test_validate_register_references_ignores_synthetic_registers() -> None:
    entity_mappings = {
        "sensor": {
            "a": {"register": "known"},
            "b": {"register": "device_clock"},
            "c": {"register": "missing"},
        }
    }

    errors = tool._validate_register_references(
        entity_mappings,
        register_names={"known"},
        synthetic_registers={"device_clock"},
    )

    assert errors == [
        "ERROR: register 'missing' used by 'sensor.c' missing from register schema"
    ]
