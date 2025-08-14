"""Binary sensors for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity

_LOGGER = logging.getLogger(__name__)

# Complete binary sensor definitions
BINARY_SENSOR_DEFINITIONS = {
    # System status (from coil registers)
    "duct_water_heater_pump": {
        "translation_key": "duct_water_heater_pump",
        "icon": "mdi:pump",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "bypass": {
        "translation_key": "bypass",
        "icon": "mdi:pipe-leak",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "coil_registers",
    },
    "info": {
        "translation_key": "info",
        "icon": "mdi:information",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "power_supply_fans": {
        "translation_key": "power_supply_fans",
        "icon": "mdi:fan",
        "device_class": BinarySensorDeviceClass.POWER,
        "register_type": "coil_registers",
    },
    "heating_cable": {
        "translation_key": "heating_cable",
        "icon": "mdi:heating-coil",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "coil_registers",
    },
    "work_permit": {
        "translation_key": "work_permit",
        "icon": "mdi:check-circle",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "gwc": {
        "translation_key": "gwc",
        "icon": "mdi:pipe",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "hood_output": {
        "translation_key": "hood_output",
        "icon": "mdi:stove",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    # System status (from discrete inputs)
    "expansion": {
        "translation_key": "expansion",
        "icon": "mdi:expansion-card",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "register_type": "discrete_inputs",
    },
    "contamination_sensor": {
        "translation_key": "contamination_sensor",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "duct_heater_protection": {
        "translation_key": "duct_heater_protection",
        "icon": "mdi:shield-heat",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "dp_duct_filter_overflow": {
        "translation_key": "dp_duct_filter_overflow",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "hood_switch": {
        "translation_key": "hood_switch",
        "icon": "mdi:toggle-switch",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "airing_sensor": {
        "translation_key": "airing_sensor",
        "icon": "mdi:motion-sensor",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "airing_switch": {
        "translation_key": "airing_switch",
        "icon": "mdi:toggle-switch",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "airing_mini": {
        "translation_key": "airing_mini",
        "icon": "mdi:fan",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fan_speed_3": {
        "translation_key": "fan_speed_3",
        "icon": "mdi:fan-speed-3",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fan_speed_2": {
        "translation_key": "fan_speed_2",
        "icon": "mdi:fan-speed-2",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fan_speed_1": {
        "translation_key": "fan_speed_1",
        "icon": "mdi:fan-speed-1",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fireplace": {
        "translation_key": "fireplace",
        "icon": "mdi:fireplace",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "dp_ahu_filter_overflow": {
        "translation_key": "dp_ahu_filter_overflow",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "ahu_filter_protection": {
        "translation_key": "ahu_filter_protection",
        "icon": "mdi:shield",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "empty_house": {
        "translation_key": "empty_house",
        "icon": "mdi:home-outline",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fire_alarm": {
        "translation_key": "fire_alarm",
        "icon": "mdi:fire",
        "device_class": BinarySensorDeviceClass.SAFETY,
        "register_type": "discrete_inputs",
    },
    # System modes (from input registers)
    "constant_flow_active": {
        "translation_key": "constant_flow_active",
        "icon": "mdi:waves",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "water_removal_active": {
        "translation_key": "water_removal_active",
        "icon": "mdi:water-off",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
}


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
        sensor_definition: dict[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, register_name)
        self._attr_device_info = coordinator.get_device_info()

        self._register_name = register_name
        self._sensor_def = sensor_definition

        # Binary sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        self._attr_device_class = sensor_definition.get("device_class")

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
