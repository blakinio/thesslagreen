"""Enhanced ThesslaGreen Modbus Integration for Home Assistant.
Kompletna integracja z wszystkimi rejestrami, autoscan i serwisami.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_RETRY,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    DEFAULT_RETRY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_TIMEOUT,
    DOMAIN,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    PLATFORMS,
)
from .coordinator import ThesslaGreenCoordinator
from .device_scanner import ThesslaGreenDeviceScanner
from . import config_flow  # noqa: F401

_LOGGER = logging.getLogger(__name__)

# Enhanced service schemas for comprehensive control
SERVICE_SET_MODE_SCHEMA = vol.Schema({
    vol.Required("mode"): vol.In(["off", "manual", "auto", "temporary"]),
    vol.Optional("intensity"): vol.All(int, vol.Range(min=10, max=150)),
})

SERVICE_SET_SPECIAL_MODE_SCHEMA = vol.Schema({
    vol.Required("special_mode"): vol.In([
        "none", "okap", "kominek", "wietrzenie", "pusty_dom", "boost", 
        "night", "party", "vacation", "economy", "comfort"
    ]),
    vol.Optional("intensity"): vol.All(int, vol.Range(min=10, max=150)),
    vol.Optional("duration"): vol.All(int, vol.Range(min=5, max=1440)),
})

SERVICE_SET_TEMPERATURE_SCHEMA = vol.Schema({
    vol.Required("temperature"): vol.All(float, vol.Range(min=15.0, max=45.0)),
    vol.Optional("mode"): vol.In(["manual", "auto", "temporary", "comfort"]),
})

SERVICE_SET_FAN_SPEED_SCHEMA = vol.Schema({
    vol.Optional("supply_speed"): vol.All(int, vol.Range(min=0, max=100)),
    vol.Optional("exhaust_speed"): vol.All(int, vol.Range(min=0, max=100)),
    vol.Optional("balance"): vol.All(int, vol.Range(min=-20, max=20)),
})

SERVICE_CONTROL_BYPASS_SCHEMA = vol.Schema({
    vol.Required("mode"): vol.In(["auto", "open", "closed"]),
})

SERVICE_CONTROL_GWC_SCHEMA = vol.Schema({
    vol.Required("mode"): vol.In(["auto", "on", "off"]),
})

SERVICE_RESET_ALARMS_SCHEMA = vol.Schema({
    vol.Optional("alarm_type", default="all"): vol.In(["errors", "warnings", "all"]),
})

SERVICE_SET_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required("day"): vol.In(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]),
    vol.Required("period"): vol.All(int, vol.Range(min=1, max=4)),
    vol.Required("start_time"): cv.string,
    vol.Required("end_time"): cv.string,
    vol.Optional("intensity"): vol.All(int, vol.Range(min=10, max=150)),
    vol.Optional("temperature"): vol.All(float, vol.Range(min=15.0, max=45.0)),
})

SERVICE_RESCAN_DEVICE_SCHEMA = vol.Schema({})

SERVICE_GET_DIAGNOSTIC_INFO_SCHEMA = vol.Schema({})

SERVICE_BACKUP_SETTINGS_SCHEMA = vol.Schema({
    vol.Optional("include_schedule", default=True): cv.boolean,
    vol.Optional("include_alarms", default=False): cv.boolean,
})

SERVICE_RESTORE_SETTINGS_SCHEMA = vol.Schema({
    vol.Required("backup_data"): dict,
    vol.Optional("restore_schedule", default=True): cv.boolean,
})

SERVICE_CALIBRATE_SENSORS_SCHEMA = vol.Schema({
    vol.Optional("outside_offset"): vol.All(float, vol.Range(min=-10.0, max=10.0)),
    vol.Optional("supply_offset"): vol.All(float, vol.Range(min=-10.0, max=10.0)),
    vol.Optional("exhaust_offset"): vol.All(float, vol.Range(min=-10.0, max=10.0)),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ThesslaGreen Modbus from a config entry with enhanced features."""
    _LOGGER.info("Setting up ThesslaGreen Modbus integration (Enhanced v2.0+)")
    
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
        host, port, slave_id, scan_interval, timeout, retry, force_full,
    )

    if force_full:
        _LOGGER.warning(
            "force_full_register_list enabled - skipping device scan; unsupported registers may cause errors"
        )
        available_registers = {
            "input_registers": set(INPUT_REGISTERS.keys()),
            "holding_registers": set(HOLDING_REGISTERS.keys()),
            "coil_registers": set(),  # Will be filled if needed
            "discrete_inputs": set(),  # Will be filled if needed
        }
        device_info = {}
        capabilities = {}
        scan_statistics = {}
    else:
        # Enhanced device scanning with comprehensive error handling
        _LOGGER.info("Scanning device capabilities and available registers...")
        scanner = ThesslaGreenDeviceScanner(host, port, slave_id, timeout)

        try:
            device_scan_result = await asyncio.wait_for(
                scanner.scan_device(),
                timeout=90.0  # Extended timeout for comprehensive scan
            )

            available_registers = device_scan_result["available_registers"]
            device_info = device_scan_result["device_info"]
            capabilities = device_scan_result["capabilities"]
            scan_statistics = device_scan_result["scan_statistics"]

            _LOGGER.info(
                "Device scan completed: %d input, %d holding, %d coil, %d discrete registers found",
                len(available_registers.get("input_registers", set())),
                len(available_registers.get("holding_registers", set())),
                len(available_registers.get("coil_registers", set())),
                len(available_registers.get("discrete_inputs", set()))
            )
            
            # Log capabilities summary
            enabled_capabilities = [k for k, v in capabilities.items() if v]
            _LOGGER.info("Device capabilities detected: %s", ", ".join(enabled_capabilities[:10]))  # Show first 10

        except asyncio.TimeoutError:
            _LOGGER.error("Device scan timed out after 90 seconds - check network connectivity")
            raise ConfigEntryNotReady("Device scan timeout - verify device is accessible")
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise ConfigEntryNotReady(f"Device scan error: {exc}")

    # Enhanced coordinator setup with comprehensive register support
    coordinator = ThesslaGreenCoordinator(
        hass=hass,
        host=host,
        port=port,
        slave_id=slave_id,
        scan_interval=scan_interval,
        timeout=timeout,
        retry=retry,
        available_registers=available_registers,
        scan_statistics=scan_statistics,
        device_info=device_info,
        capabilities=capabilities,
    )

    # Store comprehensive device information in coordinator
    coordinator.device_scan_result = {
        "available_registers": available_registers,
        "device_info": device_info,
        "capabilities": capabilities,
        "scan_statistics": scan_statistics,
    }
    coordinator.force_full_register_list = force_full

    # Perform initial data fetch to verify connectivity
    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as exc:
        _LOGGER.error("Initial data fetch failed: %s", exc)
        raise ConfigEntryNotReady(f"Cannot connect to device: {exc}")

    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register enhanced services
    await _async_register_services(hass, coordinator)

    _LOGGER.info(
        "ThesslaGreen Modbus integration setup completed successfully - %d platforms, %d services",
        len(PLATFORMS), 12  # Number of services we're registering
    )

    return True


