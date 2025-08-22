"""Register definitions for the ThesslaGreen Modbus integration."""

from __future__ import annotations

# Generated from thessla_green_registers_full.json

COIL_REGISTERS: dict[str, int] = {
    "duct_water_heater_pump": 5,
    "bypass": 9,
    "power_supply_fans": 11,
    "heating_cable": 12,
    "gwc": 14,
    "hood_output": 15,
}

DISCRETE_INPUT_REGISTERS: dict[str, int] = {
    "expansion": 1,
    "contamination_sensor": 5,
}

# Sizes of holding register blocks that span multiple consecutive registers.
# Each key is the starting register name and the value is the number of
# registers in that block.
MULTI_REGISTER_SIZES: dict[str, int] = {
    "date_time_1": 4,
    "lock_date_1": 3,
}

INPUT_REGISTERS: dict[str, int] = {
    "version_major": 0,
    "version_minor": 1,
    "period": 3,
    "version_patch": 4,
    "compilation_days": 14,
    "outside_temperature": 16,
    "supply_temperature": 17,
    "exhaust_temperature": 18,
    "serial_number_1": 24,
    "supply_air_flow": 256,
    "constant_flow_active": 271,
    "supply_percentage": 272,
    "exhaust_percentage": 273,
    "supply_flow_rate": 274,
    "exhaust_flow_rate": 275,
    "min_percentage": 276,
    "max_percentage": 277,
    "water_removal_active": 298,
    "dac_supply": 1280,
    "dac_exhaust": 1281,
    "dac_heater": 1282,
    "dac_cooler": 1283,
}

HOLDING_REGISTERS: dict[str, int] = {
    "access_level": 15,
    "cf_version": 240,
    "max_supply_air_flow_rate": 4117,
    "max_exhaust_air_flow_rate": 4119,
    "mode": 4208,
    "season_mode": 4209,
    "air_flow_rate_manual": 4210,
    "supply_air_temperature_manual": 4212,
    "manual_airing_time_to_start": 4219,
    "special_mode": 4224,
    "airing_panel_mode_time": 4233,
    "airing_switch_mode_time": 4234,
    "airing_switch_mode_on_delay": 4235,
    "airing_switch_mode_off_delay": 4236,
    "airing_switch_coef": 4238,
    "gwc_mode": 4263,
    "comfort_mode": 4305,
    "bypass_off": 4320,
    "bypass_mode": 4330,
    "nominal_supply_air_flow": 4354,
    "nominal_exhaust_air_flow": 4355,
    "on_off_panel_mode": 4387,
    "air_flow_rate_temporary_2": 4401,
    "device_name_1": 8144,
    "required_temperature": 8190,
    "alarm": 8192,
    "error": 8193,
    "s_2": 8194,
    "e_99": 8291,
    "e_100": 8292,
    "e_196_e_199": 8390,
}

