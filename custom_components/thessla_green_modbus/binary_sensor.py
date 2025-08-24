"""Binary sensor platform for the ThesslaGreen Modbus integration.

Entities are created dynamically based on the registers reported by the
device scanner. Only registers available on the target device are exposed
as binary sensor entities.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity

# Binary sensor mappings are defined centrally in entity_mappings
from .entity_mappings import BINARY_SENSOR_ENTITY_MAPPINGS

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_DEFINITIONS: Dict[str, Dict[str, Any]] = BINARY_SENSOR_ENTITY_MAPPINGS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:  # pragma: no cover
    """Set up ThesslaGreen binary sensor entities.

    This coroutine is a Home Assistant platform setup hook and is invoked
    by the framework; it is not called directly within this repository.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Create binary sensors only for registers discovered by
    # ThesslaGreenDeviceScanner.scan_device()
    for key, sensor_def in BINARY_SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]
        register_name = sensor_def.get("register", key)

        # Check if this register is available on the device
        if register_name in coordinator.available_registers.get(register_type, set()):
            address = coordinator._register_maps[register_type][register_name]
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator,
                    register_name,
                    address,
                    sensor_def,
                )
            )
            _LOGGER.debug("Created binary sensor: %s", sensor_def["translation_key"])

    if entities:
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning(
                "Cancelled while adding binary sensor entities, retrying without initial state"
            )
            async_add_entities(entities, False)
            return
        _LOGGER.info(
            "Created %d binary sensor entities for %s", len(entities), coordinator.device_name
        )
    else:
        _LOGGER.warning("No binary sensor entities created - no compatible registers found")


class ThesslaGreenBinarySensor(ThesslaGreenEntity, BinarySensorEntity):
    """Binary sensor entity for ThesslaGreen device.

    Attributes with the ``_attr_`` prefix are consumed by Home Assistant to
    configure the entity and therefore appear unused to static analysis
    tools like vulture.
    """

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        address: int,
        sensor_definition: Dict[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            coordinator,
            register_name,
            address,
            bit=sensor_definition.get("bit"),
        )

        self._register_name = register_name
        self._sensor_def = sensor_definition

        # Binary sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        self._attr_device_class: BinarySensorDeviceClass | None = sensor_definition.get(
            "device_class"
        )  # pragma: no cover

        # Translation setup
        self._attr_translation_key = sensor_definition.get("translation_key")  # pragma: no cover

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
    def extra_state_attributes(self) -> dict[str, Any]:  # pragma: no cover
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
            if self._sensor_def.get("bitmask") and self._sensor_def.get("bit") is None:
                attrs["bitmask"] = raw_value

        # Add specific information for alarm/error sensors and severity registers
        if (
            "alarm" in self._register_name
            or "error" in self._register_name
            or self._register_name.startswith(("s_", "e_"))
        ):
            attrs["severity"] = "warning" if self.is_on else "normal"

        return attrs

    @property
    def icon(self) -> str:  # pragma: no cover
        """Return the icon for the binary sensor."""
        # Ensure base_icon is a string before using it
        base_icon = self._attr_icon if isinstance(self._attr_icon, str) else None

        # Dynamic icon changes for certain sensors
        if base_icon and self._register_name in [
            "bypass",
            "gwc",
            "power_supply_fans",
            "heating_cable",
        ]:
            if self.is_on:
                return base_icon
            # Return "off" version of icon
            if "fan" in base_icon:
                return base_icon.replace("fan", "fan-off")
            if "heating" in base_icon:
                return "mdi:radiator-off"
            if "pipe" in base_icon:
                return "mdi:pipe"

        # Dynamic icon for alarms, errors and severity registers
        if (
            "alarm" in self._register_name
            or "error" in self._register_name
            or self._register_name.startswith(("s_", "e_"))
        ):
            return "mdi:alert-circle" if self.is_on else "mdi:check-circle"

        # Fallback icon when no icon is configured
        return base_icon or "mdi:fan-off"
