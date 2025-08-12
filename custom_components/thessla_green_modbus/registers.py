"""Register definitions for the ThesslaGreen Modbus integration."""
from typing import Dict

# INPUT REGISTERS (04 - READ INPUT REGISTER)
# Addresses based on MODBUS_USER_AirPack_Home_08.2021.01 specification.
INPUT_REGISTERS: Dict[str, int] = {
    # Firmware information
    "firmware_major": 0x0000,
    "firmware_minor": 0x0001,
    "day_of_week": 0x0002,
    "period": 0x0003,
    "firmware_patch": 0x0004,
    "compilation_days": 0x000E,
    "compilation_seconds": 0x000F,
    # Temperature sensors (0.1°C, 0x8000 means no sensor)
    "outside_temperature": 0x0010,
    "supply_temperature": 0x0011,
    "exhaust_temperature": 0x0012,
    "fpx_temperature": 0x0013,
    "duct_supply_temperature": 0x0014,
    "gwc_temperature": 0x0015,
    "ambient_temperature": 0x0016,
    # Serial number (six 16-bit words)
    "serial_number_1": 0x0018,
    "serial_number_2": 0x0019,
    "serial_number_3": 0x001A,
    "serial_number_4": 0x001B,
    "serial_number_5": 0x001C,
    "serial_number_6": 0x001D,
    # Air flow measurements
    "supply_air_flow": 0x0100,
    "exhaust_air_flow": 0x0101,
    "constant_flow_active": 0x010F,
    # Flow set-points
    "supply_flow_rate": 0x0112,
    "exhaust_flow_rate": 0x0113,
}

# HOLDING REGISTERS (03 - READ/WRITE HOLDING REGISTER)
# Addresses based on MODBUS_USER_AirPack_Home_08.2021.01 specification.
HOLDING_REGISTERS: Dict[str, int] = {
    # Main control registers
    "mode": 0x1070,  # 0-auto, 1-manual, 2-temporary
    "season_mode": 0x1071,  # 0-summer, 1-winter
    "air_flow_rate_manual": 0x1072,  # %
    "supply_air_temperature_manual": 0x1074,  # 0.5°C resolution
    "special_mode": 0x1080,  # special functions
    "on_off_panel_mode": 0x1123,  # 0-off, 1-on
}
