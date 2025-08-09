# ========== select.py ==========
"""COMPLETE Select entities for ThesslaGreen Modbus Integration - SILVER STANDARD.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Select entity definitions
SELECT_DEFINITIONS = {
    "mode": {
        "name": "Tryb pracy",
        "icon": "mdi:cog",
        "options": ["Automatyczny", "Manualny", "Chwilowy"],
        "values": [0, 1, 2],
        "register_type": "holding_registers",
    },
    "bypass_mode": {
        "name": "Tryb bypass",
        "icon": "mdi:pipe-leak",
        "options": ["Auto", "Otwarty", "Zamknięty"],
        "values": [0, 1, 2],
        "register_type": "holding_registers",
    },
    "gwc_mode": {
        "name": "Tryb GWC",
        "icon": "mdi:pipe",
        "options": ["Wyłączony", "Auto", "Wymuszony"],
        "values": [0, 1, 2],
        "register_type": "holding_registers",
    },
    "filter_change": {
        "name": "Typ filtra",
        "icon": "mdi:filter-variant",
        "options": ["Presostat", "Filtry płaskie", "CleanPad", "CleanPad Pure"],
        "values": [1, 2, 3, 4],
        "register_type": "holding_registers",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen select entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for register_name, select_def in SELECT_DEFINITIONS.items():
        register_type = select_def["register_type"]
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenSelect(coordinator, register_name, select_def))
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Created %d select entities", len(entities))


class ThesslaGreenSelect(CoordinatorEntity, SelectEntity):
    """Select entity for ThesslaGreen device."""

    def __init__(self, coordinator, register_name, definition):
        super().__init__(coordinator)
        self._register_name = register_name
        self._definition = definition
        
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{register_name}"
        self._attr_name = f"{coordinator.device_name} {definition['name']}"
        self._attr_device_info = coordinator.device_info_dict
        self._attr_icon = definition.get("icon")
        self._attr_options = definition["options"]

    @property
    def current_option(self) -> Optional[str]:
        """Return current option."""
        value = self.coordinator.data.get(self._register_name)
        if value is None:
            return None
        
        try:
            index = self._definition["values"].index(value)
            return self._definition["options"][index]
        except (ValueError, IndexError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            index = self._definition["options"].index(option)
            value = self._definition["values"][index]
            success = await self.coordinator.async_write_register(self._register_name, value)
            if success:
                await self.coordinator.async_request_refresh()
        except ValueError:
            _LOGGER.error("Invalid option: %s", option)


# ========== number.py ==========
"""COMPLETE Number entities for ThesslaGreen Modbus Integration - SILVER STANDARD."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Number entity definitions
NUMBER_DEFINITIONS = {
    "air_flow_rate_manual": {
        "name": "Intensywność wentylacji",
        "icon": "mdi:fan",
        "unit": PERCENTAGE,
        "min_value": 10,
        "max_value": 100,
        "step": 5,
        "mode": NumberMode.SLIDER,
        "register_type": "holding_registers",
    },
    "comfort_temperature": {
        "name": "Temperatura komfortowa",
        "icon": "mdi:thermometer",
        "unit": UnitOfTemperature.CELSIUS,
        "min_value": 16.0,
        "max_value": 30.0,
        "step": 0.5,
        "mode": NumberMode.BOX,
        "register_type": "holding_registers",
    },
    "required_temperature": {
        "name": "Temperatura zadana",
        "icon": "mdi:thermometer-auto",
        "unit": UnitOfTemperature.CELSIUS,
        "min_value": 20.0,
        "max_value": 90.0,
        "step": 0.5,
        "mode": NumberMode.BOX,
        "register_type": "holding_registers",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen number entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for register_name, number_def in NUMBER_DEFINITIONS.items():
        register_type = number_def["register_type"]
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenNumber(coordinator, register_name, number_def))
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Created %d number entities", len(entities))


class ThesslaGreenNumber(CoordinatorEntity, NumberEntity):
    """Number entity for ThesslaGreen device."""

    def __init__(self, coordinator, register_name, definition):
        super().__init__(coordinator)
        self._register_name = register_name
        self._definition = definition
        
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{register_name}"
        self._attr_name = f"{coordinator.device_name} {definition['name']}"
        self._attr_device_info = coordinator.device_info_dict
        self._attr_icon = definition.get("icon")
        self._attr_native_unit_of_measurement = definition.get("unit")
        self._attr_native_min_value = definition["min_value"]
        self._attr_native_max_value = definition["max_value"]
        self._attr_native_step = definition["step"]
        self._attr_mode = definition.get("mode", NumberMode.BOX)

    @property
    def native_value(self) -> Optional[float]:
        """Return current value."""
        return self.coordinator.data.get(self._register_name)

    async def async_set_native_value(self, value: float) -> None:
        """Update the value."""
        success = await self.coordinator.async_write_register(self._register_name, value)
        if success:
            await self.coordinator.async_request_refresh()


# ========== switch.py ==========
"""COMPLETE Switch entities for ThesslaGreen Modbus Integration - SILVER STANDARD."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Switch entity definitions
SWITCH_DEFINITIONS = {
    "on_off_panel_mode": {
        "name": "Zasilanie główne",
        "icon": "mdi:power",
        "register_type": "holding_registers",
    },
    "bypass": {
        "name": "Bypass",
        "icon": "mdi:pipe-leak",
        "register_type": "coil_registers",
    },
    "gwc": {
        "name": "GWC",
        "icon": "mdi:pipe",
        "register_type": "coil_registers",
    },
    "heating_cable": {
        "name": "Kabel grzejny",
        "icon": "mdi:heating-coil",
        "register_type": "coil_registers",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen switch entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for register_name, switch_def in SWITCH_DEFINITIONS.items():
        register_type = switch_def["register_type"]
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenSwitch(coordinator, register_name, switch_def))
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Created %d switch entities", len(entities))


class ThesslaGreenSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for ThesslaGreen device."""

    def __init__(self, coordinator, register_name, definition):
        super().__init__(coordinator)
        self._register_name = register_name
        self._definition = definition
        
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{register_name}"
        self._attr_name = f"{coordinator.device_name} {definition['name']}"
        self._attr_device_info = coordinator.device_info_dict
        self._attr_icon = definition.get("icon")

    @property
    def is_on(self) -> Optional[bool]:
        """Return True if entity is on."""
        value = self.coordinator.data.get(self._register_name)
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        register_type = self._definition["register_type"]
        if register_type == "coil_registers":
            success = await self.coordinator.async_write_coil(self._register_name, True)
        else:
            success = await self.coordinator.async_write_register(self._register_name, 1)
        
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        register_type = self._definition["register_type"]
        if register_type == "coil_registers":
            success = await self.coordinator.async_write_coil(self._register_name, False)
        else:
            success = await self.coordinator.async_write_register(self._register_name, 0)
        
        if success:
            await self.coordinator.async_request_refresh()


# ========== fan.py ==========
"""COMPLETE Fan entity for ThesslaGreen Modbus Integration - SILVER STANDARD."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = (10, 100)  # ThesslaGreen supports 10-100% airflow


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen fan entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Create fan entity if airflow control is available
    if "air_flow_rate_manual" in coordinator.available_registers.get("holding_registers", set()):
        entities = [ThesslaGreenFan(coordinator)]
        async_add_entities(entities, True)
        _LOGGER.info("Created fan entity")


class ThesslaGreenFan(CoordinatorEntity, FanEntity):
    """Fan entity for ThesslaGreen device."""

    def __init__(self, coordinator: ThesslaGreenModbusCoordinator):
        super().__init__(coordinator)
        
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_fan"
        self._attr_name = f"{coordinator.device_name} Wentylacja"
        self._attr_device_info = coordinator.device_info_dict
        self._attr_icon = "mdi:fan"
        
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED |
            FanEntityFeature.TURN_ON |
            FanEntityFeature.TURN_OFF
        )
        
        self._attr_speed_count = int_states_in_range(SPEED_RANGE)

    @property
    def is_on(self) -> Optional[bool]:
        """Return True if fan is on."""
        return self.coordinator.data.get("power_supply_fans", False)

    @property
    def percentage(self) -> Optional[int]:
        """Return current speed percentage."""
        speed = self.coordinator.data.get("air_flow_rate_manual")
        if speed is None:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, speed)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return
        
        speed = percentage_to_ranged_value(SPEED_RANGE, percentage)
        success = await self.coordinator.async_write_register("air_flow_rate_manual", speed)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, percentage: Optional[int] = None, **kwargs: Any) -> None:
        """Turn on the fan."""
        # Turn on main power first
        await self.coordinator.async_write_register("on_off_panel_mode", 1)
        
        if percentage is not None:
            await self.async_set_percentage(percentage)
        
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        success = await self.coordinator.async_write_register("on_off_panel_mode", 0)
        if success:
            await self.coordinator.async_request_refresh()


# ========== diagnostics.py ==========
"""COMPLETE Diagnostics for ThesslaGreen Modbus Integration - SILVER STANDARD."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    return {
        "config_entry": {
            "title": config_entry.title,
            "data": {
                "host": config_entry.data.get("host"),
                "port": config_entry.data.get("port"),
                "slave_id": config_entry.data.get("slave_id"),
                "name": config_entry.data.get("name"),
            },
            "options": dict(config_entry.options),
            "version": config_entry.version,
        },
        "coordinator_data": coordinator.get_diagnostics_data(),
        "current_data": dict(coordinator.data),
    }