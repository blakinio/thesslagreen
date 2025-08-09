"""POPRAWIONY ThesslaGreen Modbus Integration for Home Assistant.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
Integracja zawiera wszystkie rejestry z pliku MODBUS_USER_AirPack_Home_08.2021.01 bez wyjątku
FIX: Poprawiony import coordinator, dodane diagnostics platform
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    CONF_RETRY,
    CONF_SCAN_INTERVAL,
    CONF_FORCE_FULL_REGISTER_LIST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    MANUFACTURER,
    MODEL,
)
from .coordinator import ThesslaGreenModbusCoordinator  # POPRAWKA: Poprawiony import
from .services import async_setup_services, async_unload_services  # POPRAWKA: Import serwisów

_LOGGER = logging.getLogger(__name__)

# Define platforms this integration supports - POPRAWKA: Dodane diagnostics
PLATFORMS_TO_SETUP = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.DIAGNOSTICS,  # POPRAWKA: Dodane diagnostics platform
]


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
        entry=entry,
    )
    
    # Setup coordinator (this includes device scanning)
    try:
        await coordinator.async_setup()
    except Exception as exc:
        _LOGGER.error("Failed to setup coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Unable to connect to device: {exc}") from exc
    
    # Perform first data update
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as exc:
        _LOGGER.error("Failed to perform initial data refresh: %s", exc)
        raise ConfigEntryNotReady(f"Unable to fetch initial data: {exc}") from exc
    
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS_TO_SETUP)
    
    # Setup services (only once for first entry)
    if len(hass.data[DOMAIN]) == 1:
        await async_setup_services(hass)
    
    # Setup entry update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    _LOGGER.info("ThesslaGreen Modbus integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading ThesslaGreen Modbus integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS_TO_SETUP)
    
    if unload_ok:
        # Shutdown coordinator
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()
        
        # Remove from hass data
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Clean up domain data if no more entries
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            # Unload services when last entry is removed
            await async_unload_services(hass)
    
    _LOGGER.info("ThesslaGreen Modbus integration unloaded successfully")
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Updating options for ThesslaGreen Modbus integration")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating ThesslaGreen Modbus from version %s", config_entry.version)
    
    if config_entry.version == 1:
        # Migration from version 1 to 2
        new_data = {**config_entry.data}
        new_options = {**config_entry.options}
        
        # Add new fields with defaults if missing
        if CONF_SCAN_INTERVAL not in new_options:
            new_options[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL
        if CONF_TIMEOUT not in new_options:
            new_options[CONF_TIMEOUT] = DEFAULT_TIMEOUT
        if CONF_RETRY not in new_options:
            new_options[CONF_RETRY] = DEFAULT_RETRY
        if CONF_FORCE_FULL_REGISTER_LIST not in new_options:
            new_options[CONF_FORCE_FULL_REGISTER_LIST] = False
        
        config_entry.version = 2
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options
        )
    
    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True