"""Value conversion factors for ThesslaGreen Modbus registers."""

REGISTER_MULTIPLIERS: dict[str, float] = {
    # Temperature sensors with 0.1°C resolution
    "outside_temperature": 0.1,
    "supply_temperature": 0.1,
    "exhaust_temperature": 0.1,
    "fpx_temperature": 0.1,
    "duct_supply_temperature": 0.1,
    "gwc_temperature": 0.1,
    "ambient_temperature": 0.1,
    "heating_temperature": 0.1,
    # Temperature settings with 0.5°C resolution
    "required_temperature": 0.5,
    "supply_air_temperature_manual": 0.5,
    "supply_air_temperature_temporary_1": 0.5,
    "supply_air_temperature_temporary_2": 0.5,
    # Voltage/Current conversions
    "dac_supply": 0.00244,  # 0-4095 -> 0-10V
    "dac_exhaust": 0.00244,
    "dac_heater": 0.00244,
    "dac_cooler": 0.00244,
}
