from __future__ import annotations

import json
import types
import sys
from pathlib import Path
import importlib

# Minimal Home Assistant stubs required to import entity mappings
ha_const = types.ModuleType("homeassistant.const")
ha_const.PERCENTAGE = "%"
ha_const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
ha_const.UnitOfVolumeFlowRate = types.SimpleNamespace(CUBIC_METERS_PER_HOUR="m³/h")
ha_const.UnitOfElectricPotential = types.SimpleNamespace(VOLT="V")
ha_const.UnitOfTime = types.SimpleNamespace(HOURS="h", DAYS="d", SECONDS="s")
sys.modules.setdefault("homeassistant.const", ha_const)

sensor_mod = types.ModuleType("homeassistant.components.sensor")
sensor_mod.SensorDeviceClass = types.SimpleNamespace(
    TEMPERATURE="temperature",
    VOLTAGE="voltage",
    POWER="power",
    ENERGY="energy",
    EFFICIENCY="efficiency",
)
sensor_mod.SensorStateClass = types.SimpleNamespace(
    MEASUREMENT="measurement", TOTAL_INCREASING="total_increasing"
)
sys.modules.setdefault("homeassistant.components.sensor", sensor_mod)

binary_mod = types.ModuleType("homeassistant.components.binary_sensor")
binary_mod.BinarySensorDeviceClass = types.SimpleNamespace(
    RUNNING="running",
    OPENING="opening",
    POWER="power",
    HEAT="heat",
    CONNECTIVITY="connectivity",
    PROBLEM="problem",
    SAFETY="safety",
    MOISTURE="moisture",
)
sys.modules.setdefault("homeassistant.components.binary_sensor", binary_mod)

