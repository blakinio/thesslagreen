"""Select platform for ThesslaGreen Modbus Integration - FIXED VERSION."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    OPERATING_MODES,
    SEASON_MODES,
    SPECIAL_MODES,
    GWC_MODES,
    BYPASS_MODES,
    COMFORT_MODES,
    FPX_MODES,
)
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen select entities."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())

    # ====== MAIN OPERATING MODE SELECTORS ======
    
    # Primary operating mode
    if "mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "mode",
                "Tryb pracy",
                list(OPERATING_MODES.values()),
                "mdi:cog",
            )
        )

    # Alternative operating mode registers (new from documentation)
    if "cfg_mode1" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "cfg_mode1",
                "Tryb pracy (grupa 1)",
                list(OPERATING_MODES.values()),
                "mdi:cog-box",
            )
        )

    if "cfg_mode2" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "cfg_mode2",
                "Tryb pracy (grupa 2)",
                list(OPERATING_MODES.values()),
                "mdi:cog-outline",
            )
        )

    # Season mode
    if "season_mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "season_mode",
                "Sezon",
                list(SEASON_MODES.values()),
                "mdi:weather-sunny",
            )
        )

    # ====== SPECIAL FUNCTION SELECTOR ======
    
    if "special_mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "special_mode",
                "Funkcja specjalna",
                list(SPECIAL_MODES.values()),
                "mdi:star",
            )
        )

    # ====== SYSTEM STATUS SELECTORS (Read-only) ======
    
    # GWC mode (read-only status)
    if "gwc_mode" in holding_regs:
        entities.append(
            ThesslaGreenReadOnlySelect(
                coordinator,
                "gwc_mode",
                "Status GWC",
                list(GWC_MODES.values()),
                "mdi:heat-pump",
            )
        )

    # Bypass mode (read-only status)
    if "bypass_mode" in holding_regs:
        entities.append(
            ThesslaGreenReadOnlySelect(
                coordinator,
                "bypass_mode",
                "Status Bypass",
                list(BYPASS_MODES.values()),
                "mdi:valve",
            )
        )

    # Comfort mode (read-only status)
    if "comfort_mode" in holding_regs:
        entities.append(
            ThesslaGreenReadOnlySelect(
                coordinator,
                "comfort_mode",
                "Status KOMFORT",
                list(COMFORT_MODES.values()),
                "mdi:home-thermometer",
            )
        )

    # FPX antifreeze stage (read-only status)
    if "antifreeze_stage" in holding_regs:
        entities.append(
            ThesslaGreenReadOnlySelect(
                coordinator,
                "antifreeze_stage",
                "Stopień FPX",
                list(FPX_MODES.values()),
                "mdi:snowflake-alert",
            )
        )

    # ====== CONTROL SELECTORS (User configurable) ======
    
    # Comfort mode panel (user control)
    if "comfort_mode_panel" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "comfort_mode_panel",
                "Panel KOMFORT",
                ["EKO", "KOMFORT"],
                "mdi:home-thermometer-outline",
            )
        )

    # Bypass user mode (user control)
    if "bypass_user_mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "bypass_user_mode",
                "Typ realizacji Bypass",
                ["Typ 1", "Typ 2", "Typ 3"],
                "mdi:valve-open",
            )
        )

    # GWC regeneration type
    if "gwc_regen" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "gwc_regen",
                "Typ regeneracji GWC",
                ["Wyłączone", "Czasowe", "Temperaturowe", "Mieszane"],
                "mdi:refresh",
            )
        )

    # ====== ADVANCED SELECTORS ======
    
    # Access level (if available)
    if "access_level" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "access_level",
                "Poziom dostępu",
                ["Użytkownik", "Serwis", "Producent"],
                "mdi:account-key",
            )
        )

    # Language setting (if available)
    if "language" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "language",
                "Język panelu",
                ["Polski", "English", "Deutsch", "Français"],
                "mdi:translate",
            )
        )

    if entities:
        _LOGGER.debug("Adding %d select entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenSelect(CoordinatorEntity, SelectEntity):
    """ThesslaGreen select entity (writable)."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        options: list[str],
        icon: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_options = options
        self._attr_icon = icon

        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None

        # Map numeric values to text options
        if self._key in ["mode", "cfg_mode1", "cfg_mode2"]:
            return OPERATING_MODES.get(value, f"Unknown({value})")
        elif self._key == "season_mode":
            return SEASON_MODES.get(value, f"Unknown({value})")
        elif self._key == "special_mode":
            return SPECIAL_MODES.get(value, f"Unknown({value})")
        elif self._key == "comfort_mode_panel":
            return "KOMFORT" if value == 1 else "EKO"
        elif self._key == "bypass_user_mode":
            types = {1: "Typ 1", 2: "Typ 2", 3: "Typ 3"}
            return types.get(value, f"Unknown({value})")
        elif self._key == "gwc_regen":
            types = {0: "Wyłączone", 1: "Czasowe", 2: "Temperaturowe", 3: "Mieszane"}
            return types.get(value, f"Unknown({value})")
        elif self._key == "access_level":
            levels = {0: "Użytkownik", 1: "Serwis", 2: "Producent"}
            return levels.get(value, f"Unknown({value})")
        elif self._key == "language":
            languages = {0: "Polski", 1: "English", 2: "Deutsch", 3: "Français"}
            return languages.get(value, f"Unknown({value})")

        return f"Unknown({value})"

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        value_map = {}
        
        # Create reverse mapping from text to numeric values
        if self._key in ["mode", "cfg_mode1", "cfg_mode2"]:
            value_map = {v: k for k, v in OPERATING_MODES.items()}
        elif self._key == "season_mode":
            value_map = {v: k for k, v in SEASON_MODES.items()}
        elif self._key == "special_mode":
            value_map = {v: k for k, v in SPECIAL_MODES.items()}
        elif self._key == "comfort_mode_panel":
            value_map = {"EKO": 0, "KOMFORT": 1}
        elif self._key == "bypass_user_mode":
            value_map = {"Typ 1": 1, "Typ 2": 2, "Typ 3": 3}
        elif self._key == "gwc_regen":
            value_map = {"Wyłączone": 0, "Czasowe": 1, "Temperaturowe": 2, "Mieszane": 3}
        elif self._key == "access_level":
            value_map = {"Użytkownik": 0, "Serwis": 1, "Producent": 2}
        elif self._key == "language":
            value_map = {"Polski": 0, "English": 1, "Deutsch": 2, "Français": 3}

        if option in value_map:
            success = await self.coordinator.async_write_register(self._key, value_map[option])
            if success:
                await self.coordinator.async_request_refresh()
                _LOGGER.debug("Successfully set %s to %s (value: %s)", self._key, option, value_map[option])
            else:
                _LOGGER.error("Failed to set %s to %s", self._key, option)
        else:
            _LOGGER.error("Invalid option %s for %s", option, self._key)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add current numeric value for debugging
        value = self.coordinator.data.get(self._key)
        if value is not None:
            attributes["numeric_value"] = value
        
        # Add register information
        from .const import HOLDING_REGISTERS
        if self._key in HOLDING_REGISTERS:
            attributes["modbus_address"] = f"0x{HOLDING_REGISTERS[self._key]:04X}"
            attributes["register_type"] = "holding_register"
        
        # Add writable status
        attributes["writable"] = True
        
        return attributes


