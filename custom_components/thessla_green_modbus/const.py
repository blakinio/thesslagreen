"""Constants for the ThesslaGreen Modbus integration."""

from __future__ import annotations

from typing import Any

try:
    from homeassistant.const import Platform as _HAPlatform
except ModuleNotFoundError:  # pragma: no cover - test/runtime fallback without HA

    class _FallbackPlatform:
        BINARY_SENSOR = "binary_sensor"
        BUTTON = "button"
        CLIMATE = "climate"
        FAN = "fan"
        NUMBER = "number"
        SELECT = "select"
        SENSOR = "sensor"
        SWITCH = "switch"
        TEXT = "text"
        TIME = "time"

    _HAPlatform = _FallbackPlatform

Platform = _HAPlatform

# Maximum number of registers that can be read in a single request.
# AirPack4 firmware limit: max 16 registers per FC03/FC04 request
# (per vendor register protocol documentation — device-specific constraint,
# lower than the Modbus spec maximum of 125).
MAX_REGISTERS_PER_REQUEST = 16
MAX_REGS_PER_REQUEST = MAX_REGISTERS_PER_REQUEST
MAX_BATCH_REGISTERS = MAX_REGISTERS_PER_REQUEST

# Holding register addresses where a new batch must start.
#
# addr 16: FW 3.11 rejects FC03 batches that cross from system registers
#   (addr ≤15, e.g. access_level) into schedule registers (addr ≥16).
#   Keeping access_level (15) in its own batch and schedule_summer_* in a
#   separate one eliminates repeated batch exceptions every poll cycle.
#
# addr 8192 (0x2000): page boundary in the AirPack4 memory map.
#   A batch spanning 0x1FFF→0x2000 covers lock_pass/lock_flag (0x1FFB-0x1FFF)
#   and alarm/error/filter_change (0x2000+).  Splitting here ensures alarm
#   and error registers are always read reliably.
HOLDING_BATCH_BOUNDARIES: frozenset[int] = frozenset({16, 8192})

# Integration constants
DOMAIN = "thessla_green_modbus"
MANUFACTURER = "ThesslaGreen"
MODEL = "AirPack Home Series 4"
# Fallback model name used when the unit does not report one
UNKNOWN_MODEL = "Unknown"

# Connection defaults
DEFAULT_NAME = "ThesslaGreen"
DEFAULT_PORT = 502  # Standard Modbus TCP port
DEFAULT_SLAVE_ID = 10
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3
DEFAULT_BACKOFF = 0.0
DEFAULT_BACKOFF_JITTER = 0.0
DEFAULT_MAX_BACKOFF = 30.0
MIN_SCAN_INTERVAL = 5
TEMPERATURE_MIN_C = 15.0
TEMPERATURE_MAX_C = 35.0
TEMPERATURE_STEP_C = 0.5
MAX_VENTILATION_PERCENT = 150
FAN_SPEED_LEVELS = 10
FAN_DEFAULT_PERCENT = 50
CONFIG_FLOW_VERSION_SCALE = 4096
UART_OPTIONAL_REG_START = 4452
UART_OPTIONAL_REG_END = 4460

# Connection / transport configuration
CONF_CONNECTION_TYPE = "connection_type"
CONF_CONNECTION_MODE = "connection_mode"
CONF_SERIAL_PORT = "serial_port"
CONF_BAUD_RATE = "baud_rate"
CONF_PARITY = "parity"
CONF_STOP_BITS = "stop_bits"

CONNECTION_TYPE_TCP = "tcp"
CONNECTION_TYPE_RTU = "rtu"
CONNECTION_TYPE_TCP_RTU = "tcp_rtu"
DEFAULT_CONNECTION_TYPE = CONNECTION_TYPE_TCP

CONNECTION_MODE_TCP = "tcp"
CONNECTION_MODE_TCP_RTU = "tcp_rtu"
CONNECTION_MODE_AUTO = "auto"
DEFAULT_CONNECTION_MODE = CONNECTION_MODE_AUTO

# Default serial settings per ProtokolModbusRTU_AirPack4 specification: "9600 bps 8/N/1"
DEFAULT_SERIAL_PORT = ""
DEFAULT_BAUD_RATE = 9600
DEFAULT_PARITY = "none"
DEFAULT_STOP_BITS = 1

# Register name prefixes used to identify error/status registers
ERROR_REGISTER_PREFIX = "e_"
STATUS_REGISTER_PREFIX = "s_"

SERIAL_PARITY_MAP = {
    "none": "N",
    "even": "E",
    "odd": "O",
}

SERIAL_STOP_BITS_MAP = {
    "1": 1,
    "2": 2,
    1: 1,
    2: 2,
}

# Sensor constants
SENSOR_UNAVAILABLE = 32768  # Indicates missing/invalid sensor reading

# Registers that may report SENSOR_UNAVAILABLE (32768) when a sensor
# is missing or disconnected. Derived from the Thessla Green Modbus
# specification where each of these registers documents this sentinel
# value. The list is intentionally explicit to also serve as inline
# documentation for developers.
SENSOR_UNAVAILABLE_REGISTERS = {
    "outside_temperature",
    "supply_temperature",
    "exhaust_temperature",
    "fpx_temperature",
    "duct_supply_temperature",
    "gwc_temperature",
    "ambient_temperature",
    "heating_temperature",
    "supply_flow_rate",
    "exhaust_flow_rate",
}