# Intentionally omitted technical/configuration registers
INTENTIONAL_OMISSIONS = {
    "air_flow_rate_temporary",
    "air_flow_rate_temporary_4401",
    "airflow_rate_change_flag",
    "airing_bathroom_coef",
    "airing_coef",
    "airing_panel_mode_time",
    "airing_summer_fri",
    "airing_summer_mon",
    "airing_summer_sat",
    "airing_summer_sun",
    "airing_summer_thu",
    "airing_summer_tue",
    "airing_summer_wed",
    "airing_switch_coef",
    "airing_switch_mode_off_delay",
    "airing_switch_mode_on_delay",
    "airing_switch_mode_time",
    "airing_winter_fri",
    "airing_winter_mon",
    "airing_winter_sat",
    "airing_winter_sun",
    "airing_winter_thu",
    "airing_winter_tue",
    "airing_winter_wed",
    "antifreez_stage",
    "bypass_coef1",
    "bypass_coef2",
    "bypass_user_mode",
    "cfg_mode1",
    "cfg_mode2",
    "comfort_mode_panel",
    "configuration_mode",
    "contamination_coef",
    "date_time",
    "date_time_ddtt",
    "date_time_ggmm",
    "date_time_sscc",
    "device_name",
    "e100",
    "e101",
    "e102",
    "e103",
    "e104",
    "e105",
    "e106",
    "e138",
    "e139",
    "e152",
    "e196_e199",
    "e200",
    "e201",
    "e249",
    "e250",
    "e251",
    "e252",
    "e99",
    "empty_house_coef",
    "fan_speed1_coef",
    "fan_speed2_coef",
    "fan_speed3_coef",
    "fireplace_mode_time",
    "fireplace_supply_coef",
    "gwc_off",
    "gwc_regen",
    "gwc_regen_flag",
    "hard_reset_schedule",
    "hard_reset_settings",
    "language",
    "lock_date",
    "lock_date_00dd",
    "lock_date_00mm",
    "lock_flag",
    "lock_pass",
    "manual_airing_time_to_start",
    "open_window_coef",
    "pres_check_day",
    "pres_check_day_4432",
    "pres_check_time",
    "pres_check_time_ggmm",
    "rtc_cal",
    "s10",
    "s13",
    "s14",
    "s15",
    "s16",
    "s17",
    "s19",
    "s2",
    "s20",
    "s22",
    "s23",
    "s24",
    "s25",
    "s26",
    "s29",
    "s30",
    "s31",
    "s32",
    "s6",
    "s7",
    "s8",
    "s9",
    "schedule_summer_fri_1",
    "schedule_summer_fri_2",
    "schedule_summer_fri_3",
    "schedule_summer_fri_4",
    "schedule_summer_mon_1",
    "schedule_summer_mon_2",
    "schedule_summer_mon_3",
    "schedule_summer_mon_4",
    "schedule_summer_sat_1",
    "schedule_summer_sat_2",
    "schedule_summer_sat_3",
    "schedule_summer_sat_4",
    "schedule_summer_sun_1",
    "schedule_summer_sun_2",
    "schedule_summer_sun_3",
    "schedule_summer_sun_4",
    "schedule_summer_thu_1",
    "schedule_summer_thu_2",
    "schedule_summer_thu_3",
    "schedule_summer_thu_4",
    "schedule_summer_tue_1",
    "schedule_summer_tue_2",
    "schedule_summer_tue_3",
    "schedule_summer_tue_4",
    "schedule_summer_wed_1",
    "schedule_summer_wed_2",
    "schedule_summer_wed_3",
    "schedule_summer_wed_4",
    "schedule_winter_fri_1",
    "schedule_winter_fri_2",
    "schedule_winter_fri_3",
    "schedule_winter_fri_4",
    "schedule_winter_mon_1",
    "schedule_winter_mon_2",
    "schedule_winter_mon_3",
    "schedule_winter_mon_4",
    "schedule_winter_sat_1",
    "schedule_winter_sat_2",
    "schedule_winter_sat_3",
    "schedule_winter_sat_4",
    "schedule_winter_sun_1",
    "schedule_winter_sun_2",
    "schedule_winter_sun_3",
    "schedule_winter_sun_4",
    "schedule_winter_thu_1",
    "schedule_winter_thu_2",
    "schedule_winter_thu_3",
    "schedule_winter_thu_4",
    "schedule_winter_tue_1",
    "schedule_winter_tue_2",
    "schedule_winter_tue_3",
    "schedule_winter_tue_4",
    "schedule_winter_wed_1",
    "schedule_winter_wed_2",
    "schedule_winter_wed_3",
    "schedule_winter_wed_4",
    "setting_summer_fri_1",
    "setting_summer_fri_2",
    "setting_summer_fri_3",
    "setting_summer_fri_4",
    "setting_summer_mon_1",
    "setting_summer_mon_2",
    "setting_summer_mon_3",
    "setting_summer_mon_4",
    "setting_summer_sat_1",
    "setting_summer_sat_2",
    "setting_summer_sat_3",
    "setting_summer_sat_4",
    "setting_summer_sun_1",
    "setting_summer_sun_2",
    "setting_summer_sun_3",
    "setting_summer_sun_4",
    "setting_summer_thu_1",
    "setting_summer_thu_2",
    "setting_summer_thu_3",
    "setting_summer_thu_4",
    "setting_summer_tue_1",
    "setting_summer_tue_2",
    "setting_summer_tue_3",
    "setting_summer_tue_4",
    "setting_summer_wed_1",
    "setting_summer_wed_2",
    "setting_summer_wed_3",
    "setting_summer_wed_4",
    "setting_winter_fri_1",
    "setting_winter_fri_2",
    "setting_winter_fri_3",
    "setting_winter_fri_4",
    "setting_winter_mon_1",
    "setting_winter_mon_2",
    "setting_winter_mon_3",
    "setting_winter_mon_4",
    "setting_winter_sat_1",
    "setting_winter_sat_2",
    "setting_winter_sat_3",
    "setting_winter_sat_4",
    "setting_winter_sun_1",
    "setting_winter_sun_2",
    "setting_winter_sun_3",
    "setting_winter_sun_4",
    "setting_winter_thu_1",
    "setting_winter_thu_2",
    "setting_winter_thu_3",
    "setting_winter_thu_4",
    "setting_winter_tue_1",
    "setting_winter_tue_2",
    "setting_winter_tue_3",
    "setting_winter_tue_4",
    "setting_winter_wed_1",
    "setting_winter_wed_2",
    "setting_winter_wed_3",
    "setting_winter_wed_4",
    "special_mode",
    "start_gwc_regen_summer_time",
    "start_gwc_regen_winter_time",
    "stop_ahu_code",
    "stop_gwc_regen_summer_time",
    "stop_gwc_regen_winter_time",
    "supply_air_temperature_temporary",
    "supply_air_temperature_temporary_4404",
    "temperature_change_flag",
    "uart0_baud",
    "uart0_id",
    "uart0_parity",
    "uart0_stop",
    "uart1_baud",
    "uart1_id",
    "uart1_parity",
    "uart1_stop",
}

def test_all_registers_covered() -> None:
    """Ensure all registers are exposed or intentionally omitted."""

    json_file = (
        Path("custom_components/thessla_green_modbus/registers")
        / "thessla_green_registers_full.json"
    )
    registers = {
        r["name"]
        for r in json.loads(json_file.read_text(encoding="utf-8"))["registers"]
        if r.get("name")
    }

    entity_mod = importlib.import_module(
        "custom_components.thessla_green_modbus.entity_mappings"
    )
    exposed: set[str] = set()
    for mapping in entity_mod.ENTITY_MAPPINGS.values():
        exposed.update(mapping.keys())

    diagnostic_regs = {n for n in registers if n.startswith(("e_", "s_")) or n in {"alarm", "error"}}

    missing = registers - exposed - diagnostic_regs - INTENTIONAL_OMISSIONS
    assert not missing, f"Unmapped registers: {sorted(missing)}"

    extra = INTENTIONAL_OMISSIONS - registers
    assert not extra, f"Unknown omissions: {sorted(extra)}"
