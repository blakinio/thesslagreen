"""ThesslaGreen Modbus integration for Home Assistant - OPTIMIZED VERSION."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_RETRY,
    CONF_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    DOMAIN,
)
from .coordinator import ThesslaGreenCoordinator

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.CLIMATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ThesslaGreen Modbus from a config entry - OPTIMIZED VERSION."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave_id = entry.data.get("slave_id", 10)
    
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    retry = entry.options.get(CONF_RETRY, DEFAULT_RETRY)

    _LOGGER.info(
        "Setting up OPTIMIZED ThesslaGreen Modbus: %s:%s (slave_id=%s, scan=%ds)",
        host, port, slave_id, scan_interval,
    )

    coordinator = ThesslaGreenCoordinator(
        hass=hass,
        host=host,
        port=port,
        slave_id=slave_id,
        scan_interval=scan_interval,
        timeout=timeout,
        retry=retry,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
        
        # Log optimization results
        total_registers = sum(len(regs) for regs in coordinator.available_registers.values())
        capabilities_count = len([k for k, v in coordinator.capabilities.items() if v])
        
        _LOGGER.info(
            "OPTIMIZED setup successful! Device: %s, Registers: %d, Capabilities: %d",
            coordinator.device_info.get("device_name", "ThesslaGreen"),
            total_registers,
            capabilities_count
        )
        
    except Exception as exc:
        _LOGGER.error("Failed to setup OPTIMIZED ThesslaGreen coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Failed to connect to device: {exc}") from exc

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # ENHANCEMENT: Register device in device registry with enhanced info
    await _async_register_device(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # ENHANCEMENT: Register services
    await _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry - OPTIMIZED."""
    _LOGGER.info("Unloading OPTIMIZED ThesslaGreen Modbus integration")
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        
        # Unregister services if this was the last entry
        if not hass.data[DOMAIN]:
            await _async_unregister_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry - OPTIMIZED."""
    _LOGGER.info("Reloading OPTIMIZED ThesslaGreen Modbus integration")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry - ENHANCED."""
    _LOGGER.info("Migrating ThesslaGreen configuration from version %s", config_entry.version)

    if config_entry.version == 1:
        # Version 1 -> 2: Add new optimization configuration options
        new_data = {**config_entry.data}
        new_options = {
            **config_entry.options,
            CONF_SCAN_INTERVAL: config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_TIMEOUT: config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            CONF_RETRY: config_entry.options.get(CONF_RETRY, DEFAULT_RETRY),
        }

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options, version=2
        )

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


async def _async_register_device(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    coordinator: ThesslaGreenCoordinator
) -> None:
    """Register device in device registry with enhanced information."""
    device_registry = dr.async_get(hass)
    device_info = coordinator.device_info
    
    # Enhanced device identification
    identifiers = {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")}
    
    # Enhanced device information
    device_name = device_info.get("device_name", "ThesslaGreen AirPack")
    manufacturer = "ThesslaGreen"
    model = "AirPack"
    
    # Enhanced model detection based on capabilities
    if coordinator.capabilities.get("constant_flow"):
        model += " CF"
    if coordinator.capabilities.get("gwc_system"):
        model += " GWC"
    if coordinator.capabilities.get("expansion_module"):
        model += " EXP"
    
    sw_version = device_info.get("firmware", "Unknown")
    serial_number = device_info.get("serial_number")
    
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=identifiers,
        manufacturer=manufacturer,
        model=model,
        name=device_name,
        sw_version=sw_version,
        serial_number=serial_number,
        configuration_url=f"http://{coordinator.host}",
    )
    
    _LOGGER.debug(
        "Registered device: %s %s (FW: %s, S/N: %s)",
        manufacturer, model, sw_version, serial_number
    )


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    if hass.services.has_service(DOMAIN, "rescan_device"):
        return  # Services already registered
    
    async def async_rescan_device(call) -> None:
        """Service to rescan device capabilities."""
        entry_id = call.data.get("entry_id")
        
        if entry_id and entry_id in hass.data[DOMAIN]:
            coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry_id]
            _LOGGER.info("Rescanning device capabilities for %s", coordinator.host)
            
            try:
                # Force a fresh scan
                await coordinator.async_config_entry_first_refresh()
                _LOGGER.info("Device rescan completed successfully")
            except Exception as exc:
                _LOGGER.error("Device rescan failed: %s", exc)
        else:
            _LOGGER.error("Invalid entry_id for rescan: %s", entry_id)

    async def async_set_special_mode(call) -> None:
        """Service to set special mode."""
        entry_id = call.data.get("entry_id")
        mode = call.data.get("mode", 0)
        
        if entry_id and entry_id in hass.data[DOMAIN]:
            coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry_id]
            success = await coordinator.async_write_register("special_mode", mode)
            if success:
                _LOGGER.info("Special mode set to %d", mode)
            else:
                _LOGGER.error("Failed to set special mode")

    async def async_reset_alarms(call) -> None:
        """Service to reset alarms."""
        entry_id = call.data.get("entry_id")
        
        if entry_id and entry_id in hass.data[DOMAIN]:
            coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry_id]
            # Reset alarm flags by writing 1 to them
            success = True
            if "alarm_flag" in coordinator.available_registers.get("holding_registers", set()):
                success &= await coordinator.async_write_register("alarm_flag", 1)
            if "error_flag" in coordinator.available_registers.get("holding_registers", set()):
                success &= await coordinator.async_write_register("error_flag", 1)
            
            if success:
                _LOGGER.info("Alarm reset completed")
            else:
                _LOGGER.error("Failed to reset alarms")

    # Register services
    hass.services.async_register(
        DOMAIN, "rescan_device", async_rescan_device
    )
    hass.services.async_register(
        DOMAIN, "set_special_mode", async_set_special_mode
    )
    hass.services.async_register(
        DOMAIN, "reset_alarms", async_reset_alarms
    )
    
    _LOGGER.debug("Registered ThesslaGreen services")


async def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister integration services."""
    services = ["rescan_device", "set_special_mode", "reset_alarms"]
    
    for service in services:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
    
    _LOGGER.debug("Unregistered ThesslaGreen services")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the ThesslaGreen Modbus integration."""
    # This integration is set up via config flow only
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    _LOGGER.info("Removing ThesslaGreen Modbus integration entry: %s", entry.title)
    
    # Clean up any persistent data if needed
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()


# Error handling for common issues
class ThesslaGreenSetupError(Exception):
    """Exception raised during setup."""


class ThesslaGreenConnectionError(Exception):
    """Exception raised for connection issues."""