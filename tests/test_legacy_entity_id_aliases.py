from custom_components.thessla_green_modbus.mappings import map_legacy_entity_id


def test_map_legacy_entity_id_for_migrated_domains() -> None:
    """Legacy IDs should be translated to current domains/object IDs."""

    assert (
        map_legacy_entity_id("number.rekuperator_antifreeze_mode")
        == "binary_sensor.rekuperator_antifreeze_mode"
    )
    assert (
        map_legacy_entity_id("sensor.rekuperator_bypass_mode_status")
        == "sensor.rekuperator_bypass_mode"
    )
    assert (
        map_legacy_entity_id("binary_sensor.rekuperator_on_off_panel_mode")
        == "switch.rekuperator_on_off_panel_mode"
    )


def test_map_legacy_entity_id_for_historical_register_renames() -> None:
    """Legacy entity IDs that were never produced (broken register names) should pass through unchanged."""

    # bypass_coef_1 / bypass_coef_2 entities were never actually created in HA
    # because the JSON register was named bypass_coef1/2 (without underscore) and the
    # address lookup failed.  The aliases have been removed; the name passes through.
    assert (
        map_legacy_entity_id("number.rekuperator_bypass_coef_1")
        == "number.rekuperator_bypass_coef_1"
    )
    assert (
        map_legacy_entity_id("number.rekuperator_bypass_coef_2")
        == "number.rekuperator_bypass_coef_2"
    )


def test_map_legacy_entity_id_for_split_error_bitmask_aliases() -> None:
    """Legacy per-error aliases should map to current e_196_e_199 bit keys."""

    assert (
        map_legacy_entity_id("binary_sensor.rekuperator_error_e196")
        == "binary_sensor.rekuperator_e_196_e_199_e_196"
    )
    assert (
        map_legacy_entity_id("binary_sensor.rekuperator_error_e197")
        == "binary_sensor.rekuperator_e_196_e_199_e_197"
    )
    assert (
        map_legacy_entity_id("binary_sensor.rekuperator_error_e198")
        == "binary_sensor.rekuperator_e_196_e_199_e_198"
    )
    assert (
        map_legacy_entity_id("binary_sensor.rekuperator_error_e199")
        == "binary_sensor.rekuperator_e_196_e_199_e_199"
    )


def test_map_legacy_entity_id_for_extended_filter_check_aliases() -> None:
    """Legacy *_ext entities should map to current extended keys."""

    assert (
        map_legacy_entity_id("select.rekuperator_filter_check_day_of_week_ext")
        == "select.rekuperator_pres_check_day_4432"
    )
    assert (
        map_legacy_entity_id("time.rekuperator_filter_check_start_time")
        == "time.rekuperator_pres_check_time"
    )
    assert (
        map_legacy_entity_id("time.rekuperator_filter_check_start_time_ext")
        == "time.rekuperator_pres_check_time_ggmm"
    )


def test_map_legacy_entity_id_for_lock_date_month_alias() -> None:
    """Legacy split month lock date entity should map to current key."""

    assert (
        map_legacy_entity_id("sensor.rekuperator_product_key_lock_date_month")
        == "sensor.rekuperator_lock_date_00mm"
    )
