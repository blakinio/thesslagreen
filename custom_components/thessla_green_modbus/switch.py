"""Switch platform for ThesslaGreen Modbus Integration - FIXED VERSION."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen switch entities."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())

    # ====== MAIN DEVICE ON/OFF SWITCH ======
    if "on_off_panel_mode" in holding_regs:
        entities.append(
            ThesslaGreenMainSwitch(coordinator)
        )

    # ====== SYSTEM ENABLE/DISABLE SWITCHES ======
    
    # GWC system enable/disable
    if "gwc_off" in holding_regs:
        entities.append(
            ThesslaGreenInvertedSwitch(
                coordinator,
                "gwc_off",
                "System GWC",
                "mdi:heat-pump",
                SwitchDeviceClass.SWITCH,
            )
        )

    # Bypass system enable/disable
    if "bypass_off" in holding_regs:
        entities.append(
            ThesslaGreenInvertedSwitch(
                coordinator,
                "bypass_off",
                "System Bypass",
                "mdi:valve",
                SwitchDeviceClass.SWITCH,
            )
        )

    # Comfort mode panel switch
    if "comfort_mode_panel" in holding_regs:
        entities.append(
            ThesslaGreenSwitch(
                coordinator,
                "comfort_mode_panel",
                "Panel KOMFORT",
                "mdi:home-thermometer-outline",
                SwitchDeviceClass.SWITCH,
            )
        )

    # ====== SYSTEM RESET SWITCHES (Special) ======
    
    # Settings reset (momentary switch)
    if "hard_reset_settings" in holding_regs:
        entities.append(
            ThesslaGreenMomentarySwitch(
                coordinator,
                "hard_reset_settings",
                "Reset ustawień użytkownika",
                "mdi:restore",
            )
        )

    # Schedule reset (momentary switch)  
    if "hard_reset_schedule" in holding_regs:
        entities.append(
            ThesslaGreenMomentarySwitch(
                coordinator,
                "hard_reset_schedule",
                "Reset harmonogramów",
                "mdi:calendar-remove",
            )
        )

    # ====== CONTROL FLAGS (Special registers) ======
    
    # Airflow rate change flag (for temporary mode activation)
    if "airflow_rate_change_flag" in holding_regs:
        entities.append(
            ThesslaGreenFlagSwitch(
                coordinator,
                "airflow_rate_change_flag",
                "Flaga zmiany intensywności",
                "mdi:flag",
            )
        )

    # Temperature change flag (for temporary mode activation)
    if "temperature_change_flag" in holding_regs:
        entities.append(
            ThesslaGreenFlagSwitch(
                coordinator,
                "temperature_change_flag",
                "Flaga zmiany temperatury", 
                "mdi:flag-thermometer",
            )
        )

    # GWC regeneration flag (if writable)
    if "gwc_regen_flag" in holding_regs:
        entities.append(
            ThesslaGreenFlagSwitch(
                coordinator,
                "gwc_regen_flag",
                "Wymuszenie regeneracji GWC",
                "mdi:refresh",
            )
        )

    if entities:
        _LOGGER.debug("Adding %d switch entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenMainSwitch(CoordinatorEntity, SwitchEntity):
    """Main device ON/OFF switch."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the main switch."""
        super().__init__(coordinator)
        
        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        
        self._attr_name = f"{device_name} Główny przełącznik"
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_main_switch"
        self._attr_icon = "mdi:power"
        self._attr_device_class = SwitchDeviceClass.SWITCH

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        value = self.coordinator.data.get("on_off_panel_mode")
        if value is None:
            return None
        return value == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        success = await self.coordinator.async_write_register("on_off_panel_mode", 1)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Turned ON main device switch")
        else:
            _LOGGER.error("Failed to turn ON main device switch")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        success = await self.coordinator.async_write_register("on_off_panel_mode", 0)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Turned OFF main device switch")
        else:
            _LOGGER.error("Failed to turn OFF main device switch")

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add current device status info
        device_status = self.coordinator.data.get("device_status_smart")
        if device_status is not None:
            attributes["device_status"] = "Running" if device_status else "Stopped"
        
        # Add mode information
        mode = self.coordinator.data.get("mode")
        if mode is not None:
            mode_names = {0: "Automatyczny", 1: "Manualny", 2: "Chwilowy"}
            attributes["operating_mode"] = mode_names.get(mode, f"Unknown({mode})")
        
        # Add register info
        attributes["modbus_address"] = "0x1123"
        attributes["register_type"] = "holding_register"
        attributes["note"] = "Główny przełącznik ON/OFF urządzenia"
        
        return attributes


