"""Switch platform for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HOLDING_REGISTERS, COIL_REGISTERS
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Switch entities that can be controlled
SWITCH_ENTITIES = {
    # System control switches from holding registers
    "on_off_panel_mode": {"icon": "mdi:power", "register_type": "holding", "category": None},
    "boost_mode": {"icon": "mdi:rocket-launch", "register_type": "holding", "category": None},
    "eco_mode": {"icon": "mdi:leaf", "register_type": "holding", "category": None},
    "night_mode": {"icon": "mdi:weather-night", "register_type": "holding", "category": None},
    "party_mode": {"icon": "mdi:party-popper", "register_type": "holding", "category": None},
    "fireplace_mode": {"icon": "mdi:fireplace", "register_type": "holding", "category": None},
    "vacation_mode": {"icon": "mdi:airplane", "register_type": "holding", "category": None},
    "okap_mode": {"icon": "mdi:range-hood", "register_type": "holding", "category": None},
    "silent_mode": {"icon": "mdi:volume-off", "register_type": "holding", "category": None},
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen switch entities from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Create switch entities for available writable registers
    for register_name, config in SWITCH_ENTITIES.items():
        # Check if this register is available and writable
        is_available = False

        if config["register_type"] == "holding":
            if register_name in coordinator.available_registers.get("holding", {}):
                is_available = True
            elif coordinator.force_full_register_list and register_name in HOLDING_REGISTERS:
                is_available = True
        elif config["register_type"] == "coil":
            if register_name in coordinator.available_registers.get("coil", {}):
                is_available = True
            elif coordinator.force_full_register_list and register_name in COIL_REGISTERS:
                is_available = True

        if is_available:
            entities.append(
                ThesslaGreenSwitch(
                    coordinator=coordinator,
                    register_name=register_name,
                    entity_config=config,
                )
            )
            _LOGGER.debug("Created switch entity: %s", register_name)

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d switch entities", len(entities))
    else:
        _LOGGER.debug("No switch entities were created")


class ThesslaGreenSwitch(CoordinatorEntity, SwitchEntity):
    """ThesslaGreen switch entity."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        entity_config: Dict[str, Any],
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)

        self.register_name = register_name
        self.entity_config = entity_config

        # Entity configuration
        self._attr_unique_id = f"{coordinator.device_name}_{register_name}"
        self._attr_translation_key = register_name
        self._attr_has_entity_name = True
        self._attr_device_info = coordinator.get_device_info()
        self._attr_icon = entity_config["icon"]

        # Set entity category if specified
        if entity_config.get("category"):
            self._attr_entity_category = entity_config["category"]

        _LOGGER.debug("Initialized switch entity for register: %s", register_name)

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        if self.register_name not in self.coordinator.data:
            return None

        raw_value = self.coordinator.data[self.register_name]

        # Handle None values
        if raw_value is None:
            return None

        # Convert to boolean
        return bool(raw_value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self._write_register(self.register_name, 1)
            _LOGGER.info("Turned on %s", self.register_name)

        except Exception as exc:
            _LOGGER.error("Failed to turn on %s: %s", self.register_name, exc)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self._write_register(self.register_name, 0)
            _LOGGER.info("Turned off %s", self.register_name)

        except Exception as exc:
            _LOGGER.error("Failed to turn off %s: %s", self.register_name, exc)

    async def _write_register(self, register_name: str, value: int) -> None:
        """Write value to register."""
        register_type = self.entity_config["register_type"]

        if register_type == "holding":
            if register_name not in HOLDING_REGISTERS:
                raise ValueError(f"Register {register_name} is not a holding register")
            register_address = HOLDING_REGISTERS[register_name]
        elif register_type == "coil":
            if register_name not in COIL_REGISTERS:
                raise ValueError(f"Register {register_name} is not a coil register")
            register_address = COIL_REGISTERS[register_name]
        else:
            raise ValueError(f"Invalid register type: {register_type}")

        # Ensure client is connected
        if not self.coordinator.client or not self.coordinator.client.connected:
            if not await self.coordinator.async_ensure_client():
                raise RuntimeError("Failed to connect to device")

        # Write register - pymodbus 3.5+ compatible
        if register_type == "holding":
            response = await self.coordinator.client.write_register(
                address=register_address, value=value, slave=self.coordinator.slave_id
            )
        else:  # coil
            response = await self.coordinator.client.write_coil(
                address=register_address, value=bool(value), slave=self.coordinator.slave_id
            )

        if response.isError():
            raise RuntimeError(f"Failed to write register {register_name}: {response}")

        # Request immediate data update
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}

        # Add register information
        attributes["register_name"] = self.register_name
        register_type = self.entity_config["register_type"]

        if register_type == "holding":
            register_address = HOLDING_REGISTERS.get(self.register_name, 0)
        else:
            register_address = COIL_REGISTERS.get(self.register_name, 0)

        attributes["register_address"] = f"0x{register_address:04X}"
        attributes["register_type"] = register_type

        # Add raw value for debugging
        if self.register_name in self.coordinator.data:
            raw_value = self.coordinator.data[self.register_name]
            if raw_value is not None:
                attributes["raw_value"] = raw_value

        # Add last update time
        if self.coordinator.last_successful_update:
            attributes["last_updated"] = self.coordinator.last_successful_update.isoformat()

        # Add mode-specific information
        if "mode" in self.register_name:
            attributes["control_type"] = "operating_mode"
        elif self.register_name in ["boost_mode", "eco_mode", "night_mode"]:
            attributes["control_type"] = "performance_mode"
        elif self.register_name in ["party_mode", "fireplace_mode", "vacation_mode", "okap_mode"]:
            attributes["control_type"] = "special_mode"
        elif self.register_name == "on_off_panel_mode":
            attributes["control_type"] = "system_power"

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if coordinator is available
        if not self.coordinator.last_update_success:
            return False

        # For switch entities, we don't require the register to be in current data
        # as they are primarily for control, not just display
        return True
