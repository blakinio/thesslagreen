"""Value conversion factors for ThesslaGreen Modbus registers."""

from typing import Dict

REGISTER_MULTIPLIERS: Dict[str, float] = {
    # Temperature sensors with 0.1°C resolution
    "outside_temperature": 0.1,
    "supply_temperature": 0.1,
    "exhaust_temperature": 0.1,
    "fpx_temperature": 0.1,
    "duct_supply_temperature": 0.1,
    "gwc_temperature": 0.1,
    "ambient_temperature": 0.1,
    "heating_temperature": 0.1,
    "heat_exchanger_temperature_1": 0.1,
    "heat_exchanger_temperature_2": 0.1,
    "heat_exchanger_temperature_3": 0.1,
    "heat_exchanger_temperature_4": 0.1,
    # Temperature settings with 0.5°C resolution
    "required_temperature": 0.5,
    "comfort_temperature": 0.5,
    "economy_temperature": 0.5,
    "night_temperature": 0.5,
    "away_temperature": 0.5,
    "frost_protection_temperature": 0.5,
    "max_supply_temperature": 0.5,
    "min_supply_temperature": 0.5,
    "heating_curve_offset": 0.5,
    "bypass_temperature_threshold": 0.5,
    "bypass_hysteresis": 0.5,
    "gwc_temperature_threshold": 0.5,
    "gwc_hysteresis": 0.5,
    "preheating_temperature": 0.5,
    "defrost_temperature": 0.5,
    "night_cooling_temperature": 0.5,
    "supply_air_temperature_manual": 0.5,
    "supply_air_temperature_temporary": 0.5,
    # Legacy alias
    "required_temp": 0.5,
    # Voltage/Current conversions
    "dac_supply": 0.00244,  # 0-4095 -> 0-10V
    "dac_exhaust": 0.00244,
    "dac_heater": 0.00244,
    "dac_cooler": 0.00244,
    "motor_supply_current": 0.001,  # mA to A
    "motor_exhaust_current": 0.001,
    "motor_supply_voltage": 0.001,  # mV to V
    "motor_exhaust_voltage": 0.001,
    # Other multipliers
    "heating_curve_slope": 0.1,
}
