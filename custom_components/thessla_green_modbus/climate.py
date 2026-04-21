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

# ClimateEntityFeature.TURN_ON / TURN_OFF are guaranteed in required HA versions.
_FEATURE_TARGET_TEMPERATURE = ClimateEntityFeature.TARGET_TEMPERATURE
_FEATURE_FAN_MODE = ClimateEntityFeature.FAN_MODE
_FEATURE_PRESET_MODE = ClimateEntityFeature.PRESET_MODE
_FEATURE_TURN_ON = ClimateEntityFeature.TURN_ON
_FEATURE_TURN_OFF = ClimateEntityFeature.TURN_OFF

_LOGGER = logging.getLogger(__name__)

# HVAC mode mappings (from device mode register)
HVAC_MODE_MAP = {
    0: HVACMode.AUTO,  # Automatic mode
    1: HVACMode.FAN_ONLY,  # Manual mode
    2: HVACMode.FAN_ONLY,  # Temporary boost mode
}

HVAC_MODE_REVERSE_MAP = {
    HVACMode.AUTO: 0,
    HVACMode.FAN_ONLY: 1,  # Manual and temporary modes use fan-only
}

# Preset modes for special functions
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen climate entity.

    Home Assistant calls this during platform setup even though it is not
    referenced elsewhere in the source tree.
    """
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data

    # Create climate entity only when basic control is reported by capabilities.
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
    """Enhanced climate entity for ThesslaGreen AirPack.

    Many methods and ``_attr_*`` attributes implement the Home Assistant
    ``ClimateEntity`` API and are accessed by the framework at runtime.
    """

    def __init__(self, coordinator: ThesslaGreenModbusCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, "climate_control", -1)
        self._attr_translation_key = "thessla_green_climate"
        self._attr_has_entity_name = True

        # Climate features
        self._attr_supported_features = (
            _FEATURE_TARGET_TEMPERATURE
            | _FEATURE_FAN_MODE
            | _FEATURE_PRESET_MODE
            | _FEATURE_TURN_ON
            | _FEATURE_TURN_OFF
        )

        # Temperature settings
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = TEMPERATURE_STEP_C
        self._attr_min_temp = TEMPERATURE_MIN_C
        self._attr_max_temp = TEMPERATURE_MAX_C
        self._attr_target_temperature_step = TEMPERATURE_STEP_C

        # HVAC modes — FAN_ONLY (manual) requires the `mode` holding register
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.AUTO,
            HVACMode.FAN_ONLY,
        ]

        # Fan modes are computed dynamically via the fan_modes property

        # Preset modes
        self._attr_preset_modes = PRESET_MODES

        _LOGGER.debug("Climate entity initialized")

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature from supply sensor."""
        value = self.coordinator.data.get("supply_temperature")
        if isinstance(value, int | float):
            return float(value)
        value = self.coordinator.data.get("ambient_temperature")
        if isinstance(value, int | float):
            return float(value)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature if available."""
        data = self.coordinator.data
        for key in (
            "comfort_temperature",
            "required_temperature",
            "required_temp",
        ):
            value = data.get(key)
            if isinstance(value, int | float):
                return float(value)
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        # Check if device is turned off
        if self.coordinator.data.get("on_off_panel_mode") == 0:
            return HVACMode.OFF

        # Get mode from device
        device_mode = self.coordinator.data.get("mode", 0)
        return HVAC_MODE_MAP.get(device_mode, HVACMode.AUTO)

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        # Check if heating is active
        if self.coordinator.data.get("heating_cable", False):
            return HVACAction.HEATING

        # Check if cooling/bypass is active
        if self.coordinator.data.get("bypass", False):
            return HVACAction.COOLING

        # Check if fans are running
        if self.coordinator.data.get("power_supply_fans", False):
            return HVACAction.FAN

        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str | None:
        """Return current fan mode."""
        # Get airflow rate from manual or current setting
        airflow = self.coordinator.data.get("air_flow_rate_manual")
        if not airflow:
            airflow = self.coordinator.data.get("air_flow_rate_temporary_2")

        if not airflow:
            return None

        min_pct, max_pct = self._percentage_limits()
        rounded = int((airflow + 5) / 10) * 10
        return f"{max(min_pct, min(max_pct, rounded))}%"

    @property
    def fan_modes(self) -> list[str] | None:
        """Return available fan modes based on device limits."""

        min_pct, max_pct = self._percentage_limits()
        if max_pct < min_pct:
            return None
        start = min_pct
        modes = [f"{pct}%" for pct in range(start, max_pct + 1, 10)]
        if not modes:
            return None
        if modes[-1] != f"{max_pct}%":
            modes.append(f"{max_pct}%")
        return modes

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        special_mode = self.coordinator.data.get("special_mode", 0)

        if special_mode == 0:
            return "none"

        # Check for active special function
        for preset, bit_value in SPECIAL_FUNCTION_MAP.items():
            if special_mode == bit_value:
                return str(preset)

        return "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}

        # Temperature sensors
        if "outside_temperature" in self.coordinator.data:
            attrs["outside_temperature"] = self.coordinator.data["outside_temperature"]
        if "exhaust_temperature" in self.coordinator.data:
            attrs["exhaust_temperature"] = self.coordinator.data["exhaust_temperature"]
        if "gwc_temperature" in self.coordinator.data:
            attrs["gwc_temperature"] = self.coordinator.data["gwc_temperature"]

        # Airflow
        if "supply_flow_rate" in self.coordinator.data:
            attrs["supply_airflow"] = self.coordinator.data["supply_flow_rate"]
        if "exhaust_flow_rate" in self.coordinator.data:
            attrs["exhaust_airflow"] = self.coordinator.data["exhaust_flow_rate"]

        # Special systems
        attrs["bypass_active"] = self.coordinator.data.get("bypass", False)
        attrs["gwc_active"] = self.coordinator.data.get("gwc", False)
        attrs["heating_active"] = self.coordinator.data.get("heating_cable", False)

        # Air quality (if available)
        if "co2_level" in self.coordinator.data:
            attrs["co2_level"] = self.coordinator.data["co2_level"]
        if "humidity_indoor" in self.coordinator.data:
            attrs["humidity"] = self.coordinator.data["humidity_indoor"]

        return attrs

    async def _write_register(
        self, register: str, value: Any, *, refresh: bool = False
    ) -> Any:
        """Write register and gracefully handle coordinators with differing signatures."""

        try:
            return await self.coordinator.async_write_register(
                register,
                value,
                refresh=refresh,
                offset=0,
            )
        except TypeError:
            return await self.coordinator.async_write_register(register, value, refresh=refresh)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        _LOGGER.debug("Setting HVAC mode to %s", hvac_mode)

        if hvac_mode == HVACMode.OFF:
            success = await self._write_register("on_off_panel_mode", 0, refresh=False)
        else:
            # Turn on device first and capture result
            power_on_success = await self._write_register(
                "on_off_panel_mode", 1, refresh=False
            )

            # Retry once if power on failed
            if not power_on_success:
                _LOGGER.warning("Power-on failed when setting HVAC mode to %s, retrying", hvac_mode)
                power_on_success = await self._write_register(
                    "on_off_panel_mode", 1, refresh=False
                )

            if not power_on_success:
                _LOGGER.error("Failed to enable device before setting HVAC mode to %s", hvac_mode)
                return

            # Set mode
            device_mode = HVAC_MODE_REVERSE_MAP.get(hvac_mode, 0)
            success = await self._write_register("mode", device_mode, refresh=False)

        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set HVAC mode to %s", hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        _LOGGER.debug("Setting target temperature to %s°C", temperature)

        coordinator_data = self.coordinator.data or {}
        if coordinator_data.get("mode") == 2:
            success = await self.coordinator.async_write_temporary_temperature(
                float(temperature), refresh=False
            )
            if success:
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to set temporary target temperature to %s°C", temperature)
            return

        success = True
        if "comfort_temperature" in holding_registers():
            success = await self.coordinator.async_write_register(
                "comfort_temperature", temperature, refresh=False, offset=0
            )

        if success:
            success = await self._write_register(
                "required_temperature", temperature, refresh=False
            )

        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set target temperature to %s°C", temperature)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode (airflow rate)."""
        try:
            # Extract percentage from fan mode string
            airflow = int(fan_mode.rstrip("%"))
            _LOGGER.debug("Setting fan mode to %s%% airflow", airflow)

            # Set manual airflow rate
            min_pct, max_pct = self._percentage_limits()
            airflow = max(min_pct, min(max_pct, airflow))
            success = await self._write_register(
                "air_flow_rate_manual", airflow, refresh=False
            )

            if success:
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to set fan mode to %s", fan_mode)
        except ValueError:
            _LOGGER.error("Invalid fan mode format: %s", fan_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode (special function)."""
        _LOGGER.debug("Setting preset mode to %s", preset_mode)

        if preset_mode == "none":
            # Clear all special modes
            special_mode_value = 0
        else:
            # Set specific special mode
            special_mode_value = SPECIAL_FUNCTION_MAP.get(preset_mode, 0)

        success = await self._write_register("on_off_panel_mode", 1, refresh=False)
        if success:
            success = await self._write_register(
                "special_mode", special_mode_value, refresh=False
            )

        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set preset mode to %s", preset_mode)

    async def async_turn_on(self) -> None:
        """Turn the climate entity on."""
        _LOGGER.debug("Turning on climate entity")
        success = await self._write_register("on_off_panel_mode", 1, refresh=False)

        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn on climate entity")

    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        _LOGGER.debug("Turning off climate entity")
        success = await self._write_register("on_off_panel_mode", 0, refresh=False)

        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn off climate entity")

    @property
    def name(self) -> str:
        scan_name = (
            getattr(self.coordinator, "device_scan_result", {})
            .get("device_info", {})
            .get("device_name")
        )
        base = scan_name or getattr(
            self.coordinator,
            "device_name",
            getattr(self.coordinator, "_device_name", "ThesslaGreen"),
        )
        return f"{base} Rekuperator"

    @property
    def hvac_modes(self) -> list[HVACMode]:
        return list(getattr(self, "_attr_hvac_modes", [HVACMode.OFF, HVACMode.AUTO]))

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and "on_off_panel_mode" in self.coordinator.data
