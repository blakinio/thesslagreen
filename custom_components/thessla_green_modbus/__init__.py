"""ThesslaGreen Modbus integration for Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from importlib import import_module
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_RETRY,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_UART_SETTINGS,
    CONF_SKIP_MISSING_REGISTERS,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    CONF_DEEP_SCAN,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RETRY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SKIP_MISSING_REGISTERS,
    DEFAULT_SLAVE_ID,
    DEFAULT_TIMEOUT,
    DEFAULT_DEEP_SCAN,
    DOMAIN,
)
from .const import PLATFORMS as PLATFORM_DOMAINS
from .modbus_exceptions import ConnectionException, ModbusException

# Migration message for start-up logs
MIGRATION_MESSAGE = (
    "Register definitions now use JSON format by default; CSV files are deprecated "
    "and will be removed in a future release."
)

_LOGGER = logging.getLogger(__name__)

# Legacy default port used before version 2 when explicit port was optional
LEGACY_DEFAULT_PORT = 8899

# Legacy entity IDs that were replaced by the fan entity
LEGACY_FAN_ENTITY_IDS = [
    "number.rekuperator_predkosc",
    "number.rekuperator_speed",
]

_fan_migration_logged = False

# Supported platforms
# Build platform list compatible with both real Home Assistant enums and test stubs
PLATFORMS: list[Platform] = []
for domain in PLATFORM_DOMAINS:
    if hasattr(Platform, domain.upper()):
        PLATFORMS.append(getattr(Platform, domain.upper()))
    else:
        try:
            PLATFORMS.append(Platform(domain))
        except ValueError:
            _LOGGER.warning("Skipping unsupported platform: %s", domain)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ThesslaGreen Modbus from a config entry."""
    _LOGGER.info(MIGRATION_MESSAGE)
    _LOGGER.debug("Setting up ThesslaGreen Modbus integration for %s", entry.title)

    # Get configuration - support both new and legacy keys
    host = entry.data[CONF_HOST]
    port = entry.data.get(
        CONF_PORT, DEFAULT_PORT
    )  # Default to DEFAULT_PORT (502; legacy versions used 8899)

    # Try to get slave_id from multiple possible keys for compatibility
    slave_id = None
    if CONF_SLAVE_ID in entry.data:
        slave_id = entry.data[CONF_SLAVE_ID]
    elif "slave_id" in entry.data:
        slave_id = entry.data["slave_id"]
    elif "unit" in entry.data:
        slave_id = entry.data["unit"]  # Legacy support
    else:
        slave_id = DEFAULT_SLAVE_ID  # Use default if not found

    # Get name with fallback
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)

    # Get options with defaults
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    retry = entry.options.get(CONF_RETRY, DEFAULT_RETRY)
    force_full_register_list = entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
    scan_uart_settings = entry.options.get(CONF_SCAN_UART_SETTINGS, DEFAULT_SCAN_UART_SETTINGS)
    skip_missing_registers = entry.options.get(
        CONF_SKIP_MISSING_REGISTERS, DEFAULT_SKIP_MISSING_REGISTERS
    )
    deep_scan = entry.options.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN)

    _LOGGER.info(
        "Initializing ThesslaGreen device: %s at %s:%s (slave_id=%s, scan_interval=%ds)",
        name,
        host,
        port,
        slave_id,
        scan_interval,
    )

    # Create coordinator for managing device communication
    from .coordinator import ThesslaGreenModbusCoordinator

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
        scan_uart_settings=scan_uart_settings,
        deep_scan=deep_scan,
        skip_missing_registers=skip_missing_registers,
        entry=entry,
    )

    # Setup coordinator (this includes device scanning)
    try:
        await coordinator.async_setup()
    except (
        ConnectionException,
        ModbusException,
        asyncio.TimeoutError,
        OSError,
    ) as exc:
        _LOGGER.error("Failed to setup coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Unable to connect to device: {exc}") from exc

    # Perform first data update
    try:
        await coordinator.async_config_entry_first_refresh()
    except (
        ConnectionException,
        ModbusException,
        UpdateFailed,
        asyncio.TimeoutError,
        OSError,
    ) as exc:
        _LOGGER.error("Failed to perform initial data refresh: %s", exc)
        raise ConfigEntryNotReady(f"Unable to fetch initial data: {exc}") from exc

    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Clean up legacy entity IDs left from early versions
    await _async_cleanup_legacy_fan_entity(hass, host, port, slave_id)

    # Migrate entity unique IDs (replace ':' in host with '-')
    await _async_migrate_unique_ids(hass, entry)

    # Preload platform modules in the executor to avoid blocking the event loop
    for platform in PLATFORM_DOMAINS:
        try:
            await hass.async_add_executor_job(import_module, f".{platform}", __name__)
        except Exception:  # pragma: no cover - environment-dependent
            _LOGGER.debug("Could not preload platform %s", platform, exc_info=True)

    # Setup platforms
    _LOGGER.debug("Setting up platforms: %s", PLATFORMS)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except asyncio.CancelledError:
        _LOGGER.info("Platform setup cancelled for %s", PLATFORMS)
        raise

    # Setup services (only once for first entry)
    if len(hass.data[DOMAIN]) == 1:
        from .services import async_setup_services

        await async_setup_services(hass)

    # Setup entry update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("ThesslaGreen Modbus integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading ThesslaGreen Modbus integration")

    # Unload platforms
    unload_ok = cast(bool, await hass.config_entries.async_unload_platforms(entry, PLATFORMS))

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
            from .services import async_unload_services

            await async_unload_services(hass)

    _LOGGER.info("ThesslaGreen Modbus integration unloaded successfully")
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Updating options for ThesslaGreen Modbus integration")
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_cleanup_legacy_fan_entity(
    hass: HomeAssistant, host: str, port: int, slave_id: int
) -> None:
    """Remove or rename legacy fan-related entity IDs."""
    registry = er.async_get(hass)
    new_entity_id = "fan.rekuperator_fan"
    migrated = False

    if registry.async_get(new_entity_id):
        for old_entity_id in LEGACY_FAN_ENTITY_IDS:
            if registry.async_get(old_entity_id):
                registry.async_remove(old_entity_id)
                migrated = True
    else:
        for old_entity_id in LEGACY_FAN_ENTITY_IDS:
            if registry.async_get(old_entity_id):
                new_unique_id = f"{DOMAIN}_{host.replace(':', '-')}_{port}_{slave_id}_fan"
                registry.async_update_entity(
                    old_entity_id,
                    new_entity_id=new_entity_id,
                    new_unique_id=new_unique_id,
                )
                migrated = True
                break
        for old_entity_id in LEGACY_FAN_ENTITY_IDS:
            if registry.async_get(old_entity_id):
                registry.async_remove(old_entity_id)
                migrated = True

    global _fan_migration_logged
    if migrated and not _fan_migration_logged:
        _LOGGER.warning(
            "Legacy fan entity detected. Renamed to '%s'. Please update automations.",
            new_entity_id,
        )
        _fan_migration_logged = True


async def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entity unique IDs stored in the entity registry."""
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if ":" in reg_entry.unique_id:
            new_unique_id = reg_entry.unique_id.replace(":", "-")
            if new_unique_id != reg_entry.unique_id:
                _LOGGER.debug(
                    "Migrating unique_id for %s: %s -> %s",
                    reg_entry.entity_id,
                    reg_entry.unique_id,
                    new_unique_id,
                )
                registry.async_update_entity(reg_entry.entity_id, new_unique_id=new_unique_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating ThesslaGreen Modbus from version %s", config_entry.version)

    new_data = {**config_entry.data}
    new_options = {**config_entry.options}

    if config_entry.version == 1:
        # Migrate "unit" to CONF_SLAVE_ID if needed
        if "unit" in new_data and CONF_SLAVE_ID not in new_data:
            new_data[CONF_SLAVE_ID] = new_data["unit"]
            _LOGGER.info("Migrated 'unit' to '%s'", CONF_SLAVE_ID)

        # Ensure port is present; older versions relied on legacy default
        if CONF_PORT not in new_data:
            new_data[CONF_PORT] = LEGACY_DEFAULT_PORT
            _LOGGER.info("Added '%s' with legacy default %s", CONF_PORT, LEGACY_DEFAULT_PORT)

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

    # Build new unique ID replacing ':' in host with '-' to avoid separator conflicts
    host = new_data.get(CONF_HOST)
    port = new_data.get(CONF_PORT, LEGACY_DEFAULT_PORT)
    # Determine slave ID using same logic as setup
    if CONF_SLAVE_ID in new_data:
        slave_id = new_data[CONF_SLAVE_ID]
    elif "slave_id" in new_data:
        slave_id = new_data["slave_id"]
    elif "unit" in new_data:
        slave_id = new_data["unit"]
    else:
        slave_id = DEFAULT_SLAVE_ID

    unique_host = host.replace(":", "-") if host else host
    new_unique_id = f"{unique_host}:{port}:{slave_id}"

    hass.config_entries.async_update_entry(
        config_entry, data=new_data, options=new_options, unique_id=new_unique_id
    )

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
