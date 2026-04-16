"""Legacy entity-id alias definitions."""

from __future__ import annotations

import logging
import sys

_LOGGER = logging.getLogger(__name__)

# Map legacy entity suffixes to new domain and suffix pairs. Only a small
# subset of legacy names existed in early versions of the integration. These
# mappings allow services to transparently use the new entity IDs while warning
# users to update their automations.
LEGACY_ENTITY_ID_ALIASES: dict[str, tuple[str, str]] = {
    # Keys are suffixes of legacy entity_ids.
    # "number.rekuperator_predkosc" / "number.rekuperator_speed" → fan entity
    "predkosc": ("fan", "fan"),
    "speed": ("fan", "fan"),
}

# Exact object_id aliases used by earlier releases. These are matched before
# ``LEGACY_ENTITY_ID_ALIASES`` to avoid ambiguity for names ending with
# common suffixes like ``_mode``.
LEGACY_ENTITY_ID_OBJECT_ALIASES: dict[str, tuple[str, str]] = {
    # Legacy number entities migrated to read-only sensors.
    "rekuperator_antifreeze_mode": ("binary_sensor", "rekuperator_antifreeze_mode"),
    "rekuperator_comfort_mode": ("sensor", "rekuperator_comfort_mode"),
    "rekuperator_dac_supply": ("sensor", "rekuperator_dac_supply"),
    "rekuperator_dac_exhaust": ("sensor", "rekuperator_dac_exhaust"),
    "rekuperator_dac_heater": ("sensor", "rekuperator_dac_heater"),
    "rekuperator_dac_cooler": ("sensor", "rekuperator_dac_cooler"),
    "rekuperator_supply_air_flow": ("sensor", "rekuperator_supply_air_flow"),
    "rekuperator_exhaust_air_flow": ("sensor", "rekuperator_exhaust_air_flow"),
    "rekuperator_hood_supply_coef": ("number", "rekuperator_hood_supply_coef"),
    "rekuperator_hood_exhaust_coef": ("number", "rekuperator_hood_exhaust_coef"),
    "rekuperator_fan_speed_1_coef": ("number", "rekuperator_fan_speed_1_coef"),
    "rekuperator_fan_speed_2_coef": ("number", "rekuperator_fan_speed_2_coef"),
    "rekuperator_fan_speed_3_coef": ("number", "rekuperator_fan_speed_3_coef"),
    # Legacy status sensors migrated to select/switch controls.
    "rekuperator_mode": ("select", "rekuperator_mode"),
    "rekuperator_gwc_mode": ("sensor", "rekuperator_gwc_mode"),
    "rekuperator_season_mode": ("select", "rekuperator_season_mode"),
    "rekuperator_bypass_mode_status": ("sensor", "rekuperator_bypass_mode"),
    "rekuperator_on_off_panel_mode": ("switch", "rekuperator_on_off_panel_mode"),
    # Typo fix: antifreez_stage → antifreeze_stage (version 2.3.0)
    "rekuperator_antifreez_stage": ("sensor", "rekuperator_antifreeze_stage"),
    # Binary sensor renames (dp_ prefix added, key made more precise)
    "rekuperator_ahu_filter_overflow": ("binary_sensor", "rekuperator_dp_ahu_filter_overflow"),
    "rekuperator_duct_filter_overflow": ("binary_sensor", "rekuperator_dp_duct_filter_overflow"),
    "rekuperator_gwc_regeneration_active": ("binary_sensor", "rekuperator_gwc_regen_flag"),
    "rekuperator_central_heater_overprotection": ("binary_sensor", "rekuperator_post_heater_on"),
    "rekuperator_unit_operation_confirmation": ("binary_sensor", "rekuperator_info"),
    "rekuperator_water_heater_pump": ("binary_sensor", "rekuperator_duct_water_heater_pump"),
    # Sensor renames
    "rekuperator_maximum_percentage": ("sensor", "rekuperator_max_percentage"),
    "rekuperator_minimum_percentage": ("sensor", "rekuperator_min_percentage"),
    "rekuperator_time_period": ("sensor", "rekuperator_period"),
    "rekuperator_supply_flow_rate_m3_h": ("sensor", "rekuperator_supply_flow_rate"),
    "rekuperator_exhaust_flow_rate_m3_h": ("sensor", "rekuperator_exhaust_flow_rate"),
    "rekuperator_ahu_stop_alarm_code": ("sensor", "rekuperator_stop_ahu_code"),
    "rekuperator_active_errors": ("sensor", "rekuperator_stop_ahu_code"),
    "rekuperator_product_key_lock_date_day": ("sensor", "rekuperator_lock_date_00dd"),
    "rekuperator_comfort_mode_status": ("sensor", "rekuperator_comfort_mode"),
    # Switch renames
    "rekuperator_bypass_active": ("switch", "rekuperator_bypass_off"),
    "rekuperator_gwc_active": ("switch", "rekuperator_gwc_off"),
    "rekuperator_lock": ("switch", "rekuperator_lock_flag"),
    # Select renames
    "rekuperator_filter_check_day_of_week": ("select", "rekuperator_pres_check_day"),
    "rekuperator_filter_check_day_of_week_ext": ("select", "rekuperator_pres_check_day_4432"),
    "rekuperator_gwc_regeneration": ("select", "rekuperator_gwc_regen"),
    "rekuperator_filter_type": ("select", "rekuperator_filter_change"),
    # Time entity renames
    "rekuperator_filter_check_start_time": ("time", "rekuperator_pres_check_time"),
    "rekuperator_filter_check_start_time_ext": ("time", "rekuperator_pres_check_time_ggmm"),
    # Polish-language entity IDs (installations with HA language set to pl before 2026)
    "rekuperator_moc_odzysku_ciepla": ("sensor", "rekuperator_heat_recovery_power"),
    "rekuperator_sprawnosc_rekuperatora": ("sensor", "rekuperator_heat_recovery_efficiency"),
    "rekuperator_pobor_mocy_elektrycznej": ("sensor", "rekuperator_electrical_power"),
    "rekuperator_nazwa_urzadzenia": ("text", "rekuperator_device_name"),
    "rekuperator_predkosc_1": ("fan", "rekuperator_ventilation"),
    # Legacy split aliases for e_196_e_199 bitmask register
    "rekuperator_error_e196": ("binary_sensor", "rekuperator_e_196_e_199_e_196"),
    "rekuperator_error_e197": ("binary_sensor", "rekuperator_e_196_e_199_e_197"),
    "rekuperator_error_e198": ("binary_sensor", "rekuperator_e_196_e_199_e_198"),
    "rekuperator_error_e199": ("binary_sensor", "rekuperator_e_196_e_199_e_199"),
    # Product key lock date split fields
    "rekuperator_product_key_lock_date_month": ("sensor", "rekuperator_lock_date_00mm"),
}

