"""Service schema definitions and validators."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import (
    BYPASS_MODES,
    DAYS_OF_WEEK,
    FILTER_TYPES,
    GWC_MODES,
    MODBUS_BAUD_RATES,
    MODBUS_PARITY,
    MODBUS_PORTS,
    MODBUS_STOP_BITS,
    RESET_TYPES,
    SPECIAL_MODE_OPTIONS,
)
from .services_helpers import (
    validate_bypass_temperature_range as _validate_bypass_temperature_range_impl,
)
from .services_helpers import (
    validate_gwc_temperature_range as _validate_gwc_temperature_range_impl,
)

_ENTITY_IDS_VALIDATOR = getattr(cv, "entity_ids", list)
_CV_TIME = getattr(cv, "time", str)
_CV_STRING = getattr(cv, "string", str)
_SEASONS = ("summer", "winter")


def validate_bypass_temperature_range(data: dict[str, Any]) -> dict[str, Any]:
    """Validate bypass temperature range independently from voluptuous internals."""
    return _validate_bypass_temperature_range_impl(data)


def validate_gwc_temperature_range(data: dict[str, Any]) -> dict[str, Any]:
    """Reject configurations where min_air_temperature >= max_air_temperature."""
    return _validate_gwc_temperature_range_impl(data)


SET_SPECIAL_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("mode"): vol.In(SPECIAL_MODE_OPTIONS),
        vol.Optional("duration", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=480)),
    }
)

SET_AIRFLOW_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("day"): vol.In(DAYS_OF_WEEK),
        vol.Required("period"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
        vol.Required("start_time"): _CV_TIME,
        vol.Optional("end_time"): _CV_TIME,
        vol.Required("airflow_rate"): vol.All(vol.Coerce(int), vol.Range(min=0, max=150)),
        vol.Optional("season", default="summer"): vol.In(_SEASONS),
        vol.Optional("temperature"): vol.All(vol.Coerce(float), vol.Range(min=16.0, max=30.0)),
    }
)

SET_BYPASS_PARAMETERS_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
            vol.Required("mode"): vol.In(BYPASS_MODES),
            vol.Optional("min_outdoor_temperature"): vol.All(
                vol.Coerce(float), vol.Range(min=-20.0, max=40.0)
            ),
        }
    ),
    validate_bypass_temperature_range,
)

SET_GWC_PARAMETERS_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
            vol.Required("mode"): vol.In(GWC_MODES),
            vol.Optional("min_air_temperature"): vol.All(
                vol.Coerce(float), vol.Range(min=0.0, max=20.0)
            ),
            vol.Optional("max_air_temperature"): vol.All(
                vol.Coerce(float), vol.Range(min=30.0, max=80.0)
            ),
        }
    ),
    validate_gwc_temperature_range,
)

SET_AIR_QUALITY_THRESHOLDS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Optional("co2_low"): vol.All(vol.Coerce(int), vol.Range(min=400, max=800)),
        vol.Optional("co2_medium"): vol.All(vol.Coerce(int), vol.Range(min=600, max=1200)),
        vol.Optional("co2_high"): vol.All(vol.Coerce(int), vol.Range(min=800, max=1600)),
        vol.Optional("humidity_target"): vol.All(vol.Coerce(int), vol.Range(min=30, max=70)),
    }
)

SET_TEMPERATURE_CURVE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("slope"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=3.0)),
        vol.Required("offset"): vol.All(vol.Coerce(float), vol.Range(min=-10.0, max=10.0)),
        vol.Optional("max_supply_temp"): vol.All(vol.Coerce(float), vol.Range(min=25.0, max=95.0)),
        vol.Optional("min_supply_temp"): vol.All(vol.Coerce(float), vol.Range(min=15.0, max=35.0)),
    }
)

RESET_FILTERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("filter_type"): vol.In(FILTER_TYPES),
    }
)

RESET_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("reset_type"): vol.In(RESET_TYPES),
    }
)

START_PRESSURE_TEST_SCHEMA = vol.Schema({vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR})

SET_MODBUS_PARAMETERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("port"): vol.In(MODBUS_PORTS),
        vol.Optional("baud_rate"): vol.In(MODBUS_BAUD_RATES),
        vol.Optional("parity"): vol.In(MODBUS_PARITY),
        vol.Optional("stop_bits"): vol.In(MODBUS_STOP_BITS),
    }
)

SET_DEVICE_NAME_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("device_name"): vol.All(_CV_STRING, vol.Length(min=1, max=16)),
    }
)

SYNC_TIME_SCHEMA = vol.Schema({vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR})
REFRESH_DEVICE_DATA_SCHEMA = vol.Schema({vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR})
SCAN_ALL_REGISTERS_SCHEMA = vol.Schema({vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR})
SET_LOG_LEVEL_SCHEMA = vol.Schema(
    {
        vol.Optional("level", default="debug"): vol.In(["debug", "info", "warning", "error"]),
        vol.Optional("duration", default=900): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=86400)
        ),
    }
)

