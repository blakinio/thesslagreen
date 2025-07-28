"""Constants for TeslaGreen Modbus Integration."""
from __future__ import annotations

from typing import Final

# Domain
DOMAIN: Final = "thessla_green_modbus"

# Default configuration
DEFAULT_NAME: Final = "TeslaGreen"
DEFAULT_PORT: Final = 502
DEFAULT_SLAVE_ID: Final = 1
DEFAULT_SCAN_INTERVAL: Final = 30

# Modbus registers
MODBUS_REGISTERS: Final = {
    # Temperature sensors
    "temp_supply": 0x0001,
    "temp_extract": 0x0002,
    "temp_outdoor": 0x0003,
    "temp_exhaust": 0x0004,
    
    # Fan speeds
    "fan_supply_speed": 0x0010,
    "fan_extract_speed": 0x0011,
    
    # Air quality
    "co2_level": 0x0020,
    "humidity": 0x0021,
    "air_quality_index": 0x0022,
    
    # System status
    "system_status": 0x0030,
    "filter_status": 0x0031,
    "bypass_status": 0x0032,
    
    # Control registers
    "target_temperature": 0x0100,
    "fan_speed_setting": 0x0101,
    "mode_selection": 0x0102,
    "bypass_control": 0x0103,
}

# Device information
DEVICE_INFO: Final = {
    "identifiers": {(DOMAIN, "thessla_green_modbus")},
    "name": "TeslaGreen Rekuperator",
    "manufacturer": "TeslaGreen",
    "model": "Modbus Rekuperator",
    "sw_version": "1.0.0",
}

# Configuration schema
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_SLAVE_ID: Final = "slave_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"
