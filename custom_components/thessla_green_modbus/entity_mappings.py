"""Entity mapping definitions for the ThesslaGreen Modbus integration.

Most entity descriptions are generated from the bundled register
metadata and can be extended or overridden by the dictionaries defined in
this module. This keeps the mapping definitions in sync with the register
specification while still allowing manual tweaks (for example to change
icons or alter the entity domain).

The module also provides helpers for handling legacy entity IDs that
were renamed in newer versions of the integration.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.core import HomeAssistant

try:  # pragma: no cover - handle absence of Home Assistant
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.helpers.entity import EntityCategory
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed in tests without HA

    class EntityCategory:  # type: ignore[no-redef]
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"

    class BinarySensorDeviceClass:  # type: ignore[no-redef]
        RUNNING = "running"
        OPENING = "opening"
        POWER = "power"
        HEAT = "heat"
        CONNECTIVITY = "connectivity"
        PROBLEM = "problem"
        SAFETY = "safety"
        MOISTURE = "moisture"

    class SensorDeviceClass:  # type: ignore[no-redef]
        TEMPERATURE = "temperature"
        VOLTAGE = "voltage"
        POWER = "power"
        ENERGY = "energy"
        EFFICIENCY = "efficiency"
        VOLUME_FLOW_RATE = "volume_flow_rate"

    class SensorStateClass:  # type: ignore[no-redef]
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"


try:  # pragma: no cover - use HA constants when available
    from homeassistant.const import (
        UnitOfElectricPotential,
        UnitOfPower,
        UnitOfTemperature,
        UnitOfTime,
        UnitOfVolumeFlowRate,
    )
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed only in tests

    class UnitOfElectricPotential:  # type: ignore[no-redef]
        VOLT = "V"

    class UnitOfPower:  # type: ignore[no-redef]
        WATT = "W"

    class UnitOfTemperature:  # type: ignore[no-redef]
        CELSIUS = "°C"

    class UnitOfTime:  # type: ignore[no-redef]
        HOURS = "h"
        DAYS = "d"
        SECONDS = "s"

    class UnitOfVolumeFlowRate:  # type: ignore[no-redef]
        CUBIC_METERS_PER_HOUR = "m³/h"


try:  # pragma: no cover - fallback for tests without full HA constants
    from homeassistant.const import PERCENTAGE
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed only in tests
    PERCENTAGE = "%"

try:  # pragma: no cover - optional during isolated tests
    from .registers.loader import get_all_registers
except (ImportError, AttributeError):  # pragma: no cover - fallback when stubs incomplete

    def get_all_registers(*_args, **_kwargs):
        return []


from .const import SPECIAL_FUNCTION_MAP, coil_registers, discrete_input_registers, holding_registers
from .utils import _to_snake_case

_LOGGER = logging.getLogger(__name__)
_REGISTER_INFO_CACHE: dict[str, dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# Legacy entity ID mapping
# ---------------------------------------------------------------------------
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
    "rekuperator_gwc_regeneration": ("select", "rekuperator_gwc_regen"),
    "rekuperator_filter_type": ("select", "rekuperator_filter_change"),
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

    domain, object_id = entity_id.split(".", 1)
    if object_id in LEGACY_ENTITY_ID_OBJECT_ALIASES:
        new_domain, new_object_id = LEGACY_ENTITY_ID_OBJECT_ALIASES[object_id]
        new_entity_id = f"{new_domain}.{new_object_id}"
        if not _alias_warning_logged:
            _LOGGER.warning(
                "Legacy entity ID '%s' detected. Please update automations to use '%s'.",
                entity_id,
                new_entity_id,
            )
            _alias_warning_logged = True
        return new_entity_id

    suffix = object_id.rsplit("_", 1)[-1]
    if suffix not in LEGACY_ENTITY_ID_ALIASES:
        return entity_id

    new_domain, new_suffix = LEGACY_ENTITY_ID_ALIASES[suffix]
    parts = object_id.split("_")
    new_object_id = "_".join(parts[:-1] + [new_suffix]) if len(parts) > 1 else new_suffix
    new_entity_id = f"{new_domain}.{new_object_id}"

    if not _alias_warning_logged:
        _LOGGER.warning(
            "Legacy entity ID '%s' detected. Please update automations " "to use '%s'.",
            entity_id,
            new_entity_id,
        )
        _alias_warning_logged = True

    return new_entity_id


def _infer_icon(name: str, unit: str | None) -> str:
    """Return a default icon based on register name and unit."""
    if unit == "°C" or "temperature" in name:
        return "mdi:thermometer"
    if unit in {"m³/h", "m3/h"} or "flow" in name or "fan" in name:
        return "mdi:fan"
    if unit == PERCENTAGE or "percentage" in name:
        return "mdi:percent-outline"
    if unit in {"s", "min", "h", "d"} or "time" in name:
        return "mdi:timer"
    if unit == "V":
        return "mdi:sine-wave"
    return "mdi:numeric"


def _get_register_info(name: str) -> dict[str, Any] | None:
    """Return register metadata, handling numeric suffixes."""
    global _REGISTER_INFO_CACHE
    if _REGISTER_INFO_CACHE is None:
        _REGISTER_INFO_CACHE = {}
        for reg in get_all_registers():
            if not reg.name:
                continue
            scale = reg.multiplier or 1
            step = reg.resolution or scale
            _REGISTER_INFO_CACHE[reg.name] = {
                "access": reg.access,
                "min": reg.min,
                "max": reg.max,
                "unit": reg.unit,
                "information": reg.information,
                "scale": scale,
                "step": step,
            }
    info = _REGISTER_INFO_CACHE.get(name)
    if info is None and (suffix := name.rsplit("_", 1)) and len(suffix) > 1 and suffix[1].isdigit():
        info = _REGISTER_INFO_CACHE.get(suffix[0])
    return info


def _parse_states(value: str | None) -> dict[str, int] | None:
    """Parse ``"0 - off; 1 - on"`` style state strings into a mapping."""
    if not value or "-" not in value:
        return None
    states: dict[str, int] = {}
    for part in value.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            num_str, label = part.split("-", 1)
            number = int(num_str.strip())
        except ValueError:
            continue
        states[_to_snake_case(label.strip())] = number
    return states or None


def _load_number_mappings() -> dict[str, dict[str, Any]]:
    """Build number entity configurations from register metadata."""

    number_configs: dict[str, dict[str, Any]] = {}

    for reg in get_all_registers():
        if reg.function != 3 or not reg.name:
            continue
        # String-type registers span multiple registers and store ASCII data.
        # They cannot be meaningfully represented as a single numeric value,
        # so skip them here (e.g. ``device_name`` at holding address 8144).
        if reg.extra and reg.extra.get("type") == "string":
            continue
        register = reg.name
        info = _get_register_info(register)
        if not info:
            continue

        # Some writable holding registers are also exposed as sensors for
        # display/diagnostics. Keep creating number entities for writable
        # registers so users can still edit configuration values. For
        # read-only sensor registers we skip number creation to avoid dead
        # controls.
        if register in SENSOR_ENTITY_MAPPINGS and "W" not in (info.get("access") or ""):
            continue

        # Skip registers already handled by select/switch platforms to avoid
        # creating a duplicate Number entity alongside the correct entity type.
        if register in SELECT_ENTITY_MAPPINGS:
            continue
        if register in SWITCH_ENTITY_MAPPINGS:
            continue

        # Skip BCD date/time registers — they store encoded year/month/day
        # fields with format-descriptor "units" (e.g. "RRMM", "DDTT") that
        # are not valid measurement units and must not be editable numbers.
        if register.startswith("date_time"):
            continue

        # Skip diagnostic/error/fault registers (E/S/F codes and alarm/error flags)
        if re.match(r"[sef](?:_|\d)", register) or register in {"alarm", "error"}:
            continue

        # Skip BCD time registers (schedule/airing/GWC-regen timeslots) – they
        # decode to "HH:MM" strings, not floats, and are exposed as sensors.
        from .utils import BCD_TIME_PREFIXES

        if any(register.startswith(prefix) for prefix in BCD_TIME_PREFIXES):
            continue

        # Skip schedule intensity/airflow setting registers — they store AATT
        # packed values and are exposed as select entities (0–100 % in 10 %
        # increments), not editable number inputs.
        if register.startswith(("setting_summer_", "setting_winter_")):
            continue

        # Skip registers with enumerated states – handled as binary/select
        if _parse_states(info.get("unit")):
            continue

        # Skip registers with JSON enum field — handled as select/switch/binary_sensor
        if reg.enum and not (reg.extra and reg.extra.get("bitmask")):
            continue

        # Only expose registers that have a Number translation entry.
        # This mirrors the whitelist approach used by binary_sensor/switch/select
        # and prevents unnamed "Rekuperator" entities for reserved or
        # undocumented registers (e.g. reserved_8145–reserved_8151, lock_pass_2).
        if register not in _number_translation_keys():
            continue

        cfg: dict[str, Any] = {
            "unit": info.get("unit"),
            "step": info.get("step", 1),
            "scale": info.get("scale", 1),
        }
        if info.get("min") is not None:
            cfg["min"] = info["min"]
        if info.get("max") is not None:
            cfg["max"] = info["max"]

        number_configs[register] = cfg

    for register, override in NUMBER_OVERRIDES.items():
        number_configs.setdefault(register, {}).update(override)

    return number_configs


# Manual overrides for number entities (icons, custom units, etc.)
NUMBER_OVERRIDES: dict[str, dict[str, Any]] = {
    # Temperature setpoints — multiplier=0.5, so physical = raw × 0.5 (°C)
    # PDF raw range 20–90 → physical 10–45 °C, step 0.5 °C
    "supply_air_temperature_manual": {"icon": "mdi:thermometer-plus", "min": 10, "max": 45, "step": 0.5},
    "supply_air_temperature_temporary": {"icon": "mdi:thermometer-plus", "min": 10, "max": 45, "step": 0.5},
    "supply_air_temperature_temporary_4404": {"icon": "mdi:thermometer-plus", "min": 10, "max": 45, "step": 0.5},
    # PDF raw 10–40 → physical 5–20 °C
    "min_bypass_temperature": {"icon": "mdi:thermometer-low", "min": 5, "max": 20, "step": 0.5},
    # PDF raw 30–60 → physical 15–30 °C
    "air_temperature_summer_free_heating": {"icon": "mdi:thermometer", "min": 15, "max": 30, "step": 0.5},
    "air_temperature_summer_free_cooling": {"icon": "mdi:thermometer", "min": 15, "max": 30, "step": 0.5},
    # PDF raw 0–20 → physical 0–10 °C
    "min_gwc_air_temperature": {"icon": "mdi:thermometer-low", "min": 0, "max": 10, "step": 0.5},
    # PDF raw 30–80 → physical 15–40 °C
    "max_gwc_air_temperature": {"icon": "mdi:thermometer-high", "min": 15, "max": 40, "step": 0.5},
    # PDF raw 0–10 → physical 0–5 °C
    "delta_t_gwc": {"icon": "mdi:thermometer-lines", "min": 0, "max": 5, "step": 0.5},
    # Air flow intensity setpoints (%), multiplier=1
    "air_flow_rate_manual": {"icon": "mdi:fan", "min": 10, "max": 100, "step": 1},
    "air_flow_rate_temporary": {"icon": "mdi:fan", "min": 10, "max": 100, "step": 1},
    "air_flow_rate_temporary_4401": {"icon": "mdi:fan", "min": 10, "max": 100, "step": 1},
    "max_supply_air_flow_rate": {"icon": "mdi:fan-plus", "min": 100, "max": 150, "step": 1},
    "max_exhaust_air_flow_rate": {"icon": "mdi:fan-minus", "min": 100, "max": 150, "step": 1},
    "max_supply_air_flow_rate_gwc": {"icon": "mdi:fan-plus", "min": 100, "max": 150, "step": 1},
    "max_exhaust_air_flow_rate_gwc": {"icon": "mdi:fan-minus", "min": 100, "max": 150, "step": 1},
    # Nominal (calibrated) air flow (m³/h)
    "nominal_supply_air_flow": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    "nominal_exhaust_air_flow": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    "nominal_supply_air_flow_gwc": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    "nominal_exhaust_air_flow_gwc": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    # GWC timing
    "gwc_regen_period": {"icon": "mdi:timer", "min": 4, "max": 8, "step": 1},
    # Fan speed setpoints for AirS panel — speed 1/2/3 non-overlapping ranges
    "fan_speed_1_coef": {"icon": "mdi:speedometer", "min": 10, "max": 45, "step": 1},
    "fan_speed_2_coef": {"icon": "mdi:speedometer", "min": 46, "max": 75, "step": 1},
    "fan_speed_3_coef": {"icon": "mdi:speedometer", "min": 76, "max": 100, "step": 1},
    # Special-function intensity setpoints (%)
    "hood_supply_coef": {"icon": "mdi:stove", "min": 100, "max": 150, "step": 1},
    "hood_exhaust_coef": {"icon": "mdi:stove", "min": 100, "max": 150, "step": 1},
    "fireplace_supply_coef": {"icon": "mdi:fireplace", "min": 5, "max": 50, "step": 1},
    "airing_bathroom_coef": {"icon": "mdi:shower", "min": 100, "max": 150, "step": 1},
    "airing_coef": {"icon": "mdi:window-open", "min": 100, "max": 150, "step": 1},
    "contamination_coef": {"icon": "mdi:air-filter", "min": 100, "max": 150, "step": 1},
    "empty_house_coef": {"icon": "mdi:home-off", "min": 10, "max": 50, "step": 1},
    "airing_switch_coef": {"icon": "mdi:toggle-switch", "min": 100, "max": 150, "step": 1},
    "open_window_coef": {"icon": "mdi:window-open-variant", "min": 10, "max": 100, "step": 1},
    "bypass_coef_1": {"icon": "mdi:transfer", "min": 10, "max": 100, "step": 1},
    "bypass_coef_2": {"icon": "mdi:transfer", "min": 10, "max": 150, "step": 1},
    # Special-function timing (min)
    "airing_panel_mode_time": {"icon": "mdi:timer", "min": 1, "max": 45, "step": 1},
    "airing_switch_mode_time": {"icon": "mdi:timer", "min": 1, "max": 45, "step": 1},
    "airing_switch_mode_on_delay": {"icon": "mdi:timer-plus-outline", "min": 0, "max": 20, "step": 1},
    "airing_switch_mode_off_delay": {"icon": "mdi:timer-minus-outline", "min": 0, "max": 20, "step": 1},
    "fireplace_mode_time": {"icon": "mdi:timer", "min": 1, "max": 10, "step": 1},
    # Modbus port device IDs
    "uart_0_id": {"icon": "mdi:identifier", "min": 10, "max": 19, "step": 1},
    "uart_1_id": {"icon": "mdi:identifier", "min": 10, "max": 19, "step": 1},
    # Filter wear thresholds (0–127 %)
    "cfgszf_fn_new": {"icon": "mdi:filter-check", "min": 0, "max": 127, "step": 1},
    "cfgszf_fw_new": {"icon": "mdi:filter-check", "min": 0, "max": 127, "step": 1},
    # RTC calibration register (0–255, signed offset encoded as unsigned; no SI unit)
    "rtc_cal": {"icon": "mdi:clock-edit", "min": 0, "max": 255, "step": 1, "unit": None},
    # lock_pass — product key passphrase, first 16-bit word (0–0x423f = 16959)
    "lock_pass": {"icon": "mdi:lock", "min": 0, "max": 16959, "step": 1},
}


def _number_translation_keys() -> set[str]:
    """Return register names that have a Number translation entry in en.json.

    Used as a whitelist: only registers present here will produce a Number
    entity, preventing unnamed "Rekuperator" fallback entries for reserved or
    undocumented registers (e.g. ``reserved_8145``–``reserved_8151``).
    """
    try:
        with (Path(__file__).with_name("translations") / "en.json").open(encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("entity", {}).get("number", {}).keys())
    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as err:  # pragma: no cover - fallback when translations missing
        _LOGGER.debug("Failed to load number translation keys: %s", err)
        return set()
    except Exception as err:  # pragma: no cover - unexpected
        _LOGGER.exception("Unexpected error loading number translation keys: %s", err)
        return set()


def _load_translation_keys() -> dict[str, set[str]]:
    """Return available translation keys for supported entity types."""

    try:
        with (Path(__file__).with_name("translations") / "en.json").open(encoding="utf-8") as f:
            data = json.load(f)
        entity = data.get("entity", {})
        return {
            "binary_sensor": set(entity.get("binary_sensor", {}).keys()),
            "switch": set(entity.get("switch", {}).keys()),
            "select": set(entity.get("select", {}).keys()),
        }
    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as err:  # pragma: no cover - fallback when translations missing
        _LOGGER.debug("Failed to load translation keys: %s", err)
        return {"binary_sensor": set(), "switch": set(), "select": set()}
    except Exception as err:  # pragma: no cover - unexpected
        _LOGGER.exception("Unexpected error loading translation keys: %s", err)
        return {"binary_sensor": set(), "switch": set(), "select": set()}


def _load_discrete_mappings() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    """Generate mappings for binary_sensor, switch and select entities."""

    binary_configs: dict[str, dict[str, Any]] = {}
    switch_configs: dict[str, dict[str, Any]] = {}
    select_configs: dict[str, dict[str, Any]] = {}

    translations = _load_translation_keys()
    binary_keys = translations["binary_sensor"]
    switch_keys = translations["switch"]
    select_keys = translations["select"]

    # Coil and discrete input registers are always binary sensors
    for reg in coil_registers():
        if reg not in binary_keys:
            continue
        binary_configs[reg] = {
            "translation_key": reg,
            "register_type": "coil_registers",
        }
    for reg in discrete_input_registers():
        if reg not in binary_keys:
            continue
        binary_configs[reg] = {
            "translation_key": reg,
            "register_type": "discrete_inputs",
        }

    # Holding registers with enumerated states
    for reg in holding_registers():
        info = _get_register_info(reg)
        if not info:
            continue
        states = _parse_states(info.get("unit"))
        if not states:
            continue
        access = (info.get("access") or "").upper()
        cfg: dict[str, Any] = {"translation_key": reg, "register_type": "holding_registers"}
        if len(states) == 2 and set(states.values()) == {0, 1}:
            if "W" in access:
                if reg in switch_keys:
                    cfg["register"] = reg
                    cfg.setdefault("icon", "mdi:toggle-switch")
                    switch_configs[reg] = cfg
                else:
                    if reg in binary_keys:
                        binary_configs[reg] = cfg
        else:
            if reg in select_keys:
                cfg["states"] = states
                select_configs[reg] = cfg

    # Alarm/error registers and diagnostic S_/E_ codes should always be
    # exposed as binary sensors so they are created even if the register
    # metadata marks them as writable or enumerated. We therefore override
    # any previously generated switch/select configurations.
    diag_registers = {"alarm", "error"}
    diag_registers.update(reg for reg in holding_registers() if re.match(r"[se](?:_|\d)", reg))
    for reg in diag_registers:
        if reg not in holding_registers() and reg not in {"alarm", "error"}:
            continue
        if reg not in binary_keys:
            continue
        binary_configs[reg] = {
            "translation_key": reg,
            "register_type": "holding_registers",
            "entity_category": EntityCategory.DIAGNOSTIC,
        }
        switch_configs.pop(reg, None)
        select_configs.pop(reg, None)

    # Registers exposing bitmask flags
    func_map = {
        1: "coil_registers",
        2: "discrete_inputs",
        3: "holding_registers",
        4: "input_registers",
    }
    for reg in get_all_registers():
        if not reg.name:
            continue
        if not reg.extra or not reg.extra.get("bitmask"):
            continue
        register_type = func_map.get(reg.function)
        if not register_type:
            continue
        bits = reg.bits or []
        if bits:
            unnamed_bit = False
            for idx, bit_def in enumerate(bits):
                if isinstance(bit_def, dict):
                    bit_name = bit_def.get("name")
                else:
                    bit_name = str(bit_def) if bit_def is not None else None

                if bit_name:
                    key = f"{reg.name}_{_to_snake_case(bit_name)}"
                    binary_configs[key] = {
                        "translation_key": key,
                        "register_type": register_type,
                        "register": reg.name,
                        "bit": 1 << idx,
                    }
                else:
                    unnamed_bit = True

            if unnamed_bit:
                binary_configs.setdefault(
                    reg.name,
                    {
                        "translation_key": reg.name,
                        "register_type": register_type,
                        "bitmask": True,
                    },
                )
        else:
            binary_configs.setdefault(
                reg.name,
                {
                    "translation_key": reg.name,
                    "register_type": register_type,
                    "bitmask": True,
                },
            )

    return binary_configs, switch_configs, select_configs


# ---------------------------------------------------------------------------
# Entity configurations
# ---------------------------------------------------------------------------

# Number entity mappings loaded from register metadata during setup
NUMBER_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}
SENSOR_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    # Temperature sensors (Input Registers)
    "outside_temperature": {
        "translation_key": "outside_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "supply_temperature": {
        "translation_key": "supply_temperature",
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "exhaust_temperature": {
        "translation_key": "exhaust_temperature",
        "icon": "mdi:thermometer-minus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "fpx_temperature": {
        "translation_key": "fpx_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "duct_supply_temperature": {
        "translation_key": "duct_supply_temperature",
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "gwc_temperature": {
        "translation_key": "gwc_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "ambient_temperature": {
        "translation_key": "ambient_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heating_temperature": {
        "translation_key": "heating_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    # Air flow sensors
    "supply_flow_rate": {
        "translation_key": "supply_flow_rate_m3h",
        "icon": "mdi:fan-plus",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_flow_rate": {
        "translation_key": "exhaust_flow_rate_m3h",
        "icon": "mdi:fan-minus",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "supply_air_flow": {
        "translation_key": "supply_air_flow",
        "icon": "mdi:fan-plus",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "exhaust_air_flow": {
        "translation_key": "exhaust_air_flow",
        "icon": "mdi:fan-minus",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    # Percentage sensors
    "supply_percentage": {
        "translation_key": "supply_percentage",
        "icon": "mdi:fan-plus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "exhaust_percentage": {
        "translation_key": "exhaust_percentage",
        "icon": "mdi:fan-minus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "min_percentage": {
        "translation_key": "min_percentage",
        "icon": "mdi:percent-outline",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "max_percentage": {
        "translation_key": "max_percentage",
        "icon": "mdi:percent-outline",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    # System information sensors
    "day_of_week": {
        "translation_key": "day_of_week",
        "icon": "mdi:calendar-week",
        "register_type": "input_registers",
        # Register 2: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        "value_map": {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"},
    },
    "period": {
        "translation_key": "period",
        "icon": "mdi:clock-outline",
        "register_type": "input_registers",
        # Register 3: 0=slot 1, 1=slot 2, 2=slot 3, 3=slot 4
        "value_map": {0: "slot_1", 1: "slot_2", 2: "slot_3", 3: "slot_4"},
    },
    "compilation_days": {
        "translation_key": "compilation_days",
        "icon": "mdi:calendar",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTime.DAYS,
        "register_type": "input_registers",
    },
    "compilation_seconds": {
        "translation_key": "compilation_seconds",
        "icon": "mdi:timer",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTime.SECONDS,
        "register_type": "input_registers",
    },
    "version_major": {
        "translation_key": "version_major",
        "icon": "mdi:information",
        "register_type": "input_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "version_minor": {
        "translation_key": "version_minor",
        "icon": "mdi:information",
        "register_type": "input_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "version_patch": {
        "translation_key": "version_patch",
        "icon": "mdi:information",
        "register_type": "input_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "serial_number": {
        "translation_key": "serial_number",
        "icon": "mdi:barcode",
        "register_type": "input_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "cf_version": {
        "translation_key": "cf_version",
        "icon": "mdi:information",
        "register_type": "holding_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "exp_version": {
        "translation_key": "exp_version",
        "icon": "mdi:information-outline",
        "register_type": "holding_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    # Mode and status sensors
    "antifreeze_stage": {
        "translation_key": "antifreeze_stage",
        "icon": "mdi:snowflake-thermometer",
        "register_type": "holding_registers",
        # Register 4198: 0=FPX off, 1=FPX mode 1, 2=FPX mode 2
        "value_map": {0: "off", 1: "fpx1", 2: "fpx2"},
    },
    # gwc_mode and bypass_mode are read-only status registers (access="R") that
    # report the device's automatically-determined state. They are exposed as
    # sensors with a value_map rather than select entities so that HA does not
    # present a writable dropdown for registers that cannot accept writes.
    "gwc_mode": {
        "translation_key": "gwc_mode",
        "icon": "mdi:pipe",
        "register_type": "holding_registers",
        "value_map": {0: "off", 1: "auto", 2: "forced"},
    },
    "bypass_mode": {
        "translation_key": "bypass_mode",
        "icon": "mdi:pipe-leak",
        "register_type": "holding_registers",
        # Register 4330: 0=bypass inactive (HX active), 1=freeheating, 2=freecooling.
        # Both 1 and 2 mean the bypass damper is physically open.
        "value_map": {0: "inactive", 1: "freeheating", 2: "freecooling"},
    },
    # mode and season_mode are covered by SELECT_ENTITY_MAPPINGS (writable).
    "comfort_mode": {
        "translation_key": "comfort_mode",
        "icon": "mdi:home-heart",
        "register_type": "holding_registers",
        # Register 4305: 0=inactive, 1=heating function, 2=cooling function
        "value_map": {0: "inactive", 1: "heating", 2: "cooling"},
    },
    "constant_flow_active": {
        "translation_key": "constant_flow_active",
        "icon": "mdi:waves",
        "register_type": "input_registers",
        # Register 271: 0=inactive, 1=active
        "value_map": {0: "inactive", 1: "active"},
    },
    # Filter replacement dates (read-only holding registers)
    "filter_supply_date_limit_get": {
        "translation_key": "filter_supply_date_limit_get",
        "icon": "mdi:calendar-filter",
        "register_type": "holding_registers",
    },
    "filter_exhaust_date_limit_get": {
        "translation_key": "filter_exhaust_date_limit_get",
        "icon": "mdi:calendar-filter",
        "register_type": "holding_registers",
    },
    # Configuration sensors from holding registers
    "supply_air_temperature_manual": {
        "translation_key": "supply_air_temperature_manual",
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "min_bypass_temperature": {
        "translation_key": "min_bypass_temperature",
        "icon": "mdi:thermometer-low",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "air_temperature_summer_free_heating": {
        "translation_key": "air_temperature_summer_free_heating",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "air_temperature_summer_free_cooling": {
        "translation_key": "air_temperature_summer_free_cooling",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    # lock_date — product-key expiry year (BCD-encoded, read-only)
    "lock_date": {
        "translation_key": "lock_date",
        "icon": "mdi:calendar-lock",
        "register_type": "holding_registers",
    },
    # required_temperature — read-only comfort-mode temperature setpoint display
    "required_temperature": {
        "translation_key": "required_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    # lock_date fields — product-key expiry date (read-only)
    "lock_date_00dd": {
        "translation_key": "lock_date_00dd",
        "icon": "mdi:calendar-lock",
        "register_type": "holding_registers",
    },
    "lock_date_00mm": {
        "translation_key": "lock_date_00mm",
        "icon": "mdi:calendar-lock",
        "register_type": "holding_registers",
    },
    "max_supply_air_flow_rate": {
        "translation_key": "max_supply_air_flow_rate",
        "icon": "mdi:fan-plus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "max_exhaust_air_flow_rate": {
        "translation_key": "max_exhaust_air_flow_rate",
        "icon": "mdi:fan-minus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "nominal_supply_air_flow": {
        "translation_key": "nominal_supply_air_flow",
        "icon": "mdi:fan-clock",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "nominal_exhaust_air_flow": {
        "translation_key": "nominal_exhaust_air_flow",
        "icon": "mdi:fan-clock",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    # PWM control values (napięcia wentylatorów)
    "dac_supply": {
        "translation_key": "dac_supply",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "holding_registers",
    },
    "dac_exhaust": {
        "translation_key": "dac_exhaust",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "holding_registers",
    },
    "dac_heater": {
        "translation_key": "dac_heater",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "holding_registers",
    },
    "dac_cooler": {
        "translation_key": "dac_cooler",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "holding_registers",
    },
    # estimated_power and total_energy were register_type="calculated" and are
    # never instantiated by the sensor platform — removed until a
    # computed-register mechanism is implemented.
    # AHU stop alarm code (0 = no alarm, 1 = alarm type S active)
    "stop_ahu_code": {
        "translation_key": "stop_ahu_code",
        "icon": "mdi:alert-circle",
        "register_type": "holding_registers",
        # Register 4384: 0=no blocking alarm, 1=type S alarm (code 98)
        "value_map": {0: "none", 1: "alarm_s"},
    },
    # Derived / calculated sensors — values are produced by the coordinator's
    # _post_process_data and do not correspond to a single Modbus register.
    "device_clock": {
        "translation_key": "device_clock",
        "icon": "mdi:clock-outline",
        "device_class": None,
        "state_class": None,
        "unit": None,
        "register_type": "calculated",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "heat_recovery_efficiency": {
        "translation_key": "heat_recovery_efficiency",
        "icon": "mdi:heat-wave",
        "device_class": getattr(SensorDeviceClass, "EFFICIENCY", None),
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "calculated",
        "suggested_display_precision": 1,
    },
    "heat_recovery_power": {
        "translation_key": "heat_recovery_power",
        "icon": "mdi:radiator",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "calculated",
    },
    "electrical_power": {
        "translation_key": "electrical_power",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "calculated",
    },
}

SELECT_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    "mode": {
        "icon": "mdi:cog",
        "translation_key": "mode",
        "states": {"auto": 0, "manual": 1, "temporary": 2},
        "register_type": "holding_registers",
    },
    "season_mode": {
        "icon": "mdi:weather-partly-snowy",
        "translation_key": "season_mode",
        "states": {"winter": 0, "summer": 1},
        "register_type": "holding_registers",
    },
    "filter_change": {
        "icon": "mdi:filter-variant",
        "translation_key": "filter_change",
        "states": {
            "presostat": 1,
            "flat_filters": 2,
            "cleanpad": 3,
            "cleanpad_pure": 4,
        },
        "register_type": "holding_registers",
    },
    "gwc_regen": {
        "icon": "mdi:heat-wave",
        "translation_key": "gwc_regen",
        "states": {"inactive": 0, "daily_schedule": 1, "temperature_diff": 2},
        "register_type": "holding_registers",
    },
    "bypass_user_mode": {
        "icon": "mdi:pipe-valve",
        "translation_key": "bypass_user_mode",
        "states": {"mode_1": 1, "mode_2": 2, "mode_3": 3},
        "register_type": "holding_registers",
    },
    "cfg_mode_1": {
        "icon": "mdi:tune",
        "translation_key": "cfg_mode_1",
        "states": {"auto": 0, "manual": 1, "temporary": 2},
        "register_type": "holding_registers",
    },
    "cfg_mode_2": {
        "icon": "mdi:tune",
        "translation_key": "cfg_mode_2",
        "states": {"auto": 0, "manual": 1, "temporary": 2},
        "register_type": "holding_registers",
    },
    "configuration_mode": {
        "icon": "mdi:cog-outline",
        "translation_key": "configuration_mode",
        "states": {"normal": 0, "duct_filter_pressure": 47, "afc_filter_pressure": 65},
        "register_type": "holding_registers",
    },
    "pres_check_day": {
        "icon": "mdi:calendar-week",
        "translation_key": "pres_check_day",
        "states": {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        },
        "register_type": "holding_registers",
    },
    "pres_check_day_4432": {
        "icon": "mdi:calendar-week",
        "translation_key": "pres_check_day_4432",
        "states": {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        },
        "register_type": "holding_registers",
    },
    "access_level": {
        "icon": "mdi:account-key",
        "translation_key": "access_level",
        "states": {"user": 0, "service": 1, "manufacturer": 3},
        "register_type": "holding_registers",
    },
    "special_mode": {
        "icon": "mdi:lightning-bolt",
        "translation_key": "special_mode",
        "states": {
            "none": 0,
            "hood": 1,
            "fireplace": 2,
            "airing_doorbell": 3,
            "airing_switch": 4,
            "airing_hygrostat": 5,
            "airing_air_quality": 6,
            "airing_manual": 7,
            "airing_auto": 8,
            "airing_manual_timed": 9,
            "open_windows": 10,
            "empty_house": 11,
        },
        "register_type": "holding_registers",
    },
    "language": {
        "icon": "mdi:translate",
        "translation_key": "language",
        "states": {"pl": 0, "en": 1, "ru": 2, "uk": 3, "sk": 4},
        "register_type": "holding_registers",
    },
    "uart_0_baud": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_0_baud",
        "states": {
            "baud_4800": 0,
            "baud_9600": 1,
            "baud_14400": 2,
            "baud_19200": 3,
            "baud_28800": 4,
            "baud_38400": 5,
            "baud_57600": 6,
            "baud_76800": 7,
            "baud_115200": 8,
        },
        "register_type": "holding_registers",
    },
    "uart_0_parity": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_0_parity",
        "states": {"none": 0, "even": 1, "odd": 2},
        "register_type": "holding_registers",
    },
    "uart_0_stop": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_0_stop",
        "states": {"one": 0, "two": 1},
        "register_type": "holding_registers",
    },
    "uart_1_baud": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_1_baud",
        "states": {
            "baud_4800": 0,
            "baud_9600": 1,
            "baud_14400": 2,
            "baud_19200": 3,
            "baud_28800": 4,
            "baud_38400": 5,
            "baud_57600": 6,
            "baud_76800": 7,
            "baud_115200": 8,
        },
        "register_type": "holding_registers",
    },
    "uart_1_parity": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_1_parity",
        "states": {"none": 0, "even": 1, "odd": 2},
        "register_type": "holding_registers",
    },
    "uart_1_stop": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_1_stop",
        "states": {"one": 0, "two": 1},
        "register_type": "holding_registers",
    },
    # ERV (secondary heater) operating mode — 3 fixed options
    "cfg_post_heater_mode": {
        "icon": "mdi:radiator",
        "translation_key": "cfg_post_heater_mode",
        "states": {"off": 0, "mode_1": 1, "mode_2": 2},
        "register_type": "holding_registers",
    },
}

BINARY_SENSOR_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    # System status (from coil registers)
    "duct_water_heater_pump": {
        "translation_key": "duct_water_heater_pump",
        "icon": "mdi:pump",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "bypass": {
        "translation_key": "bypass",
        "icon": "mdi:pipe-leak",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "coil_registers",
    },
    "info": {
        "translation_key": "info",
        "icon": "mdi:information",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "power_supply_fans": {
        "translation_key": "power_supply_fans",
        "icon": "mdi:fan",
        "device_class": BinarySensorDeviceClass.POWER,
        "register_type": "coil_registers",
    },
    "heating_cable": {
        "translation_key": "heating_cable",
        "icon": "mdi:heating-coil",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "coil_registers",
    },
    "work_permit": {
        "translation_key": "work_permit",
        "icon": "mdi:check-circle",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "gwc": {
        "translation_key": "gwc",
        "icon": "mdi:pipe",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "hood_output": {
        "translation_key": "hood_output",
        "icon": "mdi:stove",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    # System status (from discrete inputs)
    "expansion": {
        "translation_key": "expansion",
        "icon": "mdi:expansion-card",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "register_type": "discrete_inputs",
    },
    "contamination_sensor": {
        "translation_key": "contamination_sensor",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "duct_heater_protection": {
        "translation_key": "duct_heater_protection",
        "icon": "mdi:shield-heat",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "dp_duct_filter_overflow": {
        "translation_key": "dp_duct_filter_overflow",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "airing_sensor": {
        "translation_key": "airing_sensor",
        "icon": "mdi:motion-sensor",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "airing_switch": {
        "translation_key": "airing_switch",
        "icon": "mdi:toggle-switch",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "airing_mini": {
        "translation_key": "airing_mini",
        "icon": "mdi:fan",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fan_speed_3": {
        "translation_key": "fan_speed_3",
        "icon": "mdi:fan-speed-3",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fan_speed_2": {
        "translation_key": "fan_speed_2",
        "icon": "mdi:fan-speed-2",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fan_speed_1": {
        "translation_key": "fan_speed_1",
        "icon": "mdi:fan-speed-1",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fireplace": {
        "translation_key": "fireplace",
        "icon": "mdi:fireplace",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "dp_ahu_filter_overflow": {
        "translation_key": "dp_ahu_filter_overflow",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "ahu_filter_protection": {
        "translation_key": "ahu_filter_protection",
        "icon": "mdi:shield",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "hood_switch": {
        "translation_key": "hood_switch",
        "icon": "mdi:stove",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "empty_house": {
        "translation_key": "empty_house",
        "icon": "mdi:home-outline",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fire_alarm": {
        "translation_key": "fire_alarm",
        "icon": "mdi:fire",
        "device_class": BinarySensorDeviceClass.SAFETY,
        "register_type": "discrete_inputs",
        "inverted": True,  # NC contact: True = circuit closed = no alarm, False = alarm triggered
    },
    # Active modes (from input registers)
    "water_removal_active": {
        "translation_key": "water_removal_active",
        "icon": "mdi:water-off",
        "device_class": BinarySensorDeviceClass.MOISTURE,
        "register_type": "input_registers",
    },
    # on_off_panel_mode is covered by SWITCH_ENTITY_MAPPINGS which provides
    # both read and control capability — no separate binary sensor needed.
    "gwc_regen_flag": {
        "translation_key": "gwc_regen_flag",
        "icon": "mdi:heat-wave",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "holding_registers",
    },
    # Antifreeze (FPX) activation flag — read-only boolean holding register
    "antifreeze_mode": {
        "translation_key": "antifreeze_mode",
        "icon": "mdi:snowflake-alert",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "holding_registers",
    },
    # Filter alarm flags (f_ prefix → diagnostic binary sensors)
    "f_142": {
        "translation_key": "f_142",
        "icon": "mdi:filter-remove",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "holding_registers",
    },
    "f_143": {
        "translation_key": "f_143",
        "icon": "mdi:filter-remove",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "holding_registers",
    },
    "f_146": {
        "translation_key": "f_146",
        "icon": "mdi:filter-alert",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "holding_registers",
    },
    "f_147": {
        "translation_key": "f_147",
        "icon": "mdi:filter-alert",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "holding_registers",
    },
    # Secondary heater (ERV) status
    "post_heater_on": {
        "translation_key": "post_heater_on",
        "icon": "mdi:radiator",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "holding_registers",
    },
}

SPECIAL_MODE_ICONS = {
    "boost": "mdi:rocket-launch",
    "eco": "mdi:leaf",
    "away": "mdi:airplane",
    "fireplace": "mdi:fireplace",
    "hood": "mdi:range-hood",
    "sleep": "mdi:weather-night",
    "party": "mdi:party-popper",
    "bathroom": "mdi:shower",
    "kitchen": "mdi:chef-hat",
    "summer": "mdi:white-balance-sunny",
    "winter": "mdi:snowflake",
}

SWITCH_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    # System control switches from holding registers
    "on_off_panel_mode": {
        "icon": "mdi:power",
        "register": "on_off_panel_mode",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "on_off_panel_mode",
    },
    "bypass_off": {
        "icon": "mdi:pipe-valve",
        "register": "bypass_off",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "bypass_off",
    },
    "gwc_off": {
        "icon": "mdi:heat-wave",
        "register": "gwc_off",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "gwc_off",
    },
    "hard_reset_settings": {
        "icon": "mdi:restore",
        "register": "hard_reset_settings",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "hard_reset_settings",
    },
    "hard_reset_schedule": {
        "icon": "mdi:restore-alert",
        "register": "hard_reset_schedule",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "hard_reset_schedule",
    },
    "comfort_mode_panel": {
        "icon": "mdi:sofa",
        "register": "comfort_mode_panel",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "comfort_mode_panel",
    },
    "airflow_rate_change_flag": {
        "icon": "mdi:air-filter",
        "register": "airflow_rate_change_flag",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "airflow_rate_change_flag",
    },
    "temperature_change_flag": {
        "icon": "mdi:thermometer-alert",
        "register": "temperature_change_flag",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "temperature_change_flag",
    },
    "lock_flag": {
        "icon": "mdi:lock",
        "register": "lock_flag",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "lock_flag",
    },
}

# Discrete entity mappings and special modes are populated during setup

# Time entity mappings for writable BCD HHMM registers
TIME_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}

# Text entities — ASCII string registers exposed as HA text controls
TEXT_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    "device_name": {
        "translation_key": "device_name",
        "icon": "mdi:rename",
        "register_type": "holding_registers",
        "max_length": 16,
    },
}

# Aggregated entity mappings for all platforms
ENTITY_MAPPINGS: dict[str, dict[str, dict[str, Any]]] = {}


def _extend_entity_mappings_from_registers() -> None:
    """Populate entity mappings for registers not explicitly defined.

    Only registers that have a corresponding translation entry are added to
    avoid creating unnamed "Rekuperator" fallback entities for reserved or
    undocumented registers.
    """

    translations = _load_translation_keys()
    binary_keys = translations["binary_sensor"]
    switch_keys = translations["switch"]
    select_keys = translations["select"]
    number_keys = _number_translation_keys()

    for reg in get_all_registers():
        if reg.function != 3 or not reg.name:
            continue
        register = reg.name
        if register in NUMBER_ENTITY_MAPPINGS:
            continue
        if register in SENSOR_ENTITY_MAPPINGS:
            continue
        if register in BINARY_SENSOR_ENTITY_MAPPINGS:
            continue
        # Skip if bit-level entities already cover this register (bitmask registers).
        # Adding a whole-register entity on top of bit entities would create a
        # redundant duplicate that reads the raw bitmask value.
        if any(v.get("register") == register for v in BINARY_SENSOR_ENTITY_MAPPINGS.values()):
            continue
        if register in SWITCH_ENTITY_MAPPINGS:
            continue
        if register in SELECT_ENTITY_MAPPINGS:
            continue
        if register in TEXT_ENTITY_MAPPINGS:
            continue
        if register in TIME_ENTITY_MAPPINGS:
            continue

        if (
            register in {"alarm", "error"}
            or register.startswith("s_")
            or register.startswith("e_")
            or register.startswith("f_")
        ):
            if register not in binary_keys:
                continue
            BINARY_SENSOR_ENTITY_MAPPINGS.setdefault(
                register,
                {
                    "translation_key": register,
                    "icon": "mdi:alert-circle",
                    "register_type": "holding_registers",
                    "device_class": BinarySensorDeviceClass.PROBLEM,
                },
            )
            continue

        # BCD date/time encoding registers — raw BCD year/month/day values with
        # format-descriptor "units" (e.g. "RRMM", "DDTT"); not plain numbers.
        if register.startswith("date_time"):
            continue

        # BCD time registers (schedule/airing/GWC timeslots).
        # RW schedule_* registers → select entity (time-slot picker).
        # RW start_gwc_regen* / stop_gwc_regen* → select entity (preset times).
        # RW pres_check_time*, airing_summer_*, airing_winter_*,
        #   manual_airing_time_to_start → native HA time entity (HH:MM picker).
        # Read-only BCD time registers remain sensors.
        from .utils import BCD_TIME_PREFIXES

        _TIME_ENTITY_PREFIXES = (
            "schedule_",
            "pres_check_time",
            "airing_summer_",
            "airing_winter_",
            "manual_airing_time_to_start",
            "start_gwc_regen",
            "stop_gwc_regen",
        )

        if any(register.startswith(prefix) for prefix in BCD_TIME_PREFIXES):
            reg_access = (reg.access or "").upper()
            if register.startswith(_TIME_ENTITY_PREFIXES) and "W" in reg_access:
                TIME_ENTITY_MAPPINGS.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:clock-outline",
                        "register_type": "holding_registers",
                    },
                )
            else:
                SENSOR_ENTITY_MAPPINGS.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:clock-outline",
                        "register_type": "holding_registers",
                    },
                )
            continue

        # Schedule intensity/airflow setting registers (setting_summer_* and
        # setting_winter_*).  These store a 0–100 % airflow value paired with
        # each BCD time slot and are exposed as select entities with 10 %
        # increment steps so that users can easily pick a preset level.
        if register.startswith(("setting_summer_", "setting_winter_")):
            reg_access = (reg.access or "").upper()
            if "W" in reg_access:
                from .schedule_helpers import PERCENT_10_SELECT_STATES

                SELECT_ENTITY_MAPPINGS.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:fan",
                        "register_type": "holding_registers",
                        "states": PERCENT_10_SELECT_STATES,
                    },
                )
            else:
                SENSOR_ENTITY_MAPPINGS.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:fan",
                        "register_type": "holding_registers",
                    },
                )
            continue

        access = (reg.access or "").upper()
        min_val = reg.min
        max_val = reg.max
        unit = reg.unit
        info_text = reg.information or ""
        scale = reg.multiplier or 1
        step = reg.resolution or scale

        # Registers with JSON enum field — classify as switch/binary_sensor/select
        if reg.enum and not (reg.extra and reg.extra.get("bitmask")):
            enum_states = {_to_snake_case(str(v)): int(k) for k, v in reg.enum.items()}
            if len(reg.enum) == 2 and set(int(k) for k in reg.enum) == {0, 1}:
                if "W" in access:
                    if register not in switch_keys:
                        continue
                    SWITCH_ENTITY_MAPPINGS.setdefault(
                        register,
                        {
                            "icon": "mdi:toggle-switch",
                            "register": register,
                            "register_type": "holding_registers",
                            "category": None,
                            "translation_key": register,
                        },
                    )
                else:
                    if register not in binary_keys:
                        continue
                    BINARY_SENSOR_ENTITY_MAPPINGS.setdefault(
                        register,
                        {
                            "translation_key": register,
                            "icon": "mdi:checkbox-marked-circle-outline",
                            "register_type": "holding_registers",
                        },
                    )
            elif "W" in access:
                if register not in select_keys:
                    continue
                SELECT_ENTITY_MAPPINGS.setdefault(
                    register,
                    {
                        "icon": "mdi:format-list-bulleted",
                        "translation_key": register,
                        "states": enum_states,
                        "register_type": "holding_registers",
                    },
                )
            else:
                # Read-only enum sensor — no translation key check needed since
                # sensor.py skips entities without a recognised translation_key
                # and these are rarely present in the register spec.
                SENSOR_ENTITY_MAPPINGS.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:information-outline",
                        "register_type": "holding_registers",
                    },
                )
            continue

        if min_val is not None and max_val is not None:
            if max_val <= 1:
                if "W" in access:
                    if register not in switch_keys:
                        continue
                    SWITCH_ENTITY_MAPPINGS.setdefault(
                        register,
                        {
                            "icon": "mdi:toggle-switch",
                            "register": register,
                            "register_type": "holding_registers",
                            "category": None,
                            "translation_key": register,
                        },
                    )
                else:
                    if register not in binary_keys:
                        continue
                    BINARY_SENSOR_ENTITY_MAPPINGS.setdefault(
                        register,
                        {
                            "translation_key": register,
                            "icon": "mdi:checkbox-marked-circle-outline",
                            "register_type": "holding_registers",
                        },
                    )
                continue

            if "W" in access and info_text and ";" in info_text and max_val <= 10:
                states: dict[str, int] = {}
                for part in info_text.split(";"):
                    part = part.strip()
                    if " - " not in part:
                        continue
                    val_str, label = part.split(" - ", 1)
                    try:
                        states[_to_snake_case(label)] = int(val_str.strip())
                    except ValueError:
                        continue
                if states:
                    if register not in select_keys:
                        continue
                    SELECT_ENTITY_MAPPINGS.setdefault(
                        register,
                        {
                            "icon": "mdi:format-list-bulleted",
                            "translation_key": register,
                            "states": states,
                            "register_type": "holding_registers",
                        },
                    )
                    continue

            if "W" in access:
                if register not in number_keys:
                    continue
                NUMBER_ENTITY_MAPPINGS.setdefault(
                    register,
                    {
                        "unit": unit,
                        "icon": _infer_icon(register, unit),
                        "min": min_val,
                        "max": max_val,
                        "step": step,
                        "scale": scale,
                    },
                )


def _build_entity_mappings() -> None:
    """Populate entity mapping dictionaries."""

    global NUMBER_ENTITY_MAPPINGS, TIME_ENTITY_MAPPINGS, ENTITY_MAPPINGS

    NUMBER_ENTITY_MAPPINGS = _load_number_mappings()
    TIME_ENTITY_MAPPINGS = {}

    _gen_binary, _gen_switch, _gen_select = _load_discrete_mappings()
    for key in BINARY_SENSOR_ENTITY_MAPPINGS:
        _gen_binary.pop(key, None)
        _gen_switch.pop(key, None)
        _gen_select.pop(key, None)
    for key in SWITCH_ENTITY_MAPPINGS:
        _gen_binary.pop(key, None)
        _gen_select.pop(key, None)
    for key in SELECT_ENTITY_MAPPINGS:
        _gen_binary.pop(key, None)
        _gen_switch.pop(key, None)
    BINARY_SENSOR_ENTITY_MAPPINGS.update(_gen_binary)
    SWITCH_ENTITY_MAPPINGS.update(_gen_switch)
    SELECT_ENTITY_MAPPINGS.update(_gen_select)

    for mode, bit in SPECIAL_FUNCTION_MAP.items():
        SWITCH_ENTITY_MAPPINGS[mode] = {
            "icon": SPECIAL_MODE_ICONS.get(mode, "mdi:toggle-switch"),
            "register": "special_mode",
            "register_type": "holding_registers",
            "category": None,
            "translation_key": mode,
            "bit": bit,
        }

    _extend_entity_mappings_from_registers()

    ENTITY_MAPPINGS = {
        "number": NUMBER_ENTITY_MAPPINGS,
        "sensor": SENSOR_ENTITY_MAPPINGS,
        "binary_sensor": BINARY_SENSOR_ENTITY_MAPPINGS,
        "switch": SWITCH_ENTITY_MAPPINGS,
        "select": SELECT_ENTITY_MAPPINGS,
        "text": TEXT_ENTITY_MAPPINGS,
        "time": TIME_ENTITY_MAPPINGS,
    }


async def async_setup_entity_mappings(hass: HomeAssistant | None = None) -> None:
    """Asynchronously build entity mappings."""

    if hass is not None:
        await hass.async_add_executor_job(_build_entity_mappings)
    else:
        _build_entity_mappings()


try:  # pragma: no cover - handle partially initialized module
    _HAS_HA = importlib.util.find_spec("homeassistant") is not None
except (ImportError, ValueError):
    _HAS_HA = False

if not _HAS_HA or "pytest" in sys.modules:  # pragma: no cover - test env
    _build_entity_mappings()