class ThesslaGreenSwitch(CoordinatorEntity, SwitchEntity):
    """General ThesslaGreen switch entity."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        device_class: SwitchDeviceClass | None = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class

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
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        return value == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        success = await self.coordinator.async_write_register(self._key, 1)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Turned ON switch %s", self._key)
        else:
            _LOGGER.error("Failed to turn ON switch %s", self._key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        success = await self.coordinator.async_write_register(self._key, 0)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Turned OFF switch %s", self._key)
        else:
            _LOGGER.error("Failed to turn OFF switch %s", self._key)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add current value
        value = self.coordinator.data.get(self._key)
        if value is not None:
            attributes["raw_value"] = value
        
        # Add register information
        from .const import HOLDING_REGISTERS
        if self._key in HOLDING_REGISTERS:
            attributes["modbus_address"] = f"0x{HOLDING_REGISTERS[self._key]:04X}"
            attributes["register_type"] = "holding_register"
        
        return attributes


class ThesslaGreenInvertedSwitch(CoordinatorEntity, SwitchEntity):
    """ThesslaGreen switch with inverted logic (0=ON, 1=OFF)."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        device_class: SwitchDeviceClass | None = None,
    ) -> None:
        """Initialize the inverted switch."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class

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
    def is_on(self) -> bool | None:
        """Return true if the switch is on (inverted logic)."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        # Inverted: 0 = enabled (ON), 1 = disabled (OFF)  
        return value == 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on (write 0 for inverted logic)."""
        success = await self.coordinator.async_write_register(self._key, 0)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Enabled system %s (wrote 0)", self._key)
        else:
            _LOGGER.error("Failed to enable system %s", self._key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off (write 1 for inverted logic)."""
        success = await self.coordinator.async_write_register(self._key, 1)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Disabled system %s (wrote 1)", self._key)
        else:
            _LOGGER.error("Failed to disable system %s", self._key)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add current value and interpretation
        value = self.coordinator.data.get(self._key)
        if value is not None:
            attributes["raw_value"] = value
            attributes["interpretation"] = "Enabled" if value == 0 else "Disabled"
            attributes["logic"] = "Inverted (0=ON, 1=OFF)"
        
        # Add register information
        from .const import HOLDING_REGISTERS
        if self._key in HOLDING_REGISTERS:
            attributes["modbus_address"] = f"0x{HOLDING_REGISTERS[self._key]:04X}"
            attributes["register_type"] = "holding_register"
        
        return attributes


class ThesslaGreenMomentarySwitch(CoordinatorEntity, SwitchEntity):
    """Momentary switch that automatically turns off after activation."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the momentary switch."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = SwitchDeviceClass.SWITCH

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
    def is_on(self) -> bool:
        """Momentary switches are always off."""
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the momentary function."""
        success = await self.coordinator.async_write_register(self._key, 1)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Activated momentary function: %s", self._key)
        else:
            _LOGGER.error("Failed to activate momentary function: %s", self._key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Cannot turn off momentary switch."""
        _LOGGER.debug("Cannot turn off momentary switch %s", self._key)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add register information
        from .const import HOLDING_REGISTERS
        if self._key in HOLDING_REGISTERS:
            attributes["modbus_address"] = f"0x{HOLDING_REGISTERS[self._key]:04X}"
            attributes["register_type"] = "holding_register"
        
        attributes["switch_type"] = "Momentary"
        attributes["note"] = "Aktywuje funkcję po naciśnięciu ON, automatycznie wraca do OFF"
        
        # Add specific notes for reset functions
        if "reset" in self._key:
            attributes["warning"] = "⚠️ Ta funkcja przywraca ustawienia fabryczne!"
        
        return attributes


class ThesslaGreenFlagSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for control flags (used for temporary mode activation)."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the flag switch."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = SwitchDeviceClass.SWITCH

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
    def is_on(self) -> bool | None:
        """Return true if the flag is set."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        return value == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the flag."""
        success = await self.coordinator.async_write_register(self._key, 1)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Set flag %s", self._key)
        else:
            _LOGGER.error("Failed to set flag %s", self._key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear the flag."""
        success = await self.coordinator.async_write_register(self._key, 0)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Cleared flag %s", self._key)
        else:
            _LOGGER.error("Failed to clear flag %s", self._key)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add current value
        value = self.coordinator.data.get(self._key)
        if value is not None:
            attributes["raw_value"] = value
            attributes["flag_status"] = "Set" if value == 1 else "Clear"
        
        # Add register information
        from .const import HOLDING_REGISTERS
        if self._key in HOLDING_REGISTERS:
            attributes["modbus_address"] = f"0x{HOLDING_REGISTERS[self._key]:04X}"
            attributes["register_type"] = "holding_register"
        
        attributes["switch_type"] = "Control Flag"
        
        # Add specific usage notes
        if "airflow_rate_change_flag" in self._key:
            attributes["usage"] = "Ustaw na ON aby aktywować tryb chwilowy dla intensywności"
        elif "temperature_change_flag" in self._key:
            attributes["usage"] = "Ustaw na ON aby aktywować tryb chwilowy dla temperatury"
        elif "gwc_regen_flag" in self._key:
            attributes["usage"] = "Ustaw na ON aby wymusić regenerację GWC"
        
        return attributes

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # Flag switches are more advanced, disable by default
        return False