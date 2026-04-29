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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    SPECIAL_FUNCTION_MAP,
    TEMPERATURE_MAX_C,
    TEMPERATURE_MIN_C,
    TEMPERATURE_STEP_C,
    holding_registers,
)
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity

_FEATURE_TARGET_TEMPERATURE = ClimateEntityFeature.TARGET_TEMPERATURE
_FEATURE_FAN_MODE = ClimateEntityFeature.FAN_MODE
_FEATURE_PRESET_MODE = ClimateEntityFeature.PRESET_MODE
_FEATURE_TURN_ON = ClimateEntityFeature.TURN_ON
_FEATURE_TURN_OFF = ClimateEntityFeature.TURN_OFF

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data
    if coordinator.capabilities.basic_control:
        entities = [ThesslaGreenClimate(coordinator)]
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning("Cancelled while adding climate entity, retrying without initial state")
            async_add_entities(entities, False)
            return
        _LOGGER.debug("Climate entity created for %s", coordinator.device_name)
    else:
        _LOGGER.info("Entity skipped due to capability: basic_control not supported")


class ThesslaGreenClimate(ThesslaGreenEntity, ClimateEntity):
    def __init__(self, coordinator: ThesslaGreenModbusCoordinator) -> None:
        super().__init__(coordinator, "climate_control", -1)
        self._attr_translation_key = "thessla_green_climate"
        self._attr_has_entity_name = True
        self._attr_supported_features = (
            _FEATURE_TARGET_TEMPERATURE | _FEATURE_FAN_MODE | _FEATURE_PRESET_MODE | _FEATURE_TURN_ON | _FEATURE_TURN_OFF
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = TEMPERATURE_STEP_C
        self._attr_min_temp = TEMPERATURE_MIN_C
        self._attr_max_temp = TEMPERATURE_MAX_C
        self._attr_target_temperature_step = TEMPERATURE_STEP_C
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.FAN_ONLY]
        self._attr_preset_modes = PRESET_MODES

    @property
    def current_temperature(self) -> float | None:
        return _first_numeric(self.coordinator.data, ("supply_temperature", "ambient_temperature"))

    @property
    def target_temperature(self) -> float | None:
        return _first_numeric(self.coordinator.data, TEMPERATURE_KEYS)

    @property
    def hvac_mode(self) -> HVACMode:
        return _hvac_mode_from_data(self.coordinator.data)

    @property
    def hvac_action(self) -> HVACAction:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self.coordinator.data.get("heating_cable", False):
            return HVACAction.HEATING
        if self.coordinator.data.get("bypass", False):
            return HVACAction.COOLING
        if self.coordinator.data.get("power_supply_fans", False):
            return HVACAction.FAN
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str | None:
        airflow = self.coordinator.data.get("air_flow_rate_manual") or self.coordinator.data.get("air_flow_rate_temporary_2")
        if not airflow:
            return None
        min_pct, max_pct = self._percentage_limits()
        rounded = int((airflow + 5) / 10) * 10
        return f"{max(min_pct, min(max_pct, rounded))}%"

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

    @property
    def preset_mode(self) -> str | None:
        return _preset_from_special_mode(self.coordinator.data.get("special_mode", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _extra_state_attributes(self.coordinator.data)

    async def _write_register(self, register: str, value: Any, *, refresh: bool = False) -> Any:  # type: ignore[override]
        try:
            return await self.coordinator.async_write_register(register, value, refresh=refresh, offset=0)
        except TypeError:
            return await self.coordinator.async_write_register(register, value, refresh=refresh)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            success = await self._write_register("on_off_panel_mode", 0, refresh=False)
        else:
            power_on_success = await self._write_register("on_off_panel_mode", 1, refresh=False)
            if not power_on_success:
                _LOGGER.warning("Power-on failed when setting HVAC mode to %s, retrying", hvac_mode)
                power_on_success = await self._write_register("on_off_panel_mode", 1, refresh=False)
            if not power_on_success:
                _LOGGER.error("Failed to enable device before setting HVAC mode to %s", hvac_mode)
                return
            success = await self._write_register("mode", HVAC_MODE_REVERSE_MAP.get(hvac_mode, 0), refresh=False)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set HVAC mode to %s", hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        coordinator_data = self.coordinator.data or {}
        if coordinator_data.get("mode") == 2:
            success = await self.coordinator.async_write_temporary_temperature(float(temperature), refresh=False)
            if success:
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to set temporary target temperature to %s°C", temperature)
            return
        success = True
        if "comfort_temperature" in holding_registers():
            success = await self.coordinator.async_write_register("comfort_temperature", temperature, refresh=False, offset=0)
        if success:
            success = await self._write_register("required_temperature", temperature, refresh=False)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set target temperature to %s°C", temperature)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        try:
            airflow = int(fan_mode.rstrip("%"))
            min_pct, max_pct = self._percentage_limits()
            airflow = max(min_pct, min(max_pct, airflow))
            success = await self._write_register("air_flow_rate_manual", airflow, refresh=False)
            if success:
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to set fan mode to %s", fan_mode)
        except ValueError:
            _LOGGER.error("Invalid fan mode format: %s", fan_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        success = await self._write_register("on_off_panel_mode", 1, refresh=False)
        if success:
            success = await self._write_register("special_mode", _special_mode_from_preset(preset_mode), refresh=False)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set preset mode to %s", preset_mode)

    async def async_turn_on(self) -> None:
        success = await self._write_register("on_off_panel_mode", 1, refresh=False)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        success = await self._write_register("on_off_panel_mode", 0, refresh=False)
        if success:
            await self.coordinator.async_request_refresh()

    @property
    def name(self) -> str:
        scan_name = getattr(self.coordinator, "device_scan_result", {}).get("device_info", {}).get("device_name")
        base = scan_name or getattr(self.coordinator, "device_name", getattr(self.coordinator, "_device_name", "ThesslaGreen"))
        return f"{base} Rekuperator"

    @property
    def hvac_modes(self) -> list[HVACMode]:
        return list(getattr(self, "_attr_hvac_modes", [HVACMode.OFF, HVACMode.AUTO]))

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and "on_off_panel_mode" in self.coordinator.data
