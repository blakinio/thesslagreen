"""Tests for runtime register value validation."""

from custom_components.thessla_green_modbus.register_map import RegisterMapEntry


def test_enum_unknown_value_is_preserved_for_read_entities() -> None:
    """Read entities should keep undocumented enum values instead of dropping state."""
    entry = RegisterMapEntry(
        name="on_off_panel_mode",
        register_type="holding_registers",
        address=4276,
        data_type="enum",
        min_value=None,
        max_value=None,
        enum_values={"OFF", "ON"},
        model_variants=("AirPack Home",),
        entity_domain="switch",
    )

    assert entry.validate(16) == 16


def test_enum_unknown_value_raises_for_non_read_entities() -> None:
    """Non-entity/unsupported domains should keep strict enum validation."""
    entry = RegisterMapEntry(
        name="strict_register",
        register_type="holding_registers",
        address=9999,
        data_type="enum",
        min_value=None,
        max_value=None,
        enum_values={"a", "b"},
        model_variants=("AirPack Home",),
        entity_domain="select",
    )

    try:
        entry.validate(7)
    except ValueError as err:
        assert "Unexpected enum value" in str(err)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for strict enum validation")