async def _async_register_services(hass: HomeAssistant, coordinator: ThesslaGreenCoordinator) -> None:
    """Register enhanced services for comprehensive device control."""
    
    async def async_set_mode(call: ServiceCall) -> None:
        """Set operation mode service."""
        mode = call.data["mode"]
        intensity = call.data.get("intensity")
        
        mode_values = {"off": 0, "manual": 1, "auto": 2, "temporary": 3}
        mode_value = mode_values.get(mode, 0)
        
        success = True
        if mode == "off":
            success = await coordinator.async_write_register("on_off_panel_mode", 0)
        else:
            await coordinator.async_write_register("on_off_panel_mode", 1)
            success = await coordinator.async_write_register("mode", mode_value)
            
            if intensity is not None and mode in ["manual", "temporary"]:
                intensity_reg = f"air_flow_rate_{mode}"
                await coordinator.async_write_register(intensity_reg, intensity)
        
        if success:
            _LOGGER.info("Set operation mode to %s", mode)
        else:
            _LOGGER.error("Failed to set operation mode to %s", mode)

    async def async_set_special_mode(call: ServiceCall) -> None:
        """Set special mode service."""
        special_mode = call.data["special_mode"]
        intensity = call.data.get("intensity")
        duration = call.data.get("duration")
        
        mode_values = {
            "none": 0, "okap": 1, "kominek": 2, "wietrzenie": 3, "pusty_dom": 4,
            "boost": 5, "night": 6, "party": 7, "vacation": 8, "economy": 9, "comfort": 10
        }
        
        mode_value = mode_values.get(special_mode, 0)
        
        if special_mode != "none":
            # Ensure system is on and in manual mode for special modes
            await coordinator.async_write_register("on_off_panel_mode", 1)
            await coordinator.async_write_register("mode", 1)
        
        success = await coordinator.async_write_register("special_mode", mode_value)
        
        # Set intensity if provided
        if intensity is not None and special_mode != "none":
            intensity_reg = f"{special_mode}_intensity"
            await coordinator.async_write_register(intensity_reg, intensity)
        
        # Set duration if provided
        if duration is not None and special_mode != "none":
            duration_reg = f"{special_mode}_duration"
            await coordinator.async_write_register(duration_reg, duration)
        
        if success:
            _LOGGER.info("Set special mode to %s", special_mode)
        else:
            _LOGGER.error("Failed to set special mode to %s", special_mode)

    async def async_set_temperature(call: ServiceCall) -> None:
        """Set temperature service."""
        temperature = call.data["temperature"]
        mode = call.data.get("mode", "comfort")
        
        # Convert temperature to register format
        temp_value = int(temperature * 2)  # 0.5°C resolution for most registers
        
        mode_registers = {
            "manual": "supply_temperature_manual",
            "auto": "supply_temperature_auto", 
            "temporary": "supply_temperature_temporary",
            "comfort": "comfort_temperature",
        }
        
        register = mode_registers.get(mode, "comfort_temperature")
        success = await coordinator.async_write_register(register, temp_value)
        
        if success:
            _LOGGER.info("Set %s temperature to %s°C", mode, temperature)
        else:
            _LOGGER.error("Failed to set %s temperature to %s°C", mode, temperature)

    async def async_set_fan_speed(call: ServiceCall) -> None:
        """Set fan speed service."""
        supply_speed = call.data.get("supply_speed")
        exhaust_speed = call.data.get("exhaust_speed")
        balance = call.data.get("balance")
        
        success = True
        if supply_speed is not None:
            success &= await coordinator.async_write_register("supply_fan_speed", supply_speed)
        
        if exhaust_speed is not None:
            success &= await coordinator.async_write_register("exhaust_fan_speed", exhaust_speed)
        
        if balance is not None:
            success &= await coordinator.async_write_register("flow_balance", balance)
        
        if success:
            _LOGGER.info("Set fan speeds: supply=%s, exhaust=%s, balance=%s", supply_speed, exhaust_speed, balance)
        else:
            _LOGGER.error("Failed to set fan speeds")

    async def async_control_bypass(call: ServiceCall) -> None:
        """Control bypass service."""
        mode = call.data["mode"]
        mode_values = {"auto": 0, "open": 1, "closed": 2}
        mode_value = mode_values.get(mode, 0)
        
        success = await coordinator.async_write_register("bypass_mode", mode_value)
        
        if success:
            _LOGGER.info("Set bypass mode to %s", mode)
        else:
            _LOGGER.error("Failed to set bypass mode to %s", mode)

    async def async_control_gwc(call: ServiceCall) -> None:
        """Control GWC service."""
        mode = call.data["mode"]
        mode_values = {"auto": 0, "on": 1, "off": 2}
        mode_value = mode_values.get(mode, 0)
        
        success = await coordinator.async_write_register("gwc_mode", mode_value)
        
        if success:
            _LOGGER.info("Set GWC mode to %s", mode)
        else:
            _LOGGER.error("Failed to set GWC mode to %s", mode)

    async def async_reset_alarms(call: ServiceCall) -> None:
        """Reset alarms service."""
        alarm_type = call.data.get("alarm_type", "all")
        
        success = True
        if alarm_type in ["errors", "all"]:
            success &= await coordinator.async_write_register("error_status", 0)
        if alarm_type in ["warnings", "all"]:
            success &= await coordinator.async_write_register("alarm_status", 0)
        
        if success:
            await coordinator.async_request_refresh()
            _LOGGER.info("Reset %s alarms", alarm_type)
        else:
            _LOGGER.error("Failed to reset %s alarms", alarm_type)

    async def async_set_schedule(call: ServiceCall) -> None:
        """Set schedule service."""
        day = call.data["day"]
        period = call.data["period"]
        start_time = call.data["start_time"]
        end_time = call.data["end_time"]
        intensity = call.data.get("intensity")
        temperature = call.data.get("temperature")
        
        # Convert time format HH:MM to HHMM
        def time_to_register(time_str):
            hours, minutes = time_str.split(":")
            return int(hours) * 100 + int(minutes)
        
        start_reg = f"schedule_{day}_period{period}_start"
        end_reg = f"schedule_{day}_period{period}_end"
        
        success = True
        success &= await coordinator.async_write_register(start_reg, time_to_register(start_time))
        success &= await coordinator.async_write_register(end_reg, time_to_register(end_time))
        
        if intensity is not None:
            intensity_reg = f"schedule_{day}_period{period}_intensity"
            success &= await coordinator.async_write_register(intensity_reg, intensity)
        
        if temperature is not None:
            temp_reg = f"schedule_{day}_period{period}_temp"
            success &= await coordinator.async_write_register(temp_reg, int(temperature * 2))
        
        if success:
            _LOGGER.info("Set schedule for %s period %d: %s-%s", day, period, start_time, end_time)
        else:
            _LOGGER.error("Failed to set schedule for %s period %d", day, period)

    async def async_rescan_device(call: ServiceCall) -> None:
        """Rescan device capabilities service."""
        _LOGGER.info("Starting device rescan...")
        if getattr(coordinator, "force_full_register_list", False):
            _LOGGER.info("force_full_register_list enabled - applying full register list without scanning")
            coordinator.available_registers = {
                "input_registers": set(INPUT_REGISTERS.keys()),
                "holding_registers": set(HOLDING_REGISTERS.keys()),
                "coil_registers": set(),
                "discrete_inputs": set(),
            }
            coordinator.device_scan_result = {
                "available_registers": coordinator.available_registers,
                "device_info": {},
                "capabilities": {},
                "scan_statistics": {},
            }
            await coordinator.async_request_refresh()
            _LOGGER.info("Device rescan skipped; full register list applied")
            return

        try:
            scanner = ThesslaGreenDeviceScanner(
                coordinator.host, coordinator.port, coordinator.slave_id, coordinator.timeout
            )
            device_scan_result = await scanner.scan_device()

            # Update coordinator with new scan results
            coordinator.available_registers = device_scan_result["available_registers"]
            coordinator.device_scan_result = device_scan_result
            coordinator.scan_statistics = device_scan_result["scan_statistics"]
            
            # Log scan statistics
            stats = coordinator.scan_statistics
            _LOGGER.info(
                "Rescan completed: %.1f%% success (%d/%d), %d failed groups, %.1fs duration",
                stats.get("success_rate", 0.0),
                stats.get("successful_reads", 0),
                stats.get("total_attempts", 0),
                len(stats.get("failed_groups", [])),
                stats.get("duration", 0)
            )
            await coordinator.async_request_refresh()

            _LOGGER.info("Device rescan completed successfully")
        except Exception as exc:
            _LOGGER.error("Device rescan failed: %s", exc)

    async def async_get_diagnostic_info(call: ServiceCall) -> None:
        """Get diagnostic information service."""
        perf_stats = coordinator.performance_stats
        
        diagnostic_info = {
            "device_info": coordinator.device_info_data,
            "performance_stats": perf_stats,
            "available_registers": {
                k: len(v) for k, v in coordinator.available_registers.items()
            },
            "scan_statistics": getattr(coordinator, "scan_statistics", {}),
            "last_update": coordinator.last_update_success_time.isoformat() if coordinator.last_update_success_time else None,
        }
        
        # Store diagnostic info as persistent notification
        hass.components.persistent_notification.create(
            f"**ThesslaGreen Diagnostic Info**\n\n"
            f"Device: {diagnostic_info['device_info'].get('model', 'Unknown')}\n"
            f"Firmware: {diagnostic_info['device_info'].get('firmware_version', 'Unknown')}\n"
            f"Success Rate: {perf_stats.get('success_rate', 0):.1f}%\n"
            f"Total Registers: {sum(diagnostic_info['available_registers'].values())}\n"
            f"Last Update: {diagnostic_info['last_update'] or 'Never'}\n\n"
            f"See logs for complete diagnostic information.",
            "ThesslaGreen Diagnostics",
            f"{DOMAIN}_diagnostics"
        )
        
        _LOGGER.info("Diagnostic info: %s", diagnostic_info)

    async def async_backup_settings(call: ServiceCall) -> None:
        """Backup device settings service."""
        include_schedule = call.data.get("include_schedule", True)
        include_alarms = call.data.get("include_alarms", False)
        
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "device_info": coordinator.device_info_data,
            "settings": {},
        }
        
        # Backup basic settings
        basic_settings = [
            "comfort_temperature", "economy_temperature", "heating_temperature", "cooling_temperature",
            "filter_change_interval", "filter_warning_days", "maintenance_interval"
        ]
        
        for setting in basic_settings:
            if setting in coordinator.data:
                backup_data["settings"][setting] = coordinator.data[setting]
        
        # Backup schedule if requested
        if include_schedule:
            backup_data["schedule"] = {}
            for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
                for period in [1, 2, 3, 4]:
                    for time_type in ["start", "end"]:
                        key = f"schedule_{day}_period{period}_{time_type}"
                        if key in coordinator.data:
                            backup_data["schedule"][key] = coordinator.data[key]
        
        # Backup alarm settings if requested
        if include_alarms:
            backup_data["alarms"] = {}
            alarm_settings = [
                "temperature_alarm_limit", "pressure_alarm_limit", "flow_alarm_limit",
                "humidity_alarm_limit", "co2_alarm_limit"
            ]
            for setting in alarm_settings:
                if setting in coordinator.data:
                    backup_data["alarms"][setting] = coordinator.data[setting]
        
        # Store backup as persistent notification with instructions
        hass.components.persistent_notification.create(
            f"**ThesslaGreen Settings Backup Created**\n\n"
            f"Timestamp: {backup_data['timestamp']}\n"
            f"Settings: {len(backup_data['settings'])} items\n"
            f"Schedule: {'Included' if include_schedule else 'Not included'}\n"
            f"Alarms: {'Included' if include_alarms else 'Not included'}\n\n"
            f"Backup data has been logged. Use the restore service to restore settings.",
            "ThesslaGreen Backup",
            f"{DOMAIN}_backup"
        )
        
        _LOGGER.info("Settings backup created: %s", backup_data)

    async def async_restore_settings(call: ServiceCall) -> None:
        """Restore device settings service."""
        backup_data = call.data["backup_data"]
        restore_schedule = call.data.get("restore_schedule", True)
        
        success_count = 0
        total_count = 0
        
        # Restore basic settings
        if "settings" in backup_data:
            for key, value in backup_data["settings"].items():
                total_count += 1
                if await coordinator.async_write_register(key, value):
                    success_count += 1
                    _LOGGER.debug("Restored setting %s = %s", key, value)
                else:
                    _LOGGER.warning("Failed to restore setting %s", key)
        
        # Restore schedule if requested
        if restore_schedule and "schedule" in backup_data:
            for key, value in backup_data["schedule"].items():
                total_count += 1
                if await coordinator.async_write_register(key, value):
                    success_count += 1
                    _LOGGER.debug("Restored schedule %s = %s", key, value)
                else:
                    _LOGGER.warning("Failed to restore schedule %s", key)
        
        # Restore alarm settings
        if "alarms" in backup_data:
            for key, value in backup_data["alarms"].items():
                total_count += 1
                if await coordinator.async_write_register(key, value):
                    success_count += 1
                    _LOGGER.debug("Restored alarm setting %s = %s", key, value)
                else:
                    _LOGGER.warning("Failed to restore alarm setting %s", key)
        
        _LOGGER.info("Settings restore completed: %d/%d successful", success_count, total_count)

    async def async_calibrate_sensors(call: ServiceCall) -> None:
        """Calibrate temperature sensors service."""
        outside_offset = call.data.get("outside_offset")
        supply_offset = call.data.get("supply_offset")
        exhaust_offset = call.data.get("exhaust_offset")
        
        success_count = 0
        total_count = 0
        
        calibration_registers = {
            "outside_offset": "sensor_calibration_outside",
            "supply_offset": "sensor_calibration_supply", 
            "exhaust_offset": "sensor_calibration_extract",
        }
        
        offsets = {
            "outside_offset": outside_offset,
            "supply_offset": supply_offset,
            "exhaust_offset": exhaust_offset,
        }
        
        for offset_name, offset_value in offsets.items():
            if offset_value is not None:
                total_count += 1
                register = calibration_registers[offset_name]
                # Convert to register format (0.1°C resolution)
                reg_value = int(offset_value * 10)
                
                if await coordinator.async_write_register(register, reg_value):
                    success_count += 1
                    _LOGGER.info("Set %s calibration to %s°C", offset_name.replace("_offset", ""), offset_value)
                else:
                    _LOGGER.error("Failed to set %s calibration", offset_name)
        
        if success_count > 0:
            _LOGGER.info("Sensor calibration completed: %d/%d successful", success_count, total_count)
        else:
            _LOGGER.warning("No sensor calibrations were applied")

    # Register all services
    services = [
        ("set_mode", async_set_mode, SERVICE_SET_MODE_SCHEMA),
        ("set_special_mode", async_set_special_mode, SERVICE_SET_SPECIAL_MODE_SCHEMA),
        ("set_temperature", async_set_temperature, SERVICE_SET_TEMPERATURE_SCHEMA),
        ("set_fan_speed", async_set_fan_speed, SERVICE_SET_FAN_SPEED_SCHEMA),
        ("control_bypass", async_control_bypass, SERVICE_CONTROL_BYPASS_SCHEMA),
        ("control_gwc", async_control_gwc, SERVICE_CONTROL_GWC_SCHEMA),
        ("reset_alarms", async_reset_alarms, SERVICE_RESET_ALARMS_SCHEMA),
        ("set_schedule", async_set_schedule, SERVICE_SET_SCHEDULE_SCHEMA),
        ("rescan_device", async_rescan_device, SERVICE_RESCAN_DEVICE_SCHEMA),
        ("get_diagnostic_info", async_get_diagnostic_info, SERVICE_GET_DIAGNOSTIC_INFO_SCHEMA),
        ("backup_settings", async_backup_settings, SERVICE_BACKUP_SETTINGS_SCHEMA),
        ("restore_settings", async_restore_settings, SERVICE_RESTORE_SETTINGS_SCHEMA),
        ("calibrate_sensors", async_calibrate_sensors, SERVICE_CALIBRATE_SENSORS_SCHEMA),
    ]
    
    for service_name, service_func, service_schema in services:
        hass.services.async_register(DOMAIN, service_name, service_func, service_schema)
    
    _LOGGER.info("Registered %d enhanced services", len(services))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading ThesslaGreen Modbus integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Shutdown coordinator gracefully
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        if hasattr(coordinator, "async_shutdown"):
            await coordinator.async_shutdown()
        
        # Remove services if this was the last entry
        if not hass.data[DOMAIN]:
            # Remove all services
            services_to_remove = [
                "set_mode", "set_special_mode", "set_temperature", "set_fan_speed",
                "control_bypass", "control_gwc", "reset_alarms", "set_schedule",
                "rescan_device", "get_diagnostic_info", "backup_settings", 
                "restore_settings", "calibrate_sensors"
            ]
            
            for service_name in services_to_remove:
                if hass.services.has_service(DOMAIN, service_name):
                    hass.services.async_remove(DOMAIN, service_name)
            
            _LOGGER.info("Removed all ThesslaGreen services")
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)