_alias_warning_logged = False


def map_legacy_entity_id(entity_id: str) -> str:
    """Map a legacy entity ID to the new format.

    If the provided ``entity_id`` matches one of the known legacy aliases, the
    corresponding new entity ID is returned and a warning is logged exactly
    once to inform the user about the change.
    """

    global _alias_warning_logged

    if "." not in entity_id:
        return entity_id

    # Read the warning flag through the parent module so that test
    # monkeypatching on the parent (e.g. ``monkeypatch.setattr(em, ...)``)
    # propagates here at call time.
    _parent = sys.modules.get(__package__)
    _already_logged: bool = (
        getattr(_parent, "_alias_warning_logged", False) if _parent is not None else _alias_warning_logged
    )

    _domain, object_id = entity_id.split(".", 1)
    if object_id in LEGACY_ENTITY_ID_OBJECT_ALIASES:
        new_domain, new_object_id = LEGACY_ENTITY_ID_OBJECT_ALIASES[object_id]
        new_entity_id = f"{new_domain}.{new_object_id}"
        if not _already_logged:
            _LOGGER.warning(
                "Legacy entity ID '%s' detected. Please update automations to use '%s'.",
                entity_id,
                new_entity_id,
            )
            _alias_warning_logged = True
            if _parent is not None:
                _parent._alias_warning_logged = True  # type: ignore[attr-defined]
        return new_entity_id

    suffix = object_id.rsplit("_", 1)[-1]
    if suffix not in LEGACY_ENTITY_ID_ALIASES:
        return entity_id

    new_domain, new_suffix = LEGACY_ENTITY_ID_ALIASES[suffix]
    parts = object_id.split("_")
    new_object_id = "_".join([*parts[:-1], new_suffix]) if len(parts) > 1 else new_suffix
    new_entity_id = f"{new_domain}.{new_object_id}"

    if not _already_logged:
        _LOGGER.warning(
            "Legacy entity ID '%s' detected. Please update automations to use '%s'.",
            entity_id,
            new_entity_id,
        )
        _alias_warning_logged = True
        if _parent is not None:
            _parent._alias_warning_logged = True  # type: ignore[attr-defined]

    return new_entity_id


__all__ = [
    "LEGACY_ENTITY_ID_ALIASES",
    "LEGACY_ENTITY_ID_OBJECT_ALIASES",
    "map_legacy_entity_id",
]
