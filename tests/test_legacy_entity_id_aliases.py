from custom_components.thessla_green_modbus.entity_mappings import map_legacy_entity_id


def test_map_legacy_entity_id_for_migrated_domains() -> None:
    """Legacy IDs should be translated to current domains/object IDs."""

    assert (
        map_legacy_entity_id("number.rekuperator_antifreeze_mode")
        == "sensor.rekuperator_antifreeze_mode"
    )
    assert (
        map_legacy_entity_id("sensor.rekuperator_bypass_mode_status")
        == "select.rekuperator_bypass_mode"
    )
    assert (
        map_legacy_entity_id("binary_sensor.rekuperator_on_off_panel_mode")
        == "switch.rekuperator_on_off_panel_mode"
    )


def test_map_legacy_entity_id_for_historical_register_renames() -> None:
    """Legacy entity IDs should handle renamed register suffixes."""

    assert (
        map_legacy_entity_id("number.rekuperator_bypass_coef_1")
        == "number.rekuperator_bypass_coef1"
    )
    assert (
        map_legacy_entity_id("number.rekuperator_bypass_coef_2")
        == "number.rekuperator_bypass_coef2"
    )
