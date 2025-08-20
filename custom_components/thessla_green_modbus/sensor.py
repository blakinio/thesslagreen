"""Sensors for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast


from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, STATE_UNAVAILABLE

from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_AIRFLOW_UNIT,
    DEFAULT_AIRFLOW_UNIT,
    AIRFLOW_UNIT_PERCENTAGE,
    AIRFLOW_RATE_REGISTERS,
    SENSOR_UNAVAILABLE,
)
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .entity_mappings import ENTITY_MAPPINGS
from .utils import TIME_REGISTER_PREFIXES

_LOGGER = logging.getLogger(__name__)
SENSOR_DEFINITIONS: dict[str, dict[str, Any]] = ENTITY_MAPPINGS.get("sensor", {})


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen sensor entities based on available registers."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    temp_created = 0
    temp_skipped = 0

    # Create sensors only for registers discovered by
    # ThesslaGreenDeviceScanner.scan_device()
    for register_name, sensor_def in SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]
        is_temp = sensor_def.get("device_class") == SensorDeviceClass.TEMPERATURE

        # Check if this register is available on the device
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenSensor(coordinator, register_name, sensor_def))
            _LOGGER.debug("Created sensor: %s", sensor_def["translation_key"])
            if is_temp:
                temp_created += 1
        elif is_temp:
            temp_skipped += 1


    translations = await translation.async_get_translations(
        hass, hass.config.language, f"component.{DOMAIN}"
    )
    entities.append(ThesslaGreenErrorCodesSensor(coordinator, translations))
    error_registers = [
        key
        for key in coordinator.available_registers.get("holding_registers", set())
        if key.startswith("e_") or key.startswith("s_")
    ]
    if error_registers:
        entities.append(ThesslaGreenActiveErrorsSensor(coordinator))


    if entities:
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning("Entity addition cancelled, adding without initial update")
            async_add_entities(entities, False)
        _LOGGER.info(
            "Created %d sensor entities for %s",
            len(entities),
            coordinator.device_name,
        )
    else:
        _LOGGER.warning("No sensor entities created - no compatible registers found")

    _LOGGER.info(
        "Temperature sensors: %d instantiated, %d skipped",
        temp_created,
        temp_skipped,
    )


class ThesslaGreenSensor(ThesslaGreenEntity, SensorEntity):
    """Sensor entity for ThesslaGreen device."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        sensor_definition: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, register_name)

        self._register_name = register_name
        self._sensor_def = sensor_definition

        # Sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        airflow_unit = getattr(getattr(coordinator, "entry", None), "options", {}).get(
            CONF_AIRFLOW_UNIT, DEFAULT_AIRFLOW_UNIT
        )
        self._attr_native_unit_of_measurement = sensor_definition.get("unit")
        if register_name in AIRFLOW_RATE_REGISTERS and airflow_unit == AIRFLOW_UNIT_PERCENTAGE:
            self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = sensor_definition.get("device_class")
        self._attr_state_class = sensor_definition.get("state_class")

        # Translation setup
        self._attr_translation_key = sensor_definition.get("translation_key")

        _LOGGER.debug(
            "Sensor initialized: %s (%s)",
            sensor_definition.get("translation_key"),
            register_name,
        )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self._register_name)

        if value in (None, SENSOR_UNAVAILABLE):
            return STATE_UNAVAILABLE
        if self._register_name.startswith(TIME_REGISTER_PREFIXES):
            if isinstance(value, int):
                return f"{value // 60:02d}:{value % 60:02d}"
            return cast(str | float | int, value)
        airflow_unit = getattr(getattr(self.coordinator, "entry", None), "options", {}).get(
            CONF_AIRFLOW_UNIT, DEFAULT_AIRFLOW_UNIT
        )
        if (
            self._register_name in AIRFLOW_RATE_REGISTERS
            and airflow_unit == AIRFLOW_UNIT_PERCENTAGE
        ):
            nominal_key = (
                "nominal_supply_air_flow"
                if self._register_name == "supply_flow_rate"
                else "nominal_exhaust_air_flow"
            )
            nominal = self.coordinator.data.get(nominal_key)
            if isinstance(nominal, (int, float)) and nominal:
                return round((cast(float, value) / float(nominal)) * 100)
            return STATE_UNAVAILABLE
        value_map = self._sensor_def.get("value_map")
        if value_map is not None:
            return cast(float | int | str, value_map.get(value, value))
        return cast(float | int | str, value)

    @property
    def available(self) -> bool:  # type: ignore[override]
        """Return if entity has valid data."""
        value = self.coordinator.data.get(self._register_name)
        if not (
            self.coordinator.last_update_success
            and value not in (None, SENSOR_UNAVAILABLE)
        ):
            return False
        airflow_unit = getattr(getattr(self.coordinator, "entry", None), "options", {}).get(
            CONF_AIRFLOW_UNIT, DEFAULT_AIRFLOW_UNIT
        )
        if (
            self._register_name in AIRFLOW_RATE_REGISTERS
            and airflow_unit == AIRFLOW_UNIT_PERCENTAGE
        ):
            nominal_key = (
                "nominal_supply_air_flow"
                if self._register_name == "supply_flow_rate"
                else "nominal_exhaust_air_flow"
            )
            nominal = self.coordinator.data.get(nominal_key)
            if not isinstance(nominal, (int, float)) or not nominal:
                return False
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}

        # Add register address for debugging
        if hasattr(self.coordinator, "device_scan_result") and self.coordinator.device_scan_result:
            attrs["register_name"] = self._register_name
            attrs["register_type"] = self._sensor_def["register_type"]

        # Add raw value for diagnostic purposes
        raw_value = self.coordinator.data.get(self._register_name)
        if raw_value is not None and isinstance(raw_value, (int, float)):
            attrs["raw_value"] = raw_value

        return attrs



