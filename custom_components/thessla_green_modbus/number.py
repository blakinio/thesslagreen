"""Number platform for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymodbus.exceptions import ConnectionException, ModbusException

from .capability_rules import capability_block_reason
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .mappings import ENTITY_MAPPINGS
from .optimistic import OptimisticState

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

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
    coordinator: ThesslaGreenModbusCoordinator = entry.runtime_data
    entities = []
    number_mappings: dict[str, dict[str, Any]] = ENTITY_MAPPINGS["number"]

    holding_map = coordinator.device_client.get_register_map("holding_registers")
    available = coordinator.device_client.available_registers.get("holding_registers", set())

    for register_name, entity_config in number_mappings.items():
        force_create = (
            coordinator.device_client.force_full_register_list and register_name in holding_map
        )

        if reason := capability_block_reason(register_name, coordinator.device_client.capabilities):
            _LOGGER.info("Entity skipped due to capability: %s (%s)", register_name, reason)
            continue

        if register_name in available or force_create:
            address = holding_map.get(register_name)
            if address is None:
                _LOGGER.error(
                    "Register %s not defined in holding registers, skipping",
                    register_name,
                )
                continue
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
        async_add_entities(entities, False)
        _LOGGER.debug("Added %d number entities", len(entities))
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
        register_map = coordinator.device_client.get_register_map("holding_registers")
        if register_name not in register_map:
            raise KeyError(f"Register {register_name} not found in holding registers")
        address = register_map[register_name]

        super().__init__(coordinator, register_name, address)

        self.register_name = register_name
        self.entity_config = entity_config
        self.register_type = register_type
        self._attr_translation_key = register_name
        self._setup_number_attributes()
        self._apply_risk_policy(entity_config)
        self._optimistic = OptimisticState()

        _LOGGER.debug("Initialized number entity for register: %s", register_name)

    def _setup_number_attributes(self) -> None:
        """Setup number attributes based on entity configuration."""
        if "unit" in self.entity_config:
            unit = self.entity_config["unit"]
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS.get(unit, unit)

        self._attr_native_min_value = self.entity_config.get("min", 0)
        self._attr_native_max_value = self.entity_config.get("max", 100)
        self._attr_native_step = self.entity_config.get("step", 1)

        if any(
            keyword in self.register_name
            for keyword in ["temperature", "duration", "coef", "percentage"]
        ):
            self._attr_mode = NumberMode.SLIDER
        else:
            self._attr_mode = NumberMode.BOX

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

        if any(
            keyword in self.register_name
            for keyword in ["hysteresis", "correction", "max", "min", "balance", "coef"]
        ):
            self._attr_entity_category = EntityCategory.CONFIG

        if "entity_category" in self.entity_config:
            ec_val = self.entity_config["entity_category"]
            self._attr_entity_category = (
                EntityCategory(ec_val) if isinstance(ec_val, str) else ec_val
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Drop the optimistic setpoint once the confirmed value matches."""
        self._clear_optimistic_if_confirmed()
        super()._handle_coordinator_update()

    def _clear_optimistic_if_confirmed(self) -> None:
        """Clear the pending setpoint once coordinator data confirms it."""
        confirmed = self.coordinator.data.get(self.register_name)
        if isinstance(confirmed, int | float):
            self._optimistic.clear_if_confirmed(
                self.register_name, confirmed, tolerance=self._optimistic_tolerance()
            )

    def _optimistic_tolerance(self) -> float:
        """Return the float tolerance used to confirm a pending setpoint."""
        try:
            return float(self._attr_native_step) / 2
        except (TypeError, ValueError):
            return 0.5

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        pending = self._optimistic.get_pending(self.register_name)
        if pending is not None:
            return float(pending)

        if self.register_name not in self.coordinator.data:
            return None

        raw_value = self.coordinator.data[self.register_name]
        if raw_value is None:
            return None

        return float(raw_value) if isinstance(raw_value, int | float) else None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        try:
            await self._write_register(self.register_name, value, include_offset=True)
            self._optimistic.set_pending(self.register_name, float(value))
            if self.hass is not None:
                self.async_write_ha_state()
            _LOGGER.debug("Set %s to %.2f", self.register_name, value)
        except (ModbusException, ConnectionException, RuntimeError, TimeoutError, OSError) as exc:
            _LOGGER.error("Failed to set %s to %.2f: %s", self.register_name, value, exc)
            raise
        except ValueError as exc:  # pragma: no cover - unexpected
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
        attributes["register_name"] = self.register_name
        register_address = self._address if self._address is not None else 0
        attributes["register_address"] = f"{register_address}"

        if self.register_name in self.coordinator.data:
            raw_value = self.coordinator.data[self.register_name]
            if raw_value is not None:
                attributes["raw_value"] = raw_value

        attributes["valid_range"] = {
            "min": self._attr_native_min_value,
            "max": self._attr_native_max_value,
            "step": self._attr_native_step,
        }

        last_update = (
            self.coordinator.device_client.statistics.get("last_successful_update")
            or self.coordinator.last_update
        )
        if last_update is not None:
            attributes["last_updated"] = last_update.isoformat()

        for meta_key in ("risk_level", "risk_category", "safety_warning"):
            meta_val = self.entity_config.get(meta_key)
            if meta_val is not None:
                attributes[meta_key] = meta_val

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available
