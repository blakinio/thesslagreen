"""Binary sensors for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .entity_mappings import ENTITY_MAPPINGS

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_DEFINITIONS: Dict[str, Dict[str, Any]] = ENTITY_MAPPINGS.get("binary_sensor", {})


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen binary sensor entities based on available registers."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Create binary sensors only for available registers (autoscan result)
    for register_name, sensor_def in BINARY_SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]

        # Check if this register is available on the device
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenBinarySensor(coordinator, register_name, sensor_def))
            _LOGGER.debug("Created binary sensor: %s", sensor_def["translation_key"])

    if entities:
        async_add_entities(entities, True)
        _LOGGER.info(
            "Created %d binary sensor entities for %s", len(entities), coordinator.device_name
        )
    else:
        _LOGGER.warning("No binary sensor entities created - no compatible registers found")


class ThesslaGreenBinarySensor(ThesslaGreenEntity, BinarySensorEntity):
    """Binary sensor entity for ThesslaGreen device."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        sensor_definition: Dict[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, register_name)
        self._attr_device_info = coordinator.get_device_info()

        self._register_name = register_name
        self._sensor_def = sensor_definition

        # Binary sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        self._attr_device_class: BinarySensorDeviceClass | None = sensor_definition.get(
            "device_class"
        )

        # Translation setup
        self._attr_translation_key = sensor_definition.get("translation_key")

        _LOGGER.debug(
            "Binary sensor initialized: %s (%s)",
            sensor_definition.get("translation_key"),
            register_name,
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        value = self.coordinator.data.get(self._register_name)

        if value is None:
            return None

        # Handle different register types
        register_type = self._sensor_def["register_type"]

        if register_type in ["coil_registers", "discrete_inputs"]:
            # Coils and discrete inputs are already boolean
            return bool(value)

        elif register_type == "input_registers":
            # Input registers: 1 = active/on, 0 = inactive/off
            return bool(value)

        elif register_type == "holding_registers":
            # Holding registers: depends on register
            if self._register_name == "on_off_panel_mode":
                return bool(value)
            else:
                return bool(value)

        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}

        # Add register information for debugging
        if hasattr(self.coordinator, "device_scan_result") and self.coordinator.device_scan_result:
            attrs["register_name"] = self._register_name
            attrs["register_type"] = self._sensor_def["register_type"]

        # Add raw value for diagnostic purposes
        raw_value = self.coordinator.data.get(self._register_name)
        if raw_value is not None:
            attrs["raw_value"] = raw_value

        # Add specific information for alarm/error sensors
        if "alarm" in self._register_name or "error" in self._register_name:
            attrs["severity"] = "warning" if self.is_on else "normal"

        return attrs

    @property
    def icon(self) -> str:
        """Return the icon for the binary sensor."""
        base_icon = self._attr_icon

        # Dynamic icon changes for certain sensors
        if self._register_name in ["bypass", "gwc", "power_supply_fans", "heating_cable"]:
            if self.is_on:
                return base_icon
            else:
                # Return "off" version of icon
                if "fan" in base_icon:
                    return base_icon.replace("fan", "fan-off")
                elif "heating" in base_icon:
                    return "mdi:radiator-off"
                elif "pipe" in base_icon:
                    return "mdi:pipe"

        # Dynamic icon for alarms and errors
        if "alarm" in self._register_name or "error" in self._register_name:
            if self.is_on:
                return "mdi:alert-circle"
            else:
                return "mdi:check-circle"

        return base_icon
