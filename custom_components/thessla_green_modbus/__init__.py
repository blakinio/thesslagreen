"""ThesslaGreen Modbus integration for Home Assistant - ENHANCED VERSION."""
from __future__ import annotations

import asyncio
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
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    DOMAIN,
    SERVICE_ACTIVATE_BOOST,
    SERVICE_CALIBRATE_SENSORS,
    SERVICE_CONFIGURE_BYPASS,
    SERVICE_CONFIGURE_CONSTANT_FLOW,
    SERVICE_CONFIGURE_GWC,
    SERVICE_DEVICE_RESCAN,
    SERVICE_EMERGENCY_STOP,
    SERVICE_QUICK_VENTILATION,
    SERVICE_RESET_ALARMS,
    SERVICE_SCHEDULE_MAINTENANCE,
    SERVICE_SET_COMFORT_TEMPERATURE,
    SERVICE_SET_INTENSITY,
    SERVICE_SET_MODE,
    SERVICE_SET_SPECIAL_FUNCTION,
)
from .coordinator import ThesslaGreenCoordinator
from .device_scanner import ThesslaGreenDeviceScanner

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

# Enhanced service schemas (HA 2025.7+ Compatible)
SERVICE_SET_MODE_SCHEMA = vol.Schema({
    vol.Required("mode"): vol.In(["auto", "manual", "temporary"]),
})

SERVICE_SET_INTENSITY_SCHEMA = vol.Schema({
    vol.Required("intensity"): vol.All(int, vol.Range(min=10, max=150)),
})

SERVICE_SET_SPECIAL_FUNCTION_SCHEMA = vol.Schema({
    vol.Required("function"): vol.In([
        "none", "hood", "fireplace", "airing_manual", "airing_auto", 
        "empty_house", "open_windows", "boost", "eco", "cooking", 
        "laundry", "bathroom", "night", "vacation", "party"
    ]),
})

SERVICE_RESET_ALARMS_SCHEMA = vol.Schema({
    vol.Optional("alarm_type"): vol.In(["warnings", "errors", "all"]),
})

SERVICE_DEVICE_RESCAN_SCHEMA = vol.Schema({})

# Enhanced service schemas (HA 2025.7+)
SERVICE_SET_COMFORT_TEMPERATURE_SCHEMA = vol.Schema({
    vol.Optional("heating_temperature"): vol.All(float, vol.Range(min=18.0, max=30.0)),
    vol.Optional("cooling_temperature"): vol.All(float, vol.Range(min=20.0, max=35.0)),
})

SERVICE_ACTIVATE_BOOST_SCHEMA = vol.Schema({
    vol.Optional("duration", default=30): vol.All(int, vol.Range(min=5, max=120)),
    vol.Optional("intensity", default=100): vol.All(int, vol.Range(min=50, max=150)),
})

SERVICE_SCHEDULE_MAINTENANCE_SCHEMA = vol.Schema({
    vol.Optional("filter_interval"): vol.All(int, vol.Range(min=90, max=365)),
    vol.Optional("warning_threshold"): vol.All(int, vol.Range(min=7, max=60)),
})

SERVICE_CALIBRATE_SENSORS_SCHEMA = vol.Schema({
    vol.Optional("sensor_type", default="all"): vol.In(["all", "temperature", "flow", "pressure"]),
})

SERVICE_CONFIGURE_GWC_SCHEMA = vol.Schema({
    vol.Optional("mode"): vol.All(int, vol.Range(min=0, max=2)),
    vol.Optional("min_air_temperature"): vol.All(float, vol.Range(min=-10.0, max=10.0)),
    vol.Optional("max_air_temperature"): vol.All(float, vol.Range(min=20.0, max=35.0)),
})

SERVICE_CONFIGURE_BYPASS_SCHEMA = vol.Schema({
    vol.Optional("mode"): vol.All(int, vol.Range(min=0, max=2)),
    vol.Optional("min_temperature"): vol.All(float, vol.Range(min=15.0, max=25.0)),
})

