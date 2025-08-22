"""Service handlers for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_extract_entity_ids

try:  # pragma: no cover - handle missing Home Assistant util during tests
    from homeassistant.util import dt as dt_util
except (ModuleNotFoundError, ImportError):  # pragma: no cover
    class _DTUtil:
        """Fallback minimal dt util."""

        @staticmethod
        def now():
            from datetime import datetime

            return datetime.now()

        @staticmethod
        def utcnow():
            from datetime import datetime, timezone

            return datetime.now(timezone.utc)

    dt_util = _DTUtil()  # type: ignore

from .const import DOMAIN, SPECIAL_FUNCTION_MAP
from . import loader
from .const import (
    BYPASS_MODES,
    DAYS_OF_WEEK,
    DOMAIN,
    FILTER_TYPES,
    GWC_MODES,
    MODBUS_BAUD_RATES,
    MODBUS_PARITY,
    MODBUS_PORTS,
    MODBUS_STOP_BITS,
    PERIODS,
    RESET_TYPES,
    SPECIAL_FUNCTION_MAP,
    SPECIAL_MODE_OPTIONS,
)
from .entity_mappings import map_legacy_entity_id
from .scanner_core import ThesslaGreenDeviceScanner
from .modbus_exceptions import ConnectionException, ModbusException

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Map service parameters to corresponding register names
AIR_QUALITY_REGISTER_MAP = {
    "co2_low": "co2_threshold_low",
    "co2_medium": "co2_threshold_medium",
    "co2_high": "co2_threshold_high",
    "humidity_target": "humidity_target",
}


def _encode_for_register(register_name: str, value: Any) -> int:
    """Encode ``value`` for ``register_name`` using register metadata."""
    definition = loader.get_register_definition(register_name)
    return definition.encode(value)
def _extract_legacy_entity_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Return entity IDs from a service call handling legacy aliases."""

    raw_ids = call.data.get("entity_id")
    if raw_ids is None:
        return set()

    if isinstance(raw_ids, str):
        raw_ids = [raw_ids]
    else:
        raw_ids = list(raw_ids)

    mapped_ids = [map_legacy_entity_id(entity_id) for entity_id in raw_ids]
    mapped_call = ServiceCall(
        domain=getattr(call, "domain", DOMAIN),
        service=getattr(call, "service", ""),
        data={**call.data, "entity_id": mapped_ids},
        context=getattr(call, "context", None),
    )
    return cast(set[str], async_extract_entity_ids(hass, mapped_call))


# Service schemas
SET_SPECIAL_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("mode"): vol.In(SPECIAL_MODE_OPTIONS),
        vol.Optional("duration", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=480)),
    }
)

SET_AIRFLOW_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("day"): vol.In(DAYS_OF_WEEK),
        vol.Required("period"): vol.In(PERIODS),
        vol.Required("start_time"): cv.time,
        vol.Required("end_time"): cv.time,
        vol.Required("airflow_rate"): vol.All(vol.Coerce(int), vol.Range(min=10, max=100)),
        vol.Optional("temperature"): vol.All(vol.Coerce(float), vol.Range(min=16.0, max=30.0)),
    }
)

SET_BYPASS_PARAMETERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("mode"): vol.In(BYPASS_MODES),
        vol.Optional("min_outdoor_temperature"): vol.All(
            vol.Coerce(float), vol.Range(min=10.0, max=40.0)
        ),
    }
)

SET_GWC_PARAMETERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("mode"): vol.In(GWC_MODES),
        vol.Optional("min_air_temperature"): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=20.0)
        ),
        vol.Optional("max_air_temperature"): vol.All(
            vol.Coerce(float), vol.Range(min=30.0, max=80.0)
        ),
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
        vol.Required("filter_type"): vol.In(FILTER_TYPES),
    }
)

RESET_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("reset_type"): vol.In(RESET_TYPES),
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
        vol.Required("port"): vol.In(MODBUS_PORTS),
        vol.Optional("baud_rate"): vol.In(MODBUS_BAUD_RATES),
        vol.Optional("parity"): vol.In(MODBUS_PARITY),
        vol.Optional("stop_bits"): vol.In(MODBUS_STOP_BITS),
    }
)

SET_DEVICE_NAME_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("device_name"): vol.All(cv.string, vol.Length(min=1, max=16)),
    }
)

REFRESH_DEVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
    }
)

SCAN_ALL_REGISTERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for ThesslaGreen Modbus integration."""

    def _normalize_option(value: str) -> str:
        """Convert translation keys to internal option values."""
        if value and value.startswith(f"{DOMAIN}."):
            value = value.split(".", 1)[1]
        prefixes = [
            "special_mode_",
            "day_",
            "period_",
            "bypass_mode_",
            "gwc_mode_",
            "filter_type_",
            "reset_type_",
            "modbus_port_",
            "modbus_baud_rate_",
            "modbus_parity_",
            "modbus_stop_bits_",
        ]
        for prefix in prefixes:
            if value.startswith(prefix):
                return value[len(prefix) :]  # noqa: E203
        return value

    async def _write_register(
        coordinator: ThesslaGreenModbusCoordinator,
        register: str,
        value: Any,
        entity_id: str,
        action: str,
    ) -> bool:
        """Write to a register with error handling.

        Returns ``True`` if the register write succeeds, ``False`` otherwise.
        """
        try:
            return bool(
                await coordinator.async_write_register(
                    register, value, refresh=False
                )
            )
        except (ModbusException, ConnectionException) as err:
            _LOGGER.error(
                "Failed to %s for %s: %s", action, entity_id, err
            )
            return False

    async def set_special_mode(call: ServiceCall) -> None:
        """Service to set special mode."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        mode = _normalize_option(call.data["mode"])
        duration = call.data.get("duration", 0)

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                # Set special mode using the special_mode register
                special_mode_value = SPECIAL_FUNCTION_MAP.get(mode, 0)
                if not await _write_register(
                    coordinator,
                    "special_mode",
                    special_mode_value,
                    entity_id,
                    "set special mode",
                ):
                    _LOGGER.error(
                        "Failed to set special mode %s for %s", mode, entity_id
                    )
                    continue

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
                        if not await _write_register(
                            coordinator,
                            duration_register,
                            duration,
                            entity_id,
                            "set special mode",
                        ):
                            _LOGGER.error(
                                "Failed to set duration for %s on %s",
                                mode,
                                entity_id,
                            )
                            continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Set special mode %s for %s", mode, entity_id)

    async def set_airflow_schedule(call: ServiceCall) -> None:
        """Service to set airflow schedule."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        day = _normalize_option(call.data["day"])
        period = _normalize_option(call.data["period"])
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
        
        # Prepare start/end values as tuples so Register.encode can
        # handle conversion to the device format.
        start_value = (start_time.hour, start_time.minute)
        end_value = (end_time.hour, end_time.minute)

        # Format times in a user-friendly way for encoding
        start_value = f"{start_time.hour:02d}:{start_time.minute:02d}"
        end_value = f"{end_time.hour:02d}:{end_time.minute:02d}"
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

                # Write schedule values relying on register encode logic
                if not await _write_register(
                    coordinator,
                    start_register,
                    start_value,
                    entity_id,
                    "set airflow schedule",
                ):
                    _LOGGER.error("Failed to set schedule start for %s", entity_id)
                    continue
                if not await _write_register(
                    coordinator,
                    end_register,
                    end_value,
                    entity_id,
                    "set airflow schedule",
                ):
                    _LOGGER.error("Failed to set schedule end for %s", entity_id)
                    continue
                if not await _write_register(
                    coordinator,
                    flow_register,
                    airflow_rate,
                    entity_id,
                    "set airflow schedule",
                ):
                    _LOGGER.error("Failed to set schedule flow for %s", entity_id)
                    continue

                if temperature is not None:
                    if not await _write_register(
                        coordinator,
                        temp_register,
                        temperature,
                        entity_id,
                        "set airflow schedule",
                    ):
                        _LOGGER.error(
                            "Failed to set schedule temperature for %s", entity_id
                        )
                        continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Set airflow schedule for %s", entity_id)

    async def set_bypass_parameters(call: ServiceCall) -> None:
        """Service to set bypass parameters."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        mode = _normalize_option(call.data["mode"])
        min_temperature = call.data.get("min_outdoor_temperature")

        mode_map = {"auto": 0, "open": 1, "closed": 2}
        mode_value = mode_map[mode]

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                if not await _write_register(
                    coordinator,
                    "bypass_mode",
                    mode_value,
                    entity_id,
                    "set bypass parameters",
                ):
                    _LOGGER.error("Failed to set bypass mode for %s", entity_id)
                    continue

                if min_temperature is not None:
                    if not await _write_register(
                        coordinator,
                        "min_bypass_temperature",
                        min_temperature,
                        entity_id,
                        "set bypass parameters",
                    ):
                        _LOGGER.error(
                            "Failed to set bypass min temperature for %s", entity_id
                        )
                        continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Set bypass parameters for %s", entity_id)

    async def set_gwc_parameters(call: ServiceCall) -> None:
        """Service to set GWC parameters."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        mode = _normalize_option(call.data["mode"])
        min_air_temperature = call.data.get("min_air_temperature")
        max_air_temperature = call.data.get("max_air_temperature")

        mode_map = {"off": 0, "auto": 1, "forced": 2}
        mode_value = mode_map[mode]

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                if not await _write_register(
                    coordinator,
                    "gwc_mode",
                    mode_value,
                    entity_id,
                    "set GWC parameters",
                ):
                    _LOGGER.error("Failed to set GWC mode for %s", entity_id)
                    continue

                if min_air_temperature is not None:
                    if not await _write_register(
                        coordinator,
                        "min_gwc_air_temperature",
                        min_air_temperature,
                        entity_id,
                        "set GWC parameters",
                    ):
                        _LOGGER.error(
                            "Failed to set GWC min air temperature for %s", entity_id
                        )
                        continue

                if max_air_temperature is not None:
                    if not await _write_register(
                        coordinator,
                        "max_gwc_air_temperature",
                        max_air_temperature,
                        entity_id,
                        "set GWC parameters",
                    ):
                        _LOGGER.error(
                            "Failed to set GWC max air temperature for %s", entity_id
                        )
                        continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Set GWC parameters for %s", entity_id)

    async def set_air_quality_thresholds(call: ServiceCall) -> None:
        """Service to set air quality thresholds."""
        entity_ids = _extract_legacy_entity_ids(hass, call)

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                for param in [
                    "co2_low",
                    "co2_medium",
                    "co2_high",
                    "humidity_target",
                ]:
                    value = call.data.get(param)
                    if value is not None:
                        register_name = AIR_QUALITY_REGISTER_MAP[param]
                        if not await _write_register(
                            coordinator,
                            register_name,
                            value,
                            entity_id,
                            "set air quality thresholds",
                        ):
                            _LOGGER.error(
                                "Failed to set %s for %s", param, entity_id
                            )
                            success = False
                            break

                if not success:
                    continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Set air quality thresholds for %s", entity_id)

    async def set_temperature_curve(call: ServiceCall) -> None:
        """Service to set temperature curve."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        slope = call.data["slope"]
        offset = call.data["offset"]
        max_supply_temp = call.data.get("max_supply_temp")
        min_supply_temp = call.data.get("min_supply_temp")

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                if not await _write_register(
                    coordinator,
                    "heating_curve_slope",
                    slope,
                    entity_id,
                    "set temperature curve",
                ):
                    _LOGGER.error(
                        "Failed to set heating curve slope for %s", entity_id
                    )
                    continue
                if not await _write_register(
                    coordinator,
                    "heating_curve_offset",
                    offset,
                    entity_id,
                    "set temperature curve",
                ):
                    _LOGGER.error(
                        "Failed to set heating curve offset for %s", entity_id
                    )
                    continue

                if max_supply_temp is not None:
                    if not await _write_register(
                        coordinator,
                        "max_supply_temperature",
                        max_supply_temp,
                        entity_id,
                        "set temperature curve",
                    ):
                        _LOGGER.error(
                            "Failed to set max supply temperature for %s", entity_id
                        )
                        continue

                if min_supply_temp is not None:
                    if not await _write_register(
                        coordinator,
                        "min_supply_temperature",
                        min_supply_temp,
                        entity_id,
                        "set temperature curve",
                    ):
                        _LOGGER.error(
                            "Failed to set min supply temperature for %s", entity_id
                        )
                        continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Set temperature curve for %s", entity_id)

    async def reset_filters(call: ServiceCall) -> None:
        """Service to reset filter counter."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        filter_type = _normalize_option(call.data["filter_type"])

        filter_type_map = {"presostat": 1, "flat_filters": 2, "cleanpad": 3, "cleanpad_pure": 4}
        filter_value = filter_type_map[filter_type]

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                if not await _write_register(
                    coordinator,
                    "filter_change",
                    filter_value,
                    entity_id,
                    "reset filters",
                ):
                    _LOGGER.error("Failed to reset filters for %s", entity_id)
                    continue
                await coordinator.async_request_refresh()
                _LOGGER.info("Reset filters for %s", entity_id)

    async def reset_settings(call: ServiceCall) -> None:
        """Service to reset settings."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        reset_type = _normalize_option(call.data["reset_type"])

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                if reset_type in ["user_settings", "all_settings"]:
                    if not await _write_register(
                        coordinator,
                        "hard_reset_settings",
                        1,
                        entity_id,
                        "reset settings",
                    ):
                        _LOGGER.error(
                            "Failed to reset user settings for %s", entity_id
                        )
                        continue

                if reset_type in ["schedule_settings", "all_settings"]:
                    if not await _write_register(
                        coordinator,
                        "hard_reset_schedule",
                        1,
                        entity_id,
                        "reset settings",
                    ):
                        _LOGGER.error(
                            "Failed to reset schedule settings for %s", entity_id
                        )
                        continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Reset settings (%s) for %s", reset_type, entity_id)

    async def start_pressure_test(call: ServiceCall) -> None:
        """Service to start pressure test."""
        entity_ids = _extract_legacy_entity_ids(hass, call)

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                # Trigger pressure test by setting current day and time
                now = dt_util.now()
                day_of_week = now.weekday()  # 0 = Monday
                time_hhmm = now.hour * 100 + now.minute

                if not await _write_register(
                    coordinator,
                    "pres_check_day_2",
                    day_of_week,
                    entity_id,
                    "start pressure test",
                ):
                    _LOGGER.error("Failed to start pressure test for %s", entity_id)
                    continue
                if not await _write_register(
                    coordinator,
                    "pres_check_time_2",
                    time_hhmm,
                    entity_id,
                    "start pressure test",
                ):
                    _LOGGER.error("Failed to start pressure test for %s", entity_id)
                    continue
                await coordinator.async_request_refresh()
                _LOGGER.info("Started pressure test for %s", entity_id)

    async def set_modbus_parameters(call: ServiceCall) -> None:
        """Service to set Modbus parameters."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        port = _normalize_option(call.data["port"])
        baud_rate = call.data.get("baud_rate")
        parity = call.data.get("parity")
        stop_bits = call.data.get("stop_bits")
        if baud_rate:
            baud_rate = _normalize_option(baud_rate)
        if parity:
            parity = _normalize_option(parity)
        if stop_bits:
            stop_bits = _normalize_option(stop_bits)

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
                    if not await _write_register(
                        coordinator,
                        f"{port_prefix}_baud",
                        baud_map[baud_rate],
                        entity_id,
                        "set Modbus parameters",
                    ):
                        _LOGGER.error("Failed to set baud rate for %s", entity_id)
                        continue

                if parity:
                    if not await _write_register(
                        coordinator,
                        f"{port_prefix}_parity",
                        parity_map[parity],
                        entity_id,
                        "set Modbus parameters",
                    ):
                        _LOGGER.error("Failed to set parity for %s", entity_id)
                        continue

                if stop_bits:
                    if not await _write_register(
                        coordinator,
                        f"{port_prefix}_stop",
                        stop_map[stop_bits],
                        entity_id,
                        "set Modbus parameters",
                    ):
                        _LOGGER.error("Failed to set stop bits for %s", entity_id)
                        continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Set Modbus parameters for %s", entity_id)

    async def set_device_name(call: ServiceCall) -> None:
        """Service to set device name."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        device_name = call.data["device_name"]

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                # Convert string to 16-bit register values (ASCII)
                name_bytes = device_name.encode("ascii")[:16].ljust(16, b"\x00")

                success = True
                for i in range(8):  # 8 registers for 16 characters
                    char1 = name_bytes[i * 2]
                    char2 = name_bytes[i * 2 + 1]
                    reg_value = (char1 << 8) | char2
                    if not await _write_register(
                        coordinator,
                        f"device_name_{i + 1}",
                        reg_value,
                        entity_id,
                        "set device name",
                    ):
                        _LOGGER.error(
                            "Failed to set device name for %s", entity_id
                        )
                        success = False
                        break

                if not success:
                    continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Set device name to '%s' for %s", device_name, entity_id)

    async def refresh_device_data(call: ServiceCall) -> None:
        """Service to refresh device data."""
        entity_ids = _extract_legacy_entity_ids(hass, call)

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                await coordinator.async_request_refresh()
                _LOGGER.info("Refreshed device data for %s", entity_id)
    async def get_unknown_registers(call: ServiceCall) -> None:
        """Service to emit unknown registers via an event."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                hass.bus.async_fire(
                    f"{DOMAIN}_unknown_registers",
                    {
                        "entity_id": entity_id,
                        "unknown_registers": coordinator.unknown_registers,
                        "scanned_registers": coordinator.scanned_registers,
                    },
                )
    async def scan_all_registers(call: ServiceCall) -> dict[str, Any] | None:
        """Service to perform a full register scan."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        results: dict[str, Any] = {}

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if not coordinator:
                continue

            scanner = await ThesslaGreenDeviceScanner.create(
                host=coordinator.host,
                port=coordinator.port,
                slave_id=coordinator.slave_id,
                timeout=coordinator.timeout,
                retry=coordinator.retry,
                scan_uart_settings=coordinator.scan_uart_settings,
                skip_known_missing=False,
                full_register_scan=True,
            )
            try:
                scan_result = await scanner.scan_device()
            finally:
                await scanner.close()

            coordinator.device_scan_result = scan_result

            unknown_registers = scan_result.get("unknown_registers", {})
            summary = {
                "register_count": scan_result.get("register_count", 0),
                "unknown_register_count": sum(len(v) for v in unknown_registers.values()),
            }

            results[entity_id] = {
                "unknown_registers": unknown_registers,
                "summary": summary,
            }
            _LOGGER.info(
                "Full register scan for %s completed: %s, unknown registers: %s",
                entity_id,
                summary,
                unknown_registers,
            )

        return results or None

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
    hass.services.async_register(
        DOMAIN, "get_unknown_registers", get_unknown_registers, REFRESH_DEVICE_DATA_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "scan_all_registers", scan_all_registers, SCAN_ALL_REGISTERS_SCHEMA
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
        "get_unknown_registers",
        "scan_all_registers",
    ]

    for service in services:
        hass.services.async_remove(DOMAIN, service)

    _LOGGER.info("ThesslaGreen Modbus services unloaded")


def _get_coordinator_from_entity_id(
    hass: HomeAssistant, entity_id: str
) -> ThesslaGreenModbusCoordinator | None:
    """Get coordinator from entity ID using entity registry.

    Legacy entity IDs are transparently mapped to their new counterparts to
    maintain backward compatibility with older automations.
    """

    mapped_entity_id = map_legacy_entity_id(entity_id)

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(mapped_entity_id) if entity_registry else None
    if not entry:
        return None
    return cast(
        "ThesslaGreenModbusCoordinator | None",
        hass.data.get(DOMAIN, {}).get(entry.config_entry_id),
    )
