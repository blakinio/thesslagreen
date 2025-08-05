"""ThesslaGreen Modbus integration for Home Assistant - ENHANCED VERSION."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import async_register_admin_service

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
    Platform.FAN,
]

# Service schemas
SERVICE_SET_MODE_SCHEMA = vol.Schema({
    vol.Required("mode"): vol.In(["auto", "manual", "temporary"]),
})

SERVICE_SET_INTENSITY_SCHEMA = vol.Schema({
    vol.Required("intensity"): vol.All(int, vol.Range(min=10, max=150)),
})

SERVICE_SET_SPECIAL_FUNCTION_SCHEMA = vol.Schema({
    vol.Required("function"): vol.In([
        "none", "hood", "fireplace", "airing_manual", "airing_auto", 
        "empty_house", "open_windows"
    ]),
})

SERVICE_RESET_ALARMS_SCHEMA = vol.Schema({
    vol.Optional("alarm_type"): vol.In(["warnings", "errors", "all"]),
})

SERVICE_DEVICE_RESCAN_SCHEMA = vol.Schema({})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ThesslaGreen Modbus from a config entry - ENHANCED VERSION."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave_id = entry.data.get("slave_id", 10)
    
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    retry = entry.options.get(CONF_RETRY, DEFAULT_RETRY)

    _LOGGER.info(
        "Setting up ENHANCED ThesslaGreen Modbus: %s:%s (slave_id=%s, scan=%ds)",
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
            "ENHANCED setup successful! Device: %s, Registers: %d, Capabilities: %d",
            coordinator.device_info.get("device_name", "ThesslaGreen"),
            total_registers,
            capabilities_count
        )
        
    except Exception as exc:
        _LOGGER.error("Failed to setup ENHANCED ThesslaGreen coordinator: %s", exc)
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
    """Unload a config entry - ENHANCED."""
    _LOGGER.info("Unloading ENHANCED ThesslaGreen Modbus integration")
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        
        # Unregister services if this was the last entry
        if not hass.data[DOMAIN]:
            await _async_unregister_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry - ENHANCED."""
    _LOGGER.info("Reloading ENHANCED ThesslaGreen Modbus integration")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry - ENHANCED with comprehensive migration."""
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

        # Migrate old slave_id if present in options to data
        if "slave_id" in config_entry.options:
            new_data["slave_id"] = config_entry.options["slave_id"]

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options, version=2
        )

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


async def _async_register_device(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: ThesslaGreenCoordinator
) -> None:
    """Register device in device registry with enhanced information."""
    device_registry = dr.async_get(hass)
    device_info = coordinator.device_info
    
    device_name = device_info.get("device_name", "ThesslaGreen AirPack")
    firmware_version = device_info.get("firmware", "Unknown")
    serial_number = device_info.get("serial_number", f"modbus_{coordinator.host}_{coordinator.slave_id}")
    
    # Determine model based on capabilities
    model = "AirPack"
    if coordinator.capabilities.get("constant_flow"):
        model += " CF"
    if coordinator.capabilities.get("gwc_system"):
        model += " GWC"
    if coordinator.capabilities.get("expansion_module"):
        model += " EXP"
    
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
        name=device_name,
        manufacturer="ThesslaGreen",
        model=model,
        sw_version=firmware_version,
        serial_number=serial_number,
        configuration_url=f"http://{coordinator.host}",
        suggested_area="HVAC",
    )


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    if hass.services.has_service(DOMAIN, "set_mode"):
        return  # Services already registered

    async def async_service_set_mode(call: ServiceCall) -> None:
        """Service to set operating mode."""
        mode_map = {"auto": 0, "manual": 1, "temporary": 2}
        mode_value = mode_map[call.data["mode"]]
        
        for coordinator in hass.data[DOMAIN].values():
            await coordinator.async_write_register("mode", mode_value)
            await coordinator.async_request_refresh()

    async def async_service_set_intensity(call: ServiceCall) -> None:
        """Service to set ventilation intensity."""
        intensity = call.data["intensity"]
        
        for coordinator in hass.data[DOMAIN].values():
            # Set manual mode first, then intensity
            await coordinator.async_write_register("mode", 1)
            await coordinator.async_write_register("air_flow_rate_manual", intensity)
            await coordinator.async_request_refresh()

    async def async_service_set_special_function(call: ServiceCall) -> None:
        """Service to set special function."""
        function_map = {
            "none": 0,
            "hood": 1,
            "fireplace": 2,
            "airing_manual": 7,
            "airing_auto": 8,
            "empty_house": 11,
            "open_windows": 10,
        }
        function_value = function_map[call.data["function"]]
        
        for coordinator in hass.data[DOMAIN].values():
            await coordinator.async_write_register("special_mode", function_value)
            await coordinator.async_request_refresh()

    async def async_service_reset_alarms(call: ServiceCall) -> None:
        """Service to reset alarms."""
        alarm_type = call.data.get("alarm_type", "all")
        
        for coordinator in hass.data[DOMAIN].values():
            if alarm_type in ["warnings", "all"]:
                # Reset warning flag
                await coordinator.async_write_register("alarm_flag", 0)
            
            if alarm_type in ["errors", "all"]:
                # Reset error flag  
                await coordinator.async_write_register("error_flag", 0)
            
            await coordinator.async_request_refresh()

    async def async_service_device_rescan(call: ServiceCall) -> None:
        """Service to rescan device capabilities."""
        for coordinator in hass.data[DOMAIN].values():
            # Trigger a complete device rescan
            from .device_scanner import ThesslaGreenDeviceScanner
            
            scanner = ThesslaGreenDeviceScanner(
                coordinator.host, coordinator.port, coordinator.slave_id
            )
            
            try:
                scan_result = await scanner.scan_device()
                coordinator.available_registers = scan_result["available_registers"]
                coordinator.device_info = scan_result["device_info"]
                coordinator.capabilities = scan_result["capabilities"]
                
                # Re-compute register groups
                coordinator._precompute_register_groups()
                
                await coordinator.async_request_refresh()
                _LOGGER.info("Device rescan completed successfully")
                
            except Exception as exc:
                _LOGGER.error("Device rescan failed: %s", exc)

    # Register services
    hass.services.async_register(
        DOMAIN, "set_mode", async_service_set_mode, schema=SERVICE_SET_MODE_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "set_intensity", async_service_set_intensity, schema=SERVICE_SET_INTENSITY_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "set_special_function", async_service_set_special_function, 
        schema=SERVICE_SET_SPECIAL_FUNCTION_SCHEMA
    )
    
    async_register_admin_service(
        hass, DOMAIN, "reset_alarms", async_service_reset_alarms, 
        schema=SERVICE_RESET_ALARMS_SCHEMA
    )
    
    async_register_admin_service(
        hass, DOMAIN, "device_rescan", async_service_device_rescan,
        schema=SERVICE_DEVICE_RESCAN_SCHEMA
    )

    _LOGGER.debug("ThesslaGreen services registered")


async def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister integration services."""
    services = ["set_mode", "set_intensity", "set_special_function", "reset_alarms", "device_rescan"]
    
    for service in services:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
    
    _LOGGER.debug("ThesslaGreen services unregistered")