class ThesslaGreenReadOnlySelect(CoordinatorEntity, SelectEntity):
    """ThesslaGreen read-only select entity (status display only)."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        options: list[str],
        icon: str,
    ) -> None:
        """Initialize the read-only select entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_options = options
        self._attr_icon = icon

        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}_status"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None

        # Map numeric values to text options for read-only registers
        if self._key == "gwc_mode":
            return GWC_MODES.get(value, f"Unknown({value})")
        elif self._key == "bypass_mode":
            return BYPASS_MODES.get(value, f"Unknown({value})")
        elif self._key == "comfort_mode":
            return COMFORT_MODES.get(value, f"Unknown({value})")
        elif self._key == "antifreeze_stage":
            return FPX_MODES.get(value, f"Unknown({value})")

        return f"Unknown({value})"

    async def async_select_option(self, option: str) -> None:
        """Select an option - NOT ALLOWED for read-only entities."""
        _LOGGER.warning("Cannot set read-only register %s to %s", self._key, option)
        # Don't raise an exception, just log and ignore
        return

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add current numeric value for debugging
        value = self.coordinator.data.get(self._key)
        if value is not None:
            attributes["numeric_value"] = value
        
        # Add register information
        from .const import HOLDING_REGISTERS
        if self._key in HOLDING_REGISTERS:
            attributes["modbus_address"] = f"0x{HOLDING_REGISTERS[self._key]:04X}"
            attributes["register_type"] = "holding_register"
        
        # Mark as read-only
        attributes["writable"] = False
        attributes["note"] = "Read-only status register"
        
        # Add interpretation based on register type
        if self._key == "gwc_mode":
            attributes["description"] = "Current GWC operating mode"
        elif self._key == "bypass_mode":
            attributes["description"] = "Current bypass function status"
        elif self._key == "comfort_mode":
            attributes["description"] = "Current comfort mode status"
        elif self._key == "antifreeze_stage":
            attributes["description"] = "Current FPX antifreeze stage"
        
        return attributes

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # Read-only status entities are enabled by default but less prominent
        return True