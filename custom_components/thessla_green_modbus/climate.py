"""Climate entity for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymodbus.exceptions import ConnectionException, ModbusException

from .const import (
    SPECIAL_FUNCTION_MAP,
    TEMPERATURE_MAX_C,
    TEMPERATURE_MIN_C,
    TEMPERATURE_STEP_C,
)
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .optimistic import OptimisticState
from .registers.maps import holding_registers

_FEATURE_TARGET_TEMPERATURE = ClimateEntityFeature.TARGET_TEMPERATURE
_FEATURE_FAN_MODE = ClimateEntityFeature.FAN_MODE
_FEATURE_PRESET_MODE = ClimateEntityFeature.PRESET_MODE
_FEATURE_TURN_ON = ClimateEntityFeature.TURN_ON
_FEATURE_TURN_OFF = ClimateEntityFeature.TURN_OFF

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

HVAC_MODE_MAP = {0: HVACMode.AUTO, 1: HVACMode.FAN_ONLY, 2: HVACMode.FAN_ONLY}
HVAC_MODE_REVERSE_MAP = {HVACMode.AUTO: 0, HVACMode.FAN_ONLY: 1}

PRESET_MODES = [
    "none",
    "eco",
    "boost",
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

TEMPERATURE_KEYS = ("comfort_temperature", "required_temperature", "required_temp")
EXTRA_ATTRS_PASSTHROUGH = {
    "outside_temperature": "outside_temperature",
    "exhaust_temperature": "exhaust_temperature",
    "gwc_temperature": "gwc_temperature",
    "supply_flow_rate": "supply_airflow",
    "exhaust_flow_rate": "exhaust_airflow",
    "co2_level": "co2_level",
    "humidity_indoor": "humidity",
}
_WRITE_ERRORS = (ModbusException, ConnectionException, TimeoutError, OSError)


def _first_numeric(data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, int | float):
            return float(value)
    return None


def _preset_from_special_mode(special_mode: Any) -> str:
    if special_mode == 0:
        return "none"
    for preset, bit_value in SPECIAL_FUNCTION_MAP.items():
        if special_mode == bit_value:
            return str(preset)
    return "none"


def _special_mode_from_preset(preset_mode: str) -> int:
    return 0 if preset_mode == "none" else SPECIAL_FUNCTION_MAP.get(preset_mode, 0)


def _hvac_mode_from_data(data: dict[str, Any]) -> HVACMode:
    if data.get("on_off_panel_mode") == 0:
        return HVACMode.OFF
    return HVAC_MODE_MAP.get(data.get("mode", 0), HVACMode.AUTO)


def _extra_state_attributes(data: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "bypass_active": data.get("bypass", False),
        "gwc_active": data.get("gwc", False),
        "heating_active": data.get("heating_cable", False),
    }
    for source_key, attr_key in EXTRA_ATTRS_PASSTHROUGH.items():
        if source_key in data:
            attrs[attr_key] = data[source_key]
    return attrs


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data
    if coordinator.device_client.capabilities.basic_control:
        # The coordinator completes its initial refresh before platforms are
        # forwarded, so requesting another update here only delays setup.
        async_add_entities([ThesslaGreenClimate(coordinator)], False)
        _LOGGER.debug("Climate entity created for %s", coordinator.device_client.device_name)
    else:
        _LOGGER.info("Entity skipped due to capability: basic_control not supported")


class ThesslaGreenClimate(ThesslaGreenEntity, ClimateEntity):
    def __init__(self, coordinator: ThesslaGreenModbusCoordinator) -> None:
        super().__init__(coordinator, "climate_control", -1)
        self._attr_translation_key = "thessla_green_climate"
        self._attr_has_entity_name = True
        self._attr_supported_features = (
            _FEATURE_TARGET_TEMPERATURE
            | _FEATURE_FAN_MODE
            | _FEATURE_PRESET_MODE
            | _FEATURE_TURN_ON
            | _FEATURE_TURN_OFF
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = TEMPERATURE_STEP_C
        self._attr_min_temp = TEMPERATURE_MIN_C
        self._attr_max_temp = TEMPERATURE_MAX_C
        self._attr_target_temperature_step = TEMPERATURE_STEP_C
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.FAN_ONLY]
        self._attr_preset_modes = PRESET_MODES
        self._optimistic = OptimisticState()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Drop optimistic command fields once the confirmed state matches."""
        self._clear_optimistic_if_confirmed()
        super()._handle_coordinator_update()

    def _clear_optimistic_if_confirmed(self) -> None:
        """Clear pending command fields once coordinator data confirms them."""
        self._optimistic.clear_if_confirmed(
            "target_temperature",
            self._confirmed_target_temperature(),
            tolerance=TEMPERATURE_STEP_C / 2,
        )
        self._optimistic.clear_if_confirmed("hvac_mode", self._confirmed_hvac_mode())
        self._optimistic.clear_if_confirmed("fan_mode", self._confirmed_fan_mode())
        self._optimistic.clear_if_confirmed("preset_mode", self._confirmed_preset_mode())

    def _set_optimistic(self, key: str, value: Any) -> None:
        """Record an optimistic command value and push it to the GUI."""
        self._optimistic.set_pending(key, value)
        if self.hass is not None:
            self.async_write_ha_state()

    @property
    def current_temperature(self) -> float | None:
        return _first_numeric(self.coordinator.data, ("supply_temperature", "ambient_temperature"))

    def _confirmed_target_temperature(self) -> float | None:
        return _first_numeric(self.coordinator.data, TEMPERATURE_KEYS)

    @property
    def target_temperature(self) -> float | None:
        pending = self._optimistic.get_pending("target_temperature")
        if pending is not None:
            return float(pending)
        return self._confirmed_target_temperature()

    def _confirmed_hvac_mode(self) -> HVACMode:
        return _hvac_mode_from_data(self.coordinator.data)

    @property
    def hvac_mode(self) -> HVACMode:
        pending = self._optimistic.get_pending("hvac_mode")
        if pending is not None:
            return pending
        return self._confirmed_hvac_mode()

    @property
    def hvac_action(self) -> HVACAction:
        if self._confirmed_hvac_mode() == HVACMode.OFF:
            return HVACAction.OFF
        if self.coordinator.data.get("heating_cable", False):
            return HVACAction.HEATING
        if self.coordinator.data.get("bypass", False):
            return HVACAction.COOLING
        if self.coordinator.data.get("power_supply_fans", False):
            return HVACAction.FAN
        return HVACAction.IDLE

    def _confirmed_fan_mode(self) -> str | None:
        airflow = self.coordinator.data.get("air_flow_rate_manual") or self.coordinator.data.get(
            "air_flow_rate_temporary_2"
        )
        if not airflow:
            return None
        min_pct, max_pct = self._percentage_limits()
        rounded = int((airflow + 5) / 10) * 10
        return f"{max(min_pct, min(max_pct, rounded))}%"

    @property
    def fan_mode(self) -> str | None:
        pending = self._optimistic.get_pending("fan_mode")
        if pending is not None:
            return pending
        return self._confirmed_fan_mode()

    @property
    def fan_modes(self) -> list[str] | None:
        min_pct, max_pct = self._percentage_limits()
        if max_pct < min_pct:
            return None
        modes = [f"{pct}%" for pct in range(min_pct, max_pct + 1, 10)]
        if not modes:
            return None
        if modes[-1] != f"{max_pct}%":
            modes.append(f"{max_pct}%")
        return modes

    def _confirmed_preset_mode(self) -> str | None:
        return _preset_from_special_mode(self.coordinator.data.get("special_mode", 0))

    @property
    def preset_mode(self) -> str | None:
        pending = self._optimistic.get_pending("preset_mode")
        if pending is not None:
            return pending
        return self._confirmed_preset_mode()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _extra_state_attributes(self.coordinator.data)

    async def _write_register(self, register: str, value: Any, *, refresh: bool = False) -> None:  # type: ignore[override]
        """Write one climate register or raise a Home Assistant action error."""
        try:
            try:
                success = await self.coordinator.async_write_register(
                    register, value, refresh=refresh, offset=0, targeted_readback=False
                )
            except TypeError:
                success = await self.coordinator.async_write_register(
                    register, value, refresh=refresh, targeted_readback=False
                )
        except asyncio.CancelledError:
            raise
        except _WRITE_ERRORS as err:
            raise HomeAssistantError(f"Failed to write {register}: {err}") from err
        if not success:
            raise HomeAssistantError(f"Device did not confirm write to {register}.")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._write_register("on_off_panel_mode", 0, refresh=False)
        else:
            if hvac_mode not in HVAC_MODE_REVERSE_MAP:
                raise ServiceValidationError(f"Unsupported HVAC mode: {hvac_mode}")
            await self._write_register("on_off_panel_mode", 1, refresh=False)
            await self._write_register(
                "mode", HVAC_MODE_REVERSE_MAP[hvac_mode], refresh=False
            )
        self._set_optimistic("hvac_mode", hvac_mode)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        temperature = float(temperature)
        if not TEMPERATURE_MIN_C <= temperature <= TEMPERATURE_MAX_C:
            raise ServiceValidationError(
                f"Target temperature must be between {TEMPERATURE_MIN_C} and {TEMPERATURE_MAX_C} °C."
            )

        coordinator_data = self.coordinator.data or {}
        if coordinator_data.get("mode") == 2:
            try:
                success = await self.coordinator.async_write_temporary_temperature(
                    temperature, refresh=False
                )
            except asyncio.CancelledError:
                raise
            except _WRITE_ERRORS as err:
                raise HomeAssistantError(
                    f"Failed to set temporary target temperature: {err}"
                ) from err
            if not success:
                raise HomeAssistantError(
                    "Device did not confirm temporary target-temperature write."
                )
        else:
            available = self.coordinator.device_client.available_registers.get(
                "holding_registers", set()
            )
            if "comfort_temperature" in holding_registers() and "comfort_temperature" in available:
                await self._write_register("comfort_temperature", temperature, refresh=False)
            await self._write_register("required_temperature", temperature, refresh=False)

        self._set_optimistic("target_temperature", temperature)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        try:
            airflow = int(fan_mode.rstrip("%"))
        except (AttributeError, ValueError) as err:
            raise ServiceValidationError(f"Invalid fan mode: {fan_mode!r}") from err
        min_pct, max_pct = self._percentage_limits()
        if not min_pct <= airflow <= max_pct:
            raise ServiceValidationError(
                f"Fan mode must be between {min_pct}% and {max_pct}%."
            )
        await self._write_register("air_flow_rate_manual", airflow, refresh=False)
        self._set_optimistic("fan_mode", f"{airflow}%")
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in PRESET_MODES:
            raise ServiceValidationError(f"Unsupported preset mode: {preset_mode}")
        await self._write_register("on_off_panel_mode", 1, refresh=False)
        await self._write_register(
            "special_mode", _special_mode_from_preset(preset_mode), refresh=False
        )
        self._set_optimistic("preset_mode", preset_mode)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        await self._write_register("on_off_panel_mode", 1, refresh=False)
        self._set_optimistic(
            "hvac_mode", HVAC_MODE_MAP.get(self.coordinator.data.get("mode", 0), HVACMode.AUTO)
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self._write_register("on_off_panel_mode", 0, refresh=False)
        self._set_optimistic("hvac_mode", HVACMode.OFF)
        await self.coordinator.async_request_refresh()

    @property
    def hvac_modes(self) -> list[HVACMode]:
        return list(getattr(self, "_attr_hvac_modes", [HVACMode.OFF, HVACMode.AUTO]))

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and "on_off_panel_mode" in self.coordinator.data