# Configuration options
CONF_SLAVE_ID = "slave_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_RETRY = "retry"
CONF_BACKOFF = "backoff"
CONF_BACKOFF_JITTER = "backoff_jitter"
CONF_FORCE_FULL_REGISTER_LIST = "force_full_register_list"
CONF_ENABLE_DEVICE_SCAN = "enable_device_scan"
CONF_SCAN_UART_SETTINGS = "scan_uart_settings"
CONF_SKIP_MISSING_REGISTERS = "skip_missing_registers"
CONF_SAFE_SCAN = "safe_scan"
CONF_AIRFLOW_UNIT = "airflow_unit"
CONF_DEEP_SCAN = "deep_scan"  # Perform exhaustive raw register scan for diagnostics
CONF_MAX_REGISTERS_PER_REQUEST = "max_registers_per_request"
CONF_LOG_LEVEL = "log_level"
CONF_SYNC_DEVICE_CLOCK_ENABLED = "sync_device_clock_enabled"
CONF_SYNC_DEVICE_CLOCK_ON_START = "sync_device_clock_on_start"
CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS = "sync_device_clock_interval_hours"
CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS = "sync_device_clock_max_drift_seconds"

DEFAULT_SYNC_DEVICE_CLOCK_ENABLED = False
DEFAULT_SYNC_DEVICE_CLOCK_ON_START = False
DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS = 24
DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS = 300

AIRFLOW_UNIT_M3H = "m3h"
AIRFLOW_UNIT_PERCENTAGE = "percentage"
DEFAULT_AIRFLOW_UNIT = AIRFLOW_UNIT_M3H

# Registers reporting airflow that changed units from percentage to m³/h
AIRFLOW_RATE_REGISTERS = {"supply_flow_rate", "exhaust_flow_rate"}

DEFAULT_SCAN_UART_SETTINGS = True
DEFAULT_SKIP_MISSING_REGISTERS = False
DEFAULT_ENABLE_DEVICE_SCAN = True
DEFAULT_DEEP_SCAN = False
DEFAULT_MAX_REGISTERS_PER_REQUEST = MAX_BATCH_REGISTERS
DEFAULT_SAFE_SCAN = False
DEFAULT_LOG_LEVEL = "info"
LOG_LEVEL_OPTIONS = ["debug", "info", "warning", "error"]

# Registers that are known to be unavailable on some devices
KNOWN_MISSING_REGISTERS = {
    "input_registers": {
        "compilation_days",  # EC2 — brak w FW 3.11
        "compilation_seconds",  # EC2 — brak w FW 3.11
        "version_patch",  # EC2 — FW 3.11 nie raportuje patch version
        "duct_supply_temperature",  # 0x8000 sentinel — brak czujnika kanałowego
        "gwc_temperature",  # 0x8000 sentinel — brak czujnika GWC
        "water_removal_active",  # EC2 — brak funkcji HEWR w FW 3.11
    },
    "holding_registers": {
        "exp_version",  # EC2 — brak modułu Expansion
        "uart_0_id",  # EC2 — ustawienia UART niedostępne w FW 3.11
        "uart_0_baud",  # EC2
        "uart_0_parity",  # EC2
        "uart_0_stop",  # EC2
        "uart_1_id",  # EC2
        "uart_1_baud",  # EC2
        "uart_1_parity",  # EC2
        "uart_1_stop",  # EC2
        "cfgszf_fn_new",  # EC2 — brak w FW 3.11
        "cfgszf_fw_new",  # EC2 — brak w FW 3.11
        "filter_supply_date_limit_get",  # EC2 — brak w FW 3.11
        "filter_exhaust_date_limit_get",  # EC2 — brak w FW 3.11
        "post_heater_on",  # EC2 — brak nagrzewnicy wtórnej
        "cfg_post_heater_mode",  # EC2 — brak nagrzewnicy wtórnej
    },
    "coil_registers": set(),
    "discrete_inputs": set(),
}

KNOWN_MISSING_CLASSIFICATION: dict[str, str] = {
    "version_patch": "optional_firmware_metadata",
    "compilation_days": "optional_firmware_metadata",
    "compilation_seconds": "optional_firmware_metadata",
    "water_removal_active": "optional_feature",
    "duct_supply_temperature": "hardware_sensor_absent",
    "gwc_temperature": "hardware_sensor_absent",
    "cfg_post_heater_mode": "hardware_gated",
    "post_heater_on": "hardware_gated",
    "cfgszf_fn_new": "expansion_or_service",
    "cfgszf_fw_new": "expansion_or_service",
    "exp_version": "expansion_or_service",
    "filter_exhaust_date_limit_get": "newer_firmware_api",
    "filter_supply_date_limit_get": "newer_firmware_api",
    "uart_0_id": "internal_service_uart",
    "uart_0_baud": "internal_service_uart",
    "uart_0_parity": "internal_service_uart",
    "uart_0_stop": "internal_service_uart",
    "uart_1_id": "internal_service_uart",
    "uart_1_baud": "internal_service_uart",
    "uart_1_parity": "internal_service_uart",
    "uart_1_stop": "internal_service_uart",
}

# Platforms supported by the integration
# Diagnostics is handled separately and therefore not listed here
PLATFORMS: list[Any] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.TIME,
    Platform.BUTTON,
]


# Special function enum index mappings for services.
# Values match the sequential enum indices in special_modes.json (0=none, 1=boost, ...).
SPECIAL_FUNCTION_MAP = {
    "boost": 1,
    "eco": 2,
    "away": 3,
    "sleep": 4,
    "fireplace": 5,
    "hood": 6,
    "party": 7,
    "bathroom": 8,
    "kitchen": 9,
    "summer": 10,
    "winter": 11,
}
