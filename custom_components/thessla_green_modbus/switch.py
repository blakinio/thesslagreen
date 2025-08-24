"""Switch platform for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .entity_mappings import ENTITY_MAPPINGS
from .modbus_exceptions import ConnectionException, ModbusException
from .registers.loader import get_registers_by_function

_LOGGER = logging.getLogger(__name__)

# Register address lookups for modbus writes
HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}
COIL_REGISTERS = {r.name: r.address for r in get_registers_by_function("01")}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:  # pragma: no cover
    """Set up ThesslaGreen switch entities from config entry.

    Home Assistant invokes this during platform setup.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Create switch entities only for writable registers discovered by
    # ThesslaGreenDeviceScanner.scan_device()
    for key, config in ENTITY_MAPPINGS["switch"].items():
        register_name = config["register"]

        # Check if this register is available and writable
        is_available = False

        if config["register_type"] == "holding_registers":
            if register_name in coordinator.available_registers.get("holding_registers", set()):
                is_available = True
            elif coordinator.force_full_register_list and register_name in HOLDING_REGISTERS:
                is_available = True
        elif config["register_type"] == "coil_registers":
            if register_name in coordinator.available_registers.get("coil_registers", set()):
                is_available = True
            elif coordinator.force_full_register_list and register_name in COIL_REGISTERS:
                is_available = True

        if is_available:
            if config["register_type"] == "holding_registers":
                address = HOLDING_REGISTERS[register_name]
            else:
                address = COIL_REGISTERS[register_name]
            entities.append(
                ThesslaGreenSwitch(
                    coordinator=coordinator,
                    key=key,
                    address=address,
                    entity_config=config,
                )
            )
            _LOGGER.debug("Created switch entity: %s", key)

    if entities:
        # Coordinator already holds initial data from setup, so update entities before add
        # to populate their state without triggering another refresh
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning(
                "Cancelled while adding switch entities, retrying without initial state"
            )
            async_add_entities(entities, False)
            return
        _LOGGER.info("Added %d switch entities", len(entities))
    else:
        _LOGGER.debug("No switch entities were created")


class ThesslaGreenSwitch(ThesslaGreenEntity, SwitchEntity):
    """ThesslaGreen switch entity.

    ``_attr_*`` attributes and entity methods implement the Home Assistant
    ``SwitchEntity`` API and therefore may look unused.
    """

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        key: str,
        address: int,
        entity_config: dict[str, Any],
    ) -> None:
        """Initialize the switch entity."""
        register_name = entity_config["register"]
        register_type = entity_config["register_type"]
        if register_type == "holding_registers":
            address = HOLDING_REGISTERS.get(register_name, 0)
        else:
            address = COIL_REGISTERS.get(register_name, 0)
        bit = entity_config.get("bit")
        super().__init__(coordinator, key, address, bit)
        super().__init__(coordinator, key, address, bit=entity_config.get("bit"))

        self.entity_config = entity_config
        self.register_name = register_name
        self.bit = bit

        # Entity configuration
        self._attr_translation_key = entity_config["translation_key"]  # pragma: no cover
        self._attr_icon = entity_config.get("icon", "mdi:toggle-switch")

        # Set entity category if specified
        if entity_config.get("category"):
            self._attr_entity_category = entity_config["category"]  # pragma: no cover

        _LOGGER.debug("Initialized switch entity: %s", key)

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        if self.register_name not in self.coordinator.data:
            return None

        raw_value = self.coordinator.data[self.register_name]

        # Handle None values
        if raw_value is None:
            return None

        if self.bit is not None:
            return bool(raw_value & self.bit)

        # Convert to boolean
        return bool(raw_value)

    async def async_turn_on(self, **kwargs: Any) -> None:  # pragma: no cover
        """Turn the switch on."""
        try:
            if self.bit is not None:
                current = self.coordinator.data.get(self.register_name, 0)
                value = current | self.bit
            else:
                value = 1
            await self._write_register(self.register_name, value)
            _LOGGER.info("Turned on %s", self.register_name)

        except (ModbusException, ConnectionException, RuntimeError) as exc:
            _LOGGER.error("Failed to turn on %s: %s", self.register_name, exc)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            if self.bit is not None:
                current = self.coordinator.data.get(self.register_name, 0)
                value = current & ~self.bit
            else:
                value = 0
            await self._write_register(self.register_name, value)
            _LOGGER.info("Turned off %s", self.register_name)

        except (ModbusException, ConnectionException, RuntimeError) as exc:
            _LOGGER.error("Failed to turn off %s: %s", self.register_name, exc)
            raise

    async def _write_register(self, register_name: str, value: int) -> None:
        """Write value to register."""
        success = await self.coordinator.async_write_register(register_name, value, refresh=False)
        if not success:
            raise RuntimeError(f"Failed to write register {register_name}")

        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:  # pragma: no cover
        """Return additional state attributes."""
        attributes = {}

        # Add register information
        attributes["register_name"] = self.register_name
        register_type = self.entity_config["register_type"]

        register_address = self._address if self._address is not None else 0
        attributes["register_address"] = f"0x{register_address:04X}"
        attributes["register_type"] = register_type

        # Add raw value for debugging
        if self.register_name in self.coordinator.data:
            raw_value = self.coordinator.data[self.register_name]
            if raw_value is not None:
                attributes["raw_value"] = raw_value

        # Add last update time
        last_update = (
            self.coordinator.statistics.get("last_successful_update")
            or self.coordinator.last_update
        )
        if last_update is not None:
            attributes["last_updated"] = last_update.isoformat()

        # Add mode-specific information
        if self.register_name == "special_mode":
            attributes["control_type"] = "special_mode"
            if self.bit is not None:
                attributes["bit"] = self.bit
        elif self.register_name == "on_off_panel_mode":
            attributes["control_type"] = "system_power"
        elif "mode" in self.register_name:
            attributes["control_type"] = "operating_mode"

        return attributes

    @property
    def available(self) -> bool:  # pragma: no cover
        """Return if entity is available."""
        # Entity is available if coordinator is available
        if not self.coordinator.last_update_success:
            return False

        # For switch entities, we don't require the register to be in current data
        # as they are primarily for control, not just display
        return True