class ThesslaGreenErrorCodesSensor(ThesslaGreenEntity, SensorEntity):
    """Aggregate active error registers into a single sensor."""

    _attr_icon = "mdi:alert-circle"
    _register_name = "error_codes"

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        translations: dict[str, str],
    ) -> None:
        """Initialize the aggregated error sensor."""
        super().__init__(coordinator, self._register_name)
        self._translations = translations
        self._attr_translation_key = self._register_name

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str | None:
        """Return comma-separated translated active error codes."""
        errors = [
            self._translations.get(f"errors.{key}", key)
            for key, value in self.coordinator.data.items()
            if key.startswith("e_") and value
        ]
        return ", ".join(sorted(errors)) if errors else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """List active error register keys."""
        active = [
            key
            for key, value in self.coordinator.data.items()
            if key.startswith("e_") and value
        ]
        return {"active_errors": active} if active else {}
class ThesslaGreenActiveErrorsSensor(ThesslaGreenEntity, SensorEntity):
    """Sensor that aggregates active error and status registers."""

    _attr_name = "Active Errors"
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: ThesslaGreenModbusCoordinator) -> None:
        """Initialize the active errors sensor."""
        super().__init__(coordinator, "active_errors")
        self._translations: dict[str, str] = {}

    async def async_added_to_hass(self) -> None:
        """Load translations when entity is added to Home Assistant."""
        self._translations = await translation.async_get_translations(
            self.hass, self.hass.config.language, f"component.{DOMAIN}"
        )

    @property
    def native_value(self) -> str | None:
        """Return comma-separated list of active error/status codes."""
        codes = [
            key
            for key, value in self.coordinator.data.items()
            if value and (key.startswith("e_") or key.startswith("s_"))
        ]
        return ", ".join(codes) if codes else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return mapping of codes to translated descriptions."""
        errors = {
            code: self._translations.get(f"errors.{code}", code)
            for code, value in self.coordinator.data.items()
            if value and (code.startswith("e_") or code.startswith("s_"))
        }
        return {"errors": errors} if errors else {}
