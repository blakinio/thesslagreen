"""Number platform for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, get_holding_registers

try:  # Newer versions expose metadata through ENTITY_MAPPINGS
    from .const import ENTITY_MAPPINGS
except ImportError:  # pragma: no cover - fall back when not available
    ENTITY_MAPPINGS = {}
from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .entity_mappings import ENTITY_MAPPINGS
from .modbus_exceptions import ConnectionException, ModbusException
from .const import HOLDING_REGISTERS

_LOGGER = logging.getLogger(__name__)

HOLDING_REGISTERS = get_holding_registers()

# Unit mappings
UNIT_MAPPINGS = {
    "°C": UnitOfTemperature.CELSIUS,
    "%": PERCENTAGE,
    "min": UnitOfTime.MINUTES,
    "h": UnitOfTime.HOURS,
    "m³/h": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen number entities from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Get number entity mappings
    number_mappings: dict[str, dict[str, Any]] = ENTITY_MAPPINGS.get("number", {})
    if not number_mappings:
        _LOGGER.debug("No number entity mappings found; skipping setup")
        return

    # Create number entities only for registers discovered by
    # ThesslaGreenDeviceScanner.scan_device()
    for register_name, entity_config in number_mappings.items():
        if register_name in coordinator.available_registers.get("holding_registers", set()):
            entities.append(
                ThesslaGreenNumber(
                    coordinator=coordinator,
                    register_name=register_name,
                    entity_config=entity_config,
                    register_type="holding_registers",
                )
            )
            _LOGGER.debug("Created number entity: %s", register_name)

    if entities:
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning(
                "Cancelled while adding number entities, retrying without initial state"
            )
            async_add_entities(entities, False)
            return
        _LOGGER.info("Added %d number entities", len(entities))
    else:
        _LOGGER.debug("No number entities were created")


class ThesslaGreenNumber(ThesslaGreenEntity, NumberEntity):
    """ThesslaGreen number entity."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        entity_config: dict[str, Any],
        register_type: str | None = None,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, register_name)

        self.register_name = register_name
        self.entity_config = entity_config
        self.register_type = register_type

        # Entity configuration
        self._attr_translation_key = register_name

        # Number configuration
        self._setup_number_attributes()

        _LOGGER.debug("Initialized number entity for register: %s", register_name)

    def _setup_number_attributes(self) -> None:
        """Setup number attributes based on entity configuration."""
        # Unit of measurement
        if "unit" in self.entity_config:
            unit = self.entity_config["unit"]
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS.get(unit, unit)

        # Min/max values
        self._attr_native_min_value = self.entity_config.get("min", 0)
        self._attr_native_max_value = self.entity_config.get("max", 100)

        # Step size
        self._attr_native_step = self.entity_config.get("step", 1)

        # Mode - slider for temperatures, durations and coefficients
        if any(
            keyword in self.register_name
            for keyword in ["temperature", "duration", "coef", "percentage"]
        ):
            self._attr_mode = NumberMode.SLIDER
        else:
            self._attr_mode = NumberMode.BOX

        # Icon
        if "temperature" in self.register_name:
            self._attr_icon = "mdi:thermometer"
        elif (
            "flow" in self.register_name
            or "rate" in self.register_name
            or "fan_speed" in self.register_name
        ):
            self._attr_icon = "mdi:fan"
        elif "duration" in self.register_name:
            self._attr_icon = "mdi:timer"
        elif "intensity" in self.register_name:
            self._attr_icon = "mdi:gauge"
        elif "coef" in self.register_name or "percentage" in self.register_name:
            self._attr_icon = "mdi:percent"
        else:
            self._attr_icon = "mdi:numeric"

        # Entity category for configuration parameters
        if any(
            keyword in self.register_name
            for keyword in ["hysteresis", "correction", "max", "min", "balance", "coef"]
        ):
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.register_name not in self.coordinator.data:
            return None

        raw_value = self.coordinator.data[self.register_name]

        # Handle None values
        if raw_value is None:
            return None

        return float(raw_value) if isinstance(raw_value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        try:
            success = await self.coordinator.async_write_register(
                self.register_name, value, refresh=False
            )
            if success:
                await self.coordinator.async_request_refresh()
                _LOGGER.info("Set %s to %.2f", self.register_name, value)
            else:
                _LOGGER.error("Failed to set %s to %.2f", self.register_name, value)
                raise RuntimeError(f"Failed to write register {self.register_name}")

        except (ModbusException, ConnectionException, RuntimeError) as exc:
            _LOGGER.error("Failed to set %s to %.2f: %s", self.register_name, value, exc)
            raise
        except (ValueError, OSError) as exc:  # pragma: no cover - unexpected
            _LOGGER.exception(
                "Error setting %s to %.2f: %s",
                self.register_name,
                value,
                exc,
            )
            raise

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes: dict[str, Any] = {}

        # Add register information
        attributes["register_name"] = self.register_name
        attributes["register_address"] = f"0x{HOLDING_REGISTERS.get(self.register_name, 0):04X}"

        # Add raw value for debugging
        if self.register_name in self.coordinator.data:
            raw_value = self.coordinator.data[self.register_name]
            if raw_value is not None:
                attributes["raw_value"] = raw_value

        # Add valid range
        attributes["valid_range"] = {
            "min": self._attr_native_min_value,
            "max": self._attr_native_max_value,
            "step": self._attr_native_step,
        }

        # Add last update time
        last_update = (
            self.coordinator.statistics.get("last_successful_update")
            or self.coordinator.last_update
        )
        if last_update is not None:
            attributes["last_updated"] = last_update.isoformat()

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if coordinator is available
        if not self.coordinator.last_update_success:
            return False

        # For number entities, we don't require the register to be in current data
        # as they are primarily for control, not just display
        return True
