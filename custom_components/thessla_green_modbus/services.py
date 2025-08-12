"""Service handlers for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SPECIAL_FUNCTION_MAP
from .multipliers import REGISTER_MULTIPLIERS

_LOGGER = logging.getLogger(__name__)

# Map service parameters to corresponding register names
AIR_QUALITY_REGISTER_MAP = {
    "co2_low": "co2_threshold_low",
    "co2_medium": "co2_threshold_medium",
    "co2_high": "co2_threshold_high",
    "humidity_target": "humidity_target",
}


def _scale_for_register(register_name: str, value: float) -> int:
    """Scale ``value`` according to ``REGISTER_MULTIPLIERS`` for ``register_name``.

    This converts user-facing units (e.g. degrees Celsius) to raw register
    values expected by the device.
    """
    multiplier = REGISTER_MULTIPLIERS.get(register_name)
    if multiplier is not None:
        return int(round(value / multiplier))
    return int(round(value))


# Service schemas
SET_SPECIAL_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("mode"): vol.In(
            [
                "none",
                "boost",
                "eco",
                "away",
                "sleep",
                "fireplace",
                "hood",
                "party",
                "bathroom",
                "kitchen",
                "summer",
                "winter",
            ]
        ),
        vol.Optional("duration", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=480)),
    }
)

SET_AIRFLOW_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("day"): vol.In(
            ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        ),
        vol.Required("period"): vol.In(["1", "2"]),
        vol.Required("start_time"): cv.time,
        vol.Required("end_time"): cv.time,
        vol.Required("airflow_rate"): vol.All(vol.Coerce(int), vol.Range(min=10, max=100)),
        vol.Optional("temperature"): vol.All(vol.Coerce(float), vol.Range(min=16.0, max=30.0)),
    }
)

SET_BYPASS_PARAMETERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("mode"): vol.In(["auto", "open", "closed"]),
        vol.Optional("temperature_threshold"): vol.All(
            vol.Coerce(float), vol.Range(min=18.0, max=30.0)
        ),
        vol.Optional("hysteresis"): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=5.0)),
    }
)

SET_GWC_PARAMETERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("mode"): vol.In(["off", "auto", "forced"]),
        vol.Optional("temperature_threshold"): vol.All(
            vol.Coerce(float), vol.Range(min=-5.0, max=15.0)
        ),
        vol.Optional("hysteresis"): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=5.0)),
    }
)

SET_AIR_QUALITY_THRESHOLDS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Optional("co2_low"): vol.All(vol.Coerce(int), vol.Range(min=400, max=800)),
        vol.Optional("co2_medium"): vol.All(vol.Coerce(int), vol.Range(min=600, max=1200)),
        vol.Optional("co2_high"): vol.All(vol.Coerce(int), vol.Range(min=800, max=1600)),
        vol.Optional("humidity_target"): vol.All(vol.Coerce(int), vol.Range(min=30, max=70)),
    }
)

SET_TEMPERATURE_CURVE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("slope"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=3.0)),
        vol.Required("offset"): vol.All(vol.Coerce(float), vol.Range(min=-10.0, max=10.0)),
        vol.Optional("max_supply_temp"): vol.All(vol.Coerce(float), vol.Range(min=25.0, max=95.0)),
        vol.Optional("min_supply_temp"): vol.All(vol.Coerce(float), vol.Range(min=15.0, max=35.0)),
    }
)

RESET_FILTERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("filter_type"): vol.In(
            ["presostat", "flat_filters", "cleanpad", "cleanpad_pure"]
        ),
    }
)

RESET_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("reset_type"): vol.In(["user_settings", "schedule_settings", "all_settings"]),
    }
)

START_PRESSURE_TEST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
    }
)

SET_MODBUS_PARAMETERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("port"): vol.In(["air_b", "air_plus"]),
        vol.Optional("baud_rate"): vol.In(
            ["4800", "9600", "14400", "19200", "28800", "38400", "57600", "76800", "115200"]
        ),
        vol.Optional("parity"): vol.In(["none", "even", "odd"]),
        vol.Optional("stop_bits"): vol.In(["1", "2"]),
    }
)

SET_DEVICE_NAME_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("device_name"): vol.All(cv.string, vol.Match(r"^[ -~]{1,16}$")),
    }
)

REFRESH_DEVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for ThesslaGreen Modbus integration."""

    async def set_special_mode(call: ServiceCall) -> None:
        """Service to set special mode."""
        entity_ids = async_extract_entity_ids(hass, call)
        mode = call.data["mode"]
        duration = call.data.get("duration", 0)

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                # Set special mode using the special_mode register
                special_mode_value = SPECIAL_FUNCTION_MAP.get(mode, 0)
                await coordinator.async_write_register(
                    "special_mode", special_mode_value, refresh=False
                )

                # Set duration if specified and supported
                if duration > 0 and mode in [
                    "boost",
                    "fireplace",
                    "hood",
                    "party",
                    "bathroom",
                ]:
                    duration_register = f"{mode}_duration"
                    if duration_register in coordinator.available_registers.get(
                        "holding_registers", set()
                    ):
                        await coordinator.async_write_register(
                            duration_register, duration, refresh=False
                        )

                await coordinator.async_request_refresh()
                _LOGGER.info("Set special mode %s for %s", mode, entity_id)

    async def set_airflow_schedule(call: ServiceCall) -> None:
        """Service to set airflow schedule."""
        entity_ids = async_extract_entity_ids(hass, call)
        day = call.data["day"]
        period = call.data["period"]
        start_time = call.data["start_time"]
        end_time = call.data["end_time"]
        airflow_rate = call.data["airflow_rate"]
        temperature = call.data.get("temperature")

        # Convert day name to index
        day_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        day_index = day_map[day]

        # Convert time to HHMM format
        start_hhmm = start_time.hour * 100 + start_time.minute
        end_hhmm = end_time.hour * 100 + end_time.minute

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                # Calculate register names based on day and period
                day_names = [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                ]
                day_name = day_names[day_index]

                start_register = f"schedule_{day_name}_period{period}_start"
                end_register = f"schedule_{day_name}_period{period}_end"
                flow_register = f"schedule_{day_name}_period{period}_flow"
                temp_register = f"schedule_{day_name}_period{period}_temp"

                # Write schedule values with proper scaling
                await coordinator.async_write_register(
                    start_register,
                    _scale_for_register(start_register, start_hhmm),
                    refresh=False,
                )
                await coordinator.async_write_register(
                    end_register,
                    _scale_for_register(end_register, end_hhmm),
                    refresh=False,
                )
                await coordinator.async_write_register(
                    flow_register,
                    _scale_for_register(flow_register, airflow_rate),
                    refresh=False,
                )

                if temperature is not None:
                    await coordinator.async_write_register(
                        temp_register,
                        _scale_for_register(temp_register, temperature),
                        refresh=False,
                    )

                await coordinator.async_request_refresh()
                _LOGGER.info("Set airflow schedule for %s", entity_id)

    async def set_bypass_parameters(call: ServiceCall) -> None:
        """Service to set bypass parameters."""
        entity_ids = async_extract_entity_ids(hass, call)
        mode = call.data["mode"]
        temperature_threshold = call.data.get("temperature_threshold")
        hysteresis = call.data.get("hysteresis")

        mode_map = {"auto": 0, "open": 1, "closed": 2}
        mode_value = mode_map[mode]

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                await coordinator.async_write_register(
                    "bypass_mode",
                    _scale_for_register("bypass_mode", mode_value),
                    refresh=False,
                )

                if temperature_threshold is not None:
                    await coordinator.async_write_register(
                        "bypass_temperature_threshold",
                        _scale_for_register("bypass_temperature_threshold", temperature_threshold),
                        refresh=False,
                    )

                if hysteresis is not None:
                    await coordinator.async_write_register(
                        "bypass_hysteresis",
                        _scale_for_register("bypass_hysteresis", hysteresis),
                        refresh=False,
                    )

                await coordinator.async_request_refresh()
                _LOGGER.info("Set bypass parameters for %s", entity_id)

    async def set_gwc_parameters(call: ServiceCall) -> None:
        """Service to set GWC parameters."""
        entity_ids = async_extract_entity_ids(hass, call)
        mode = call.data["mode"]
        temperature_threshold = call.data.get("temperature_threshold")
        hysteresis = call.data.get("hysteresis")

        mode_map = {"off": 0, "auto": 1, "forced": 2}
        mode_value = mode_map[mode]

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                await coordinator.async_write_register(
                    "gwc_mode",
                    _scale_for_register("gwc_mode", mode_value),
                    refresh=False,
                )

                if temperature_threshold is not None:
                    await coordinator.async_write_register(
                        "gwc_temperature_threshold",
                        _scale_for_register("gwc_temperature_threshold", temperature_threshold),
                        refresh=False,
                    )

                if hysteresis is not None:
                    await coordinator.async_write_register(
                        "gwc_hysteresis",
                        _scale_for_register("gwc_hysteresis", hysteresis),
                        refresh=False,
                    )

                await coordinator.async_request_refresh()
                _LOGGER.info("Set GWC parameters for %s", entity_id)

    async def set_air_quality_thresholds(call: ServiceCall) -> None:
        """Service to set air quality thresholds."""
        entity_ids = async_extract_entity_ids(hass, call)

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                for param in ["co2_low", "co2_medium", "co2_high", "humidity_target"]:
                    value = call.data.get(param)
                    if value is not None:
                        register_name = AIR_QUALITY_REGISTER_MAP[param]
                        await coordinator.async_write_register(register_name, value, refresh=False)

                await coordinator.async_request_refresh()
                _LOGGER.info("Set air quality thresholds for %s", entity_id)

    async def set_temperature_curve(call: ServiceCall) -> None:
        """Service to set temperature curve."""
        entity_ids = async_extract_entity_ids(hass, call)
        slope = call.data["slope"]
        offset = call.data["offset"]
        max_supply_temp = call.data.get("max_supply_temp")
        min_supply_temp = call.data.get("min_supply_temp")

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                await coordinator.async_write_register(
                    "heating_curve_slope",
                    _scale_for_register("heating_curve_slope", slope),
                    refresh=False,
                )
                await coordinator.async_write_register(
                    "heating_curve_offset",
                    _scale_for_register("heating_curve_offset", offset),
                    refresh=False,
                )

                if max_supply_temp is not None:
                    await coordinator.async_write_register(
                        "max_supply_temperature",
                        _scale_for_register("max_supply_temperature", max_supply_temp),
                        refresh=False,
                    )

                if min_supply_temp is not None:
                    await coordinator.async_write_register(
                        "min_supply_temperature",
                        _scale_for_register("min_supply_temperature", min_supply_temp),
                        refresh=False,
                    )

                await coordinator.async_request_refresh()
                _LOGGER.info("Set temperature curve for %s", entity_id)

    async def reset_filters(call: ServiceCall) -> None:
        """Service to reset filter counter."""
        entity_ids = async_extract_entity_ids(hass, call)
        filter_type = call.data["filter_type"]

        filter_type_map = {"presostat": 1, "flat_filters": 2, "cleanpad": 3, "cleanpad_pure": 4}
        filter_value = filter_type_map[filter_type]

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                await coordinator.async_write_register("filter_change", filter_value, refresh=False)
                await coordinator.async_request_refresh()
                _LOGGER.info("Reset filters for %s", entity_id)

    async def reset_settings(call: ServiceCall) -> None:
        """Service to reset settings."""
        entity_ids = async_extract_entity_ids(hass, call)
        reset_type = call.data["reset_type"]

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                if reset_type in ["user_settings", "all_settings"]:
                    await coordinator.async_write_register("hard_reset_settings", 1, refresh=False)

                if reset_type in ["schedule_settings", "all_settings"]:
                    await coordinator.async_write_register("hard_reset_schedule", 1, refresh=False)

                await coordinator.async_request_refresh()
                _LOGGER.info("Reset settings (%s) for %s", reset_type, entity_id)

    async def start_pressure_test(call: ServiceCall) -> None:
        """Service to start pressure test."""
        entity_ids = async_extract_entity_ids(hass, call)

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                # Trigger pressure test by setting current day and time
                now = dt_util.now()
                day_of_week = now.weekday()  # 0 = Monday
                time_hhmm = now.hour * 100 + now.minute

                await coordinator.async_write_register("pres_check_day", day_of_week, refresh=False)
                await coordinator.async_write_register("pres_check_time", time_hhmm, refresh=False)
                await coordinator.async_request_refresh()
                _LOGGER.info("Started pressure test for %s", entity_id)

    async def set_modbus_parameters(call: ServiceCall) -> None:
        """Service to set Modbus parameters."""
        entity_ids = async_extract_entity_ids(hass, call)
        port = call.data["port"]
        baud_rate = call.data.get("baud_rate")
        parity = call.data.get("parity")
        stop_bits = call.data.get("stop_bits")

        baud_map = {
            "4800": 0,
            "9600": 1,
            "14400": 2,
            "19200": 3,
            "28800": 4,
            "38400": 5,
            "57600": 6,
            "76800": 7,
            "115200": 8,
        }
        parity_map = {"none": 0, "even": 1, "odd": 2}
        stop_map = {"1": 0, "2": 1}

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                port_prefix = "uart0" if port == "air_b" else "uart1"

                if baud_rate:
                    await coordinator.async_write_register(
                        f"{port_prefix}_baud", baud_map[baud_rate], refresh=False
                    )

                if parity:
                    await coordinator.async_write_register(
                        f"{port_prefix}_parity", parity_map[parity], refresh=False
                    )

                if stop_bits:
                    await coordinator.async_write_register(
                        f"{port_prefix}_stop", stop_map[stop_bits], refresh=False
                    )

                await coordinator.async_request_refresh()
                _LOGGER.info("Set Modbus parameters for %s", entity_id)

    async def set_device_name(call: ServiceCall) -> None:
        """Service to set device name."""
        entity_ids = async_extract_entity_ids(hass, call)
        device_name = call.data["device_name"]

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                # Convert string to 16-bit register values (ASCII)
                name_bytes = device_name.encode("ascii")[:16].ljust(16, b"\x00")

                for i in range(8):  # 8 registers for 16 characters
                    char1 = name_bytes[i * 2]
                    char2 = name_bytes[i * 2 + 1]
                    reg_value = (char1 << 8) | char2
                    await coordinator.async_write_register(
                        f"device_name_{i + 1}", reg_value, refresh=False
                    )

                await coordinator.async_request_refresh()
                _LOGGER.info("Set device name to '%s' for %s", device_name, entity_id)

    async def refresh_device_data(call: ServiceCall) -> None:
        """Service to refresh device data."""
        entity_ids = async_extract_entity_ids(hass, call)

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                await coordinator.async_request_refresh()
                _LOGGER.info("Refreshed device data for %s", entity_id)

    # Register all services
    hass.services.async_register(
        DOMAIN, "set_special_mode", set_special_mode, SET_SPECIAL_MODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_airflow_schedule", set_airflow_schedule, SET_AIRFLOW_SCHEDULE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_bypass_parameters", set_bypass_parameters, SET_BYPASS_PARAMETERS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_gwc_parameters", set_gwc_parameters, SET_GWC_PARAMETERS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "set_air_quality_thresholds",
        set_air_quality_thresholds,
        SET_AIR_QUALITY_THRESHOLDS_SCHEMA,
    )  # noqa: E501
    hass.services.async_register(
        DOMAIN, "set_temperature_curve", set_temperature_curve, SET_TEMPERATURE_CURVE_SCHEMA
    )
    hass.services.async_register(DOMAIN, "reset_filters", reset_filters, RESET_FILTERS_SCHEMA)
    hass.services.async_register(DOMAIN, "reset_settings", reset_settings, RESET_SETTINGS_SCHEMA)
    hass.services.async_register(
        DOMAIN, "start_pressure_test", start_pressure_test, START_PRESSURE_TEST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_modbus_parameters", set_modbus_parameters, SET_MODBUS_PARAMETERS_SCHEMA
    )
    hass.services.async_register(DOMAIN, "set_device_name", set_device_name, SET_DEVICE_NAME_SCHEMA)
    hass.services.async_register(
        DOMAIN, "refresh_device_data", refresh_device_data, REFRESH_DEVICE_DATA_SCHEMA
    )

    _LOGGER.info("ThesslaGreen Modbus services registered successfully")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services for ThesslaGreen Modbus integration."""
    services = [
        "set_special_mode",
        "set_airflow_schedule",
        "set_bypass_parameters",
        "set_gwc_parameters",
        "set_air_quality_thresholds",
        "set_temperature_curve",
        "reset_filters",
        "reset_settings",
        "start_pressure_test",
        "set_modbus_parameters",
        "set_device_name",
        "refresh_device_data",
    ]

    for service in services:
        hass.services.async_remove(DOMAIN, service)

    _LOGGER.info("ThesslaGreen Modbus services unloaded")


def _get_coordinator_from_entity_id(hass: HomeAssistant, entity_id: str):
    """Get coordinator from entity ID using entity registry."""
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(entity_id) if entity_registry else None
    if not entry:
        return None
    return hass.data.get(DOMAIN, {}).get(entry.config_entry_id)
