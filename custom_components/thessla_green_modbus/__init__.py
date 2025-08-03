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