SERVICE_CONFIGURE_CONSTANT_FLOW_SCHEMA = vol.Schema({
    vol.Optional("supply_target"): vol.All(int, vol.Range(min=50, max=500)),
    vol.Optional("exhaust_target"): vol.All(int, vol.Range(min=50, max=500)),
    vol.Optional("tolerance"): vol.All(int, vol.Range(min=5, max=25)),
})

SERVICE_EMERGENCY_STOP_SCHEMA = vol.Schema({})

SERVICE_QUICK_VENTILATION_SCHEMA = vol.Schema({
    vol.Optional("duration", default=15): vol.All(int, vol.Range(min=5, max=60)),
    vol.Optional("intensity", default=80): vol.All(int, vol.Range(min=30, max=120)),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ThesslaGreen Modbus from a config entry - ENHANCED VERSION."""
    _LOGGER.info("Setting up ThesslaGreen Modbus integration (Enhanced v2.0)")
    
    # Get configuration with enhanced error handling
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT] 
    slave_id = entry.data.get(CONF_SLAVE_ID, 10)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    retry = entry.options.get(CONF_RETRY, DEFAULT_RETRY)
    
    _LOGGER.debug(
        "Configuration: host=%s, port=%s, slave_id=%s, scan_interval=%s, timeout=%s, retry=%s",
        host, port, slave_id, scan_interval, timeout, retry
    )
    
    # Enhanced device scanner with capability detection
    try:
        _LOGGER.info("Scanning device capabilities...")
        scanner = ThesslaGreenDeviceScanner(host, port, slave_id)
        device_scan_result = await asyncio.wait_for(
            scanner.scan_device(), 
            timeout=60.0  # Allow up to 60 seconds for initial scan
        )
        
        if not device_scan_result:
            raise ConfigEntryNotReady("Device scan failed - no data received")
            
        available_registers = device_scan_result.get("available_registers", {})
        device_info = device_scan_result.get("device_info", {})
        capabilities = device_scan_result.get("capabilities", {})
        
        _LOGGER.info(
            "Device scan completed: %d input registers, %d holding registers, %d capabilities",
            len(available_registers.get("input_registers", set())),
            len(available_registers.get("holding_registers", set())),
            len([k for k, v in capabilities.items() if v])
        )
        
    except asyncio.TimeoutError:
        _LOGGER.error("Device scan timed out after 60 seconds")
        raise ConfigEntryNotReady("Device scan timeout - check network connectivity")
    except Exception as exc:
        _LOGGER.error("Device scan failed: %s", exc)
        raise ConfigEntryNotReady(f"Device scan error: {exc}")
    
    # Enhanced coordinator setup
    coordinator = ThesslaGreenCoordinator(
        hass=hass,
        host=host,
        port=port,
        slave_id=slave_id,
        scan_interval=scan_interval,
        timeout=timeout,
        retry=retry,
        available_registers=available_registers,
    )
    
    # Store device info in coordinator for entities
    coordinator.device_scan_result = device_scan_result
    
    # Initial data fetch with enhanced error handling
    try:
        _LOGGER.info("Performing initial data fetch...")
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial data fetch completed successfully")
    except Exception as exc:
        _LOGGER.error("Initial data fetch failed: %s", exc)
        raise ConfigEntryNotReady(f"Failed to fetch initial data: {exc}")
    
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Enhanced device registry entry
    device_registry = dr.async_get(hass)
    device_name = device_info.get("device_name", f"ThesslaGreen {host}")
    firmware_version = device_info.get("firmware", "Unknown")
    
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{host}_{slave_id}")},
        name=device_name,
        manufacturer="ThesslaGreen",
        model="AirPack Home",
        sw_version=firmware_version,
        configuration_url=f"http://{host}",
    )
    
    # Setup platforms with enhanced capability-based loading
    _LOGGER.info("Setting up platforms...")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Enhanced service registration (HA 2025.7+ Compatible)
    await _async_register_services(hass, coordinator)
    
    _LOGGER.info("ThesslaGreen Modbus integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading ThesslaGreen Modbus integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Remove coordinator from hass data
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator:
            _LOGGER.debug("Coordinator removed from hass data")
            
        # Remove domain data if no more entries
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)
            
        # Unregister services if no more coordinators
        if not hass.data.get(DOMAIN, {}):
            await _async_unregister_services(hass)
    
    _LOGGER.info("ThesslaGreen Modbus integration unloaded successfully")
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading ThesslaGreen Modbus integration")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def _async_register_services(hass: HomeAssistant, coordinator: ThesslaGreenCoordinator) -> None:
    """Register enhanced services for ThesslaGreen integration."""
    _LOGGER.debug("Registering ThesslaGreen services")
    
    # Basic control services
    async def async_set_operating_mode(call: ServiceCall) -> None:
        """Set operating mode service."""
        mode_map = {"auto": 0, "manual": 1, "temporary": 2}
        mode_value = mode_map[call.data["mode"]]
        
        success = await coordinator.async_write_register("mode", mode_value)
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Set operating mode to %s", call.data["mode"])
        else:
            _LOGGER.error("Failed to set operating mode to %s", call.data["mode"])
    
    async def async_set_intensity(call: ServiceCall) -> None:
        """Set ventilation intensity service."""
        intensity = call.data["intensity"]
        current_mode = coordinator.data.get("mode", 1)
        
        # Determine which register to write based on current mode
        if current_mode == 0:  # Auto mode - switch to manual
            await coordinator.async_write_register("mode", 1)
            register_key = "air_flow_rate_manual"
        elif current_mode == 1:  # Manual mode
            register_key = "air_flow_rate_manual"
        elif current_mode == 2:  # Temporary mode
            register_key = "air_flow_rate_temporary"
        else:
            register_key = "air_flow_rate_manual"
        
        success = await coordinator.async_write_register(register_key, intensity)
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Set intensity to %d%%", intensity)
        else:
            _LOGGER.error("Failed to set intensity to %d%%", intensity)
    
    async def async_set_special_function(call: ServiceCall) -> None:
        """Set special function service."""
        function_map = {
            "none": 0, "hood": 1, "fireplace": 2, "airing_manual": 3, "airing_auto": 4,
            "boost": 5, "eco": 6, "airing": 7, "cooking": 8, "laundry": 9, "bathroom": 10,
            "empty_house": 11, "open_windows": 12, "night": 13, "vacation": 14, "party": 15
        }
        
        function_value = function_map[call.data["function"]]
        success = await coordinator.async_write_register("special_mode", function_value)
        
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Set special function to %s", call.data["function"])
        else:
            _LOGGER.error("Failed to set special function to %s", call.data["function"])
    
    async def async_reset_alarms(call: ServiceCall) -> None:
        """Reset alarms service."""
        alarm_type = call.data.get("alarm_type", "all")
        
        # Reset based on alarm type
        success = True
        if alarm_type in ["all", "errors"]:
            success &= await coordinator.async_write_register("maintenance_reset", 1)
        if alarm_type in ["all", "warnings"]:
            success &= await coordinator.async_write_register("maintenance_reset", 2)
        
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Reset %s alarms", alarm_type)
        else:
            _LOGGER.error("Failed to reset %s alarms", alarm_type)
    
    async def async_rescan_device(call: ServiceCall) -> None:
        """Rescan device capabilities service."""
        _LOGGER.info("Rescanning device capabilities...")
        try:
            scanner = ThesslaGreenDeviceScanner(coordinator.host, coordinator.port, coordinator.slave_id)
            device_scan_result = await asyncio.wait_for(scanner.scan_device(), timeout=60.0)
            
            if device_scan_result:
                coordinator.available_registers = device_scan_result.get("available_registers", {})
                coordinator.device_scan_result = device_scan_result
                await coordinator.async_request_refresh()
                _LOGGER.info("Device rescan completed successfully")
            else:
                _LOGGER.error("Device rescan failed - no data received")
        except Exception as exc:
            _LOGGER.error("Device rescan failed: %s", exc)
    
    # Enhanced services (HA 2025.7+)
    async def async_set_comfort_temperature(call: ServiceCall) -> None:
        """Set comfort temperatures service."""
        success = True
        
        if "heating_temperature" in call.data:
            temp_value = int(call.data["heating_temperature"] * 2)  # Convert to 0.5°C resolution
            success &= await coordinator.async_write_register("comfort_temperature_heating", temp_value)
            
        if "cooling_temperature" in call.data:
            temp_value = int(call.data["cooling_temperature"] * 2)  # Convert to 0.5°C resolution
            success &= await coordinator.async_write_register("comfort_temperature_cooling", temp_value)
        
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Set comfort temperatures")
        else:
            _LOGGER.error("Failed to set comfort temperatures")
    
    async def async_activate_boost_mode(call: ServiceCall) -> None:
        """Activate boost mode service."""
        duration = call.data.get("duration", 30)
        intensity = call.data.get("intensity", 100)
        
        # Set boost mode and parameters
        success = True
        success &= await coordinator.async_write_register("special_mode", 5)  # BOOST mode
        success &= await coordinator.async_write_register("mode", 1)  # Manual mode
        success &= await coordinator.async_write_register("air_flow_rate_manual", intensity)
        success &= await coordinator.async_write_register("boost_time_remaining", duration)
        
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Activated boost mode: %d%% for %d minutes", intensity, duration)
        else:
            _LOGGER.error("Failed to activate boost mode")
    
    async def async_emergency_stop(call: ServiceCall) -> None:
        """Emergency stop service."""
        success = await coordinator.async_write_register("system_on_off", 0)
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.warning("Emergency stop activated")
        else:
            _LOGGER.error("Failed to activate emergency stop")
    
    async def async_quick_ventilation(call: ServiceCall) -> None:
        """Quick ventilation service."""
        duration = call.data.get("duration", 15)
        intensity = call.data.get("intensity", 80)
        
        # Switch to temporary mode with specified parameters
        success = True
        success &= await coordinator.async_write_register("mode", 2)  # Temporary mode
        success &= await coordinator.async_write_register("air_flow_rate_temporary", intensity)
        success &= await coordinator.async_write_register("temporary_time_remaining", duration)
        
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Started quick ventilation: %d%% for %d minutes", intensity, duration)
        else:
            _LOGGER.error("Failed to start quick ventilation")
    
    # Register all services
    services = [
        (SERVICE_SET_MODE, async_set_operating_mode, SERVICE_SET_MODE_SCHEMA),
        (SERVICE_SET_INTENSITY, async_set_intensity, SERVICE_SET_INTENSITY_SCHEMA),
        (SERVICE_SET_SPECIAL_FUNCTION, async_set_special_function, SERVICE_SET_SPECIAL_FUNCTION_SCHEMA),
        (SERVICE_RESET_ALARMS, async_reset_alarms, SERVICE_RESET_ALARMS_SCHEMA),
        (SERVICE_DEVICE_RESCAN, async_rescan_device, SERVICE_DEVICE_RESCAN_SCHEMA),
        (SERVICE_SET_COMFORT_TEMPERATURE, async_set_comfort_temperature, SERVICE_SET_COMFORT_TEMPERATURE_SCHEMA),
        (SERVICE_ACTIVATE_BOOST, async_activate_boost_mode, SERVICE_ACTIVATE_BOOST_SCHEMA),
        (SERVICE_EMERGENCY_STOP, async_emergency_stop, SERVICE_EMERGENCY_STOP_SCHEMA),
        (SERVICE_QUICK_VENTILATION, async_quick_ventilation, SERVICE_QUICK_VENTILATION_SCHEMA),
    ]
    
    for service_name, service_func, service_schema in services:
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(
                DOMAIN, service_name, service_func, schema=service_schema
            )
    
    _LOGGER.debug("Registered %d ThesslaGreen services", len(services))


async def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services when no more coordinators."""
    services_to_remove = [
        SERVICE_SET_MODE,
        SERVICE_SET_INTENSITY,
        SERVICE_SET_SPECIAL_FUNCTION,
        SERVICE_RESET_ALARMS,
        SERVICE_DEVICE_RESCAN,
        SERVICE_SET_COMFORT_TEMPERATURE,
        SERVICE_ACTIVATE_BOOST,
        SERVICE_EMERGENCY_STOP,
        SERVICE_QUICK_VENTILATION,
    ]
    
    for service_name in services_to_remove:
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)
    
    _LOGGER.debug("Unregistered ThesslaGreen services")