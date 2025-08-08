"""ThesslaGreen Modbus Integration for Home Assistant.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
Integracja zawiera wszystkie rejestry z pliku MODBUS_USER_AirPack_Home_08.2021.01 bez wyjątku
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    CONF_RETRY,
    CONF_FORCE_FULL_REGISTER_LIST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    MANUFACTURER,
    MODEL,
)
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Define platforms this integration supports
PLATFORMS_TO_SETUP = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.FAN, Platform.SELECT, Platform.NUMBER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ThesslaGreen Modbus from a config entry."""
    _LOGGER.debug("Setting up ThesslaGreen Modbus integration for %s", entry.title)
    
    # Get configuration
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave_id = entry.data[CONF_SLAVE_ID]
    name = entry.data[CONF_NAME]
    
    # Get options with defaults
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    retry = entry.options.get(CONF_RETRY, DEFAULT_RETRY)
    force_full_register_list = entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
    
    _LOGGER.info(
        "Initializing ThesslaGreen device: %s at %s:%s (slave_id=%s, scan_interval=%ds)",
        name, host, port, slave_id, scan_interval
    )
    
    # Create coordinator for managing device communication
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host=host,
        port=port,
        slave_id=slave_id,
        name=name,
        scan_interval=timedelta(seconds=scan_interval),
        timeout=timeout,
        retry=retry,
        force_full_register_list=force_full_register_list,
        entry_data=entry.data,
    )
    
    # Test initial connection and get device info
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed as err:
        _LOGGER.error("Authentication failed for %s: %s", name, err)
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except UpdateFailed as err:
        _LOGGER.error("Failed to connect to %s: %s", name, err)
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err
    except Exception as err:
        _LOGGER.error("Unexpected error setting up %s: %s", name, err, exc_info=True)
        raise ConfigEntryNotReady(f"Unexpected error: {err}") from err
    
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Setup device registry entry
    device_info = coordinator.get_device_info()
    _LOGGER.info(
        "Device setup complete: %s (firmware: %s, registers: %d, capabilities: %s)",
        device_info["name"],
        device_info.get("sw_version", "Unknown"),
        coordinator.get_register_count(),
        ", ".join(coordinator.get_capabilities_summary())
    )
    
    # Forward setup to platforms - only setup platforms that have available entities
    platforms_to_setup = []
    for platform in PLATFORMS_TO_SETUP:
        if coordinator.has_entities_for_platform(platform.value):
            platforms_to_setup.append(platform)
            _LOGGER.debug("Platform %s has available entities - will be setup", platform.value)
        else:
            _LOGGER.debug("Platform %s has no available entities - skipping", platform.value)
    
    if platforms_to_setup:
        await hass.config_entries.async_forward_entry_setups(entry, platforms_to_setup)
        _LOGGER.info("Setup complete for %d platforms: %s", len(platforms_to_setup), [p.value for p in platforms_to_setup])
    else:
        _LOGGER.warning("No platforms have available entities - check device connectivity")
    
    # Setup options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading ThesslaGreen Modbus integration for %s", entry.title)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if not coordinator:
        _LOGGER.warning("No coordinator found for entry %s during unload", entry.entry_id)
        return True
    
    # Determine which platforms are actually setup
    platforms_to_unload = []
    for platform in PLATFORMS_TO_SETUP:
        if coordinator.has_entities_for_platform(platform.value):
            platforms_to_unload.append(platform)
    
    # Unload platforms
    if platforms_to_unload:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms_to_unload)
        if not unload_ok:
            _LOGGER.warning("Failed to unload some platforms for %s", entry.title)
            return False
    
    # Cleanup coordinator
    try:
        await coordinator.async_shutdown()
    except Exception as err:
        _LOGGER.warning("Error during coordinator shutdown: %s", err)
    
    # Remove from hass data
    hass.data[DOMAIN].pop(entry.entry_id, None)
    
    _LOGGER.info("Successfully unloaded ThesslaGreen Modbus integration for %s", entry.title)
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Updating options for %s", entry.title)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if not coordinator:
        _LOGGER.warning("No coordinator found for entry %s during options update", entry.entry_id)
        return
    
    # Update coordinator settings
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    retry = entry.options.get(CONF_RETRY, DEFAULT_RETRY)
    force_full_register_list = entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
    
    # Update coordinator configuration
    await coordinator.async_update_options(
        scan_interval=timedelta(seconds=scan_interval),
        timeout=timeout,
        retry=retry,
        force_full_register_list=force_full_register_list,
    )
    
    _LOGGER.info(
        "Updated options for %s: scan_interval=%ds, timeout=%ds, retry=%d, force_full=%s",
        entry.title, scan_interval, timeout, retry, force_full_register_list
    )


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.debug("Reloading ThesslaGreen Modbus integration for %s", entry.title)
    
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)