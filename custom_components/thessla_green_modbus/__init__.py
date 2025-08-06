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
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CONF_RETRY,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    CONF_FORCE_FULL_REGISTER_LIST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    DOMAIN,
    PLATFORMS,
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
    INPUT_REGISTERS,
    HOLDING_REGISTERS,
    COIL_REGISTERS,
    DISCRETE_INPUTS,
)
from .coordinator import ThesslaGreenCoordinator
from .device_scanner import ThesslaGreenDeviceScanner

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


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
    vol.Optional("filter_warning"): vol.All(int, vol.Range(min=7, max=60)),
})

SERVICE_EMERGENCY_STOP_SCHEMA = vol.Schema({})

SERVICE_QUICK_VENTILATION_SCHEMA = vol.Schema({
    vol.Optional("duration", default=15): vol.All(int, vol.Range(min=5, max=60)),
    vol.Optional("intensity", default=80): vol.All(int, vol.Range(min=50, max=150)),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ThesslaGreen Modbus from a config entry."""
    _LOGGER.info("Setting up ThesslaGreen Modbus integration (Enhanced v2.0)")
    
    # Extract configuration
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave_id = entry.data[CONF_SLAVE_ID]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    retry = entry.options.get(CONF_RETRY, DEFAULT_RETRY)
    force_full = entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)

    _LOGGER.debug(
        "Configuration: host=%s, port=%s, slave_id=%s, scan_interval=%s, timeout=%s, retry=%s, force_full=%s",
        host,
        port,
        slave_id,
        scan_interval,
        timeout,
        retry,
        force_full,
    )

    if force_full:
        _LOGGER.warning(
            "force_full_register_list enabled - skipping device scan; unsupported registers may cause errors"
        )
        available_registers = {
            "input_registers": set(INPUT_REGISTERS.keys()),
            "holding_registers": set(HOLDING_REGISTERS.keys()),
            "coil_registers": set(COIL_REGISTERS.keys()),
            "discrete_inputs": set(DISCRETE_INPUTS.keys()),
        }
        device_info = {}
        capabilities = {}
    else:
        # Enhanced device scanning with timeout
        _LOGGER.info("Scanning device capabilities...")
        scanner = ThesslaGreenDeviceScanner(host, port, slave_id, timeout)

        try:
            device_scan_result = await asyncio.wait_for(
                scanner.scan_device(),
                timeout=60.0  # 60 second timeout for device scan
            )

            available_registers = device_scan_result["available_registers"]
            device_info = device_scan_result["device_info"]
            capabilities = device_scan_result["capabilities"]

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

    device_scan_result = {
        "available_registers": available_registers,
        "device_info": device_info,
        "capabilities": capabilities,
    }
    
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
        scan_statistics=device_scan_result["scan_statistics"],
    )

    # Store device info in coordinator for entities
    coordinator.device_scan_result = device_scan_result
    coordinator.force_full_register_list = force_full
    
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
        
        # Determine which intensity register to write based on current mode
        current_mode = coordinator.data.get("mode", 1)
        
        if current_mode == 0:  # Auto mode
            register_key = "air_flow_rate_auto"
        elif current_mode == 1:  # Manual mode
            register_key = "air_flow_rate_manual"
        elif current_mode == 2:  # Temporary mode
            register_key = "air_flow_rate_temporary"
        else:
            register_key = "air_flow_rate_manual"  # Default
        
        success = await coordinator.async_write_register(register_key, intensity)
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Set intensity to %d%% (%s)", intensity, register_key)
        else:
            _LOGGER.error("Failed to set intensity to %d%%", intensity)
    
    async def async_set_special_function(call: ServiceCall) -> None:
        """Set special function service."""
        function = call.data["function"]
        
        # Map function names to values
        function_map = {
            "none": 0, "hood": 1, "fireplace": 2, "airing_manual": 3, "airing_auto": 4,
            "empty_house": 11, "open_windows": 7, "boost": 5, "eco": 6,
            "cooking": 8, "laundry": 9, "bathroom": 10, "night": 13, "vacation": 12, "party": 14
        }
        
        function_value = function_map.get(function, 0)
        success = await coordinator.async_write_register("special_mode", function_value)
        
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Set special function to %s", function)
        else:
            _LOGGER.error("Failed to set special function to %s", function)
    
    async def async_reset_alarms(call: ServiceCall) -> None:
        """Reset alarms service."""
        alarm_type = call.data.get("alarm_type", "all")
        
        success = True
        if alarm_type in ["errors", "all"]:
            success &= await coordinator.async_write_register("error_code", 0)
        if alarm_type in ["warnings", "all"]:
            success &= await coordinator.async_write_register("warning_code", 0)
        
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Reset %s alarms", alarm_type)
        else:
            _LOGGER.error("Failed to reset %s alarms", alarm_type)
    
    async def async_rescan_device(call: ServiceCall) -> None:
        """Rescan device capabilities service."""
        _LOGGER.info("Starting device rescan...")
        if getattr(coordinator, "force_full_register_list", False):
            _LOGGER.info(
                "force_full_register_list enabled - applying full register list without scanning"
            )
            coordinator.available_registers = {
                "input_registers": set(INPUT_REGISTERS.keys()),
                "holding_registers": set(HOLDING_REGISTERS.keys()),
                "coil_registers": set(COIL_REGISTERS.keys()),
                "discrete_inputs": set(DISCRETE_INPUTS.keys()),
            }
            coordinator.device_scan_result = {
                "available_registers": coordinator.available_registers,
                "device_info": {},
                "capabilities": {},
            }
            await coordinator.async_request_refresh()
            _LOGGER.info(
                "Device rescan skipped; full register list applied"
            )
            return

        try:
            scanner = ThesslaGreenDeviceScanner(
                coordinator.host, coordinator.port, coordinator.slave_id, coordinator.timeout
            )
            device_scan_result = await scanner.scan_device()

            # Update coordinator with new scan results
            coordinator.available_registers = device_scan_result["available_registers"]
            coordinator.device_scan_result = device_scan_result
 codex/enhance-logging-in-device-scanner
            coordinator.scan_statistics = device_scan_result["scan_statistics"]
            stats = coordinator.scan_statistics
            _LOGGER.debug(
                "Rescan stats: %.1f%% success (%d/%d), %d failed groups",
                stats.get("success_rate", 0.0),
                stats.get("successful_reads", 0),
                stats.get("total_attempts", 0),
                len(stats.get("failed_groups", [])),
            )
            
=======

 main
            await coordinator.async_request_refresh()

            _LOGGER.info("Device rescan completed successfully")
        except Exception as exc:
            _LOGGER.error("Device rescan failed: %s", exc)
    
    # Enhanced services (HA 2025.7+)
    async def async_set_comfort_temperature(call: ServiceCall) -> None:
        """Set comfort temperatures service."""
        success = True
        
        if "heating_temperature" in call.data:
            temp_value = int(call.data["heating_temperature"] * 10)  # Convert to 0.1°C units
            success &= await coordinator.async_write_register("comfort_temperature_heating", temp_value)
        
        if "cooling_temperature" in call.data:
            temp_value = int(call.data["cooling_temperature"] * 10)  # Convert to 0.1°C units
            success &= await coordinator.async_write_register("comfort_temperature_cooling", temp_value)
        
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Updated comfort temperatures")
        else:
            _LOGGER.error("Failed to update comfort temperatures")
    
    async def async_activate_boost_mode(call: ServiceCall) -> None:
        """Activate boost mode service."""
        duration = call.data.get("duration", 30)
        intensity = call.data.get("intensity", 100)
        
        # Set special mode to boost and configure parameters
        success = True
        success &= await coordinator.async_write_register("special_mode", 5)  # Boost mode
        success &= await coordinator.async_write_register("boost_duration", duration)
        success &= await coordinator.async_write_register("air_flow_rate_temporary", intensity)
        
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