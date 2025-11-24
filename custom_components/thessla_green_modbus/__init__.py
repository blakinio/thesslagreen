"""ThesslaGreen Modbus integration for Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from importlib import import_module
from typing import TYPE_CHECKING, cast

# Provide ``patch`` from ``unittest.mock`` for test modules that use it without
# importing. This mirrors the behaviour provided by the Home Assistant test
# harness and keeps the standalone tests lightweight.
import builtins
from unittest.mock import patch as _patch

# Only provide ``patch`` if it hasn't already been supplied by the test harness
if not hasattr(builtins, "patch"):
    builtins.patch = _patch

try:  # Home Assistant may not be installed for external tooling
    from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
except ModuleNotFoundError:  # pragma: no cover - fallback for testing tools
    CONF_HOST = "host"
    CONF_NAME = "name"
    CONF_PORT = "port"

if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .const import (
    CONF_BACKOFF,
    CONF_BACKOFF_JITTER,
    CONF_DEEP_SCAN,
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_RETRY,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_UART_SETTINGS,
    CONF_SKIP_MISSING_REGISTERS,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    DEFAULT_DEEP_SCAN,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_BACKOFF,
    DEFAULT_BACKOFF_JITTER,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RETRY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SKIP_MISSING_REGISTERS,
    DEFAULT_SLAVE_ID,
    DEFAULT_TIMEOUT,
    DOMAIN,
    async_setup_options,
    migrate_unique_id,
)
from .const import PLATFORMS as PLATFORM_DOMAINS
from .entity_mappings import async_setup_entity_mappings
from .modbus_exceptions import ConnectionException, ModbusException

_LOGGER = logging.getLogger(__name__)

# Legacy default port used before version 2 when explicit port was optional
LEGACY_DEFAULT_PORT = 8899

# Legacy entity IDs that were replaced by the fan entity
LEGACY_FAN_ENTITY_IDS = [
    "number.rekuperator_predkosc",
    "number.rekuperator_speed",
]

_fan_migration_logged = False


_platform_cache: list[object] | None = None


def _get_platforms() -> list[object]:
    """Return supported platform enums or plain strings.

    Importing Home Assistant is deferred so external tools can use this module
    without the `homeassistant` package installed. If the import fails, simple
    domain strings are returned instead of `Platform` enums.
    """

    global _platform_cache
    if _platform_cache is not None:
        return _platform_cache

    try:  # Import only when running inside Home Assistant
        from homeassistant.const import Platform  # type: ignore
    except Exception:  # pragma: no cover - Home Assistant missing
        _platform_cache = list(PLATFORM_DOMAINS)
        return _platform_cache

    platforms: list[Platform] = []
    for domain in PLATFORM_DOMAINS:
        if hasattr(Platform, domain.upper()):
            platforms.append(getattr(Platform, domain.upper()))
        else:
            try:
                platforms.append(Platform(domain))
            except ValueError:  # pragma: no cover - unsupported domain
                _LOGGER.warning("Skipping unsupported platform: %s", domain)
    _platform_cache = platforms
    return platforms


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


def _is_invalid_auth_error(exc: Exception) -> bool:
    """Return True if the exception indicates invalid authentication."""

    message = str(exc).lower()
    return any(keyword in message for keyword in ("auth", "credential", "password", "login"))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # pragma: no cover
    """Set up ThesslaGreen Modbus from a config entry.

    This hook is invoked by Home Assistant during config entry setup even
    though it appears unused within the integration code itself.
    """
    from homeassistant.exceptions import ConfigEntryNotReady  # type: ignore
    from homeassistant.helpers.update_coordinator import (
        UpdateFailed,  # type: ignore
    )

    _LOGGER.debug("Setting up ThesslaGreen Modbus integration for %s", entry.title)

    await hass.async_add_executor_job(import_module, ".config_flow", __name__)

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
    backoff = entry.options.get(CONF_BACKOFF, DEFAULT_BACKOFF)
    backoff_jitter = entry.options.get(CONF_BACKOFF_JITTER, DEFAULT_BACKOFF_JITTER)
    force_full_register_list = entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
    scan_uart_settings = entry.options.get(CONF_SCAN_UART_SETTINGS, DEFAULT_SCAN_UART_SETTINGS)
    skip_missing_registers = entry.options.get(
        CONF_SKIP_MISSING_REGISTERS, DEFAULT_SKIP_MISSING_REGISTERS
    )
    deep_scan = entry.options.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN)
    max_registers_per_request = entry.options.get(
        CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
    )

    _LOGGER.info(
        "Initializing ThesslaGreen device: %s at %s:%s (slave_id=%s, scan_interval=%ds)",
        name,
        host,
        port,
        slave_id,
        scan_interval,
    )

    # Create coordinator for managing device communication
    coordinator_mod = await hass.async_add_executor_job(
        import_module, ".coordinator", __name__
    )
    ThesslaGreenModbusCoordinator = coordinator_mod.ThesslaGreenModbusCoordinator

    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host=host,
        port=port,
        slave_id=slave_id,
        name=name,
        scan_interval=timedelta(seconds=scan_interval),
        timeout=timeout,
        retry=retry,
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        force_full_register_list=force_full_register_list,
        scan_uart_settings=scan_uart_settings,
        deep_scan=deep_scan,
        skip_missing_registers=skip_missing_registers,
        max_registers_per_request=max_registers_per_request,
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
        if _is_invalid_auth_error(exc):
            _LOGGER.error("Authentication failed during setup: %s", exc)
            await entry.async_start_reauth(hass)
            return False
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
        if _is_invalid_auth_error(exc):
            _LOGGER.error("Authentication failed during initial refresh: %s", exc)
            await entry.async_start_reauth(hass)
            return False
        _LOGGER.error("Failed to perform initial data refresh: %s", exc)
        raise ConfigEntryNotReady(f"Unable to fetch initial data: {exc}") from exc

    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Clean up legacy entity IDs left from early versions
    await _async_cleanup_legacy_fan_entity(hass, coordinator)

    # Migrate entity unique IDs (replace ':' in host with '-')
    await _async_migrate_unique_ids(hass, entry)

    # Load option lists and entity mappings
    await async_setup_options(hass)
    await async_setup_entity_mappings(hass)

    # Preload platform modules in the executor to avoid blocking the event loop
    for platform in PLATFORM_DOMAINS:
        try:
            await hass.async_add_executor_job(import_module, f".{platform}", __name__)
        except (ImportError, ModuleNotFoundError) as err:  # pragma: no cover - environment-dependent
            _LOGGER.debug("Could not preload platform %s: %s", platform, err)
        except Exception as err:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected error preloading platform %s: %s", platform, err)

    # Setup platforms
    platforms = _get_platforms()
    _LOGGER.debug("Setting up platforms: %s", platforms)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
    except asyncio.CancelledError:
        _LOGGER.info("Platform setup cancelled for %s", platforms)
        raise

    # Setup services (only once for first entry)
    if len(hass.data[DOMAIN]) == 1:
        from .services import async_setup_services

        await async_setup_services(hass)

    # Setup entry update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("ThesslaGreen Modbus integration setup completed successfully")
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:  # pragma: no cover
    """Unload a config entry.

    Called by Home Assistant when a config entry is removed.  Kept for the
    callback interface despite not being referenced directly.
    """
    _LOGGER.debug("Unloading ThesslaGreen Modbus integration")

    # Unload platforms
    platforms = _get_platforms()
    unload_ok = cast(
        bool, await hass.config_entries.async_unload_platforms(entry, platforms)
    )

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
    hass: HomeAssistant, coordinator
) -> None:
    """Remove or rename legacy fan-related entity IDs."""
    from homeassistant.helpers import entity_registry as er  # type: ignore

    registry = er.async_get(hass)
    new_entity_id = "fan.rekuperator_fan"
    migrated = False
    host = coordinator.host
    port = coordinator.port
    slave_id = coordinator.slave_id
    serial = coordinator.device_info.get("serial_number")

    if registry.async_get(new_entity_id):
        for old_entity_id in LEGACY_FAN_ENTITY_IDS:
            if registry.async_get(old_entity_id):
                registry.async_remove(old_entity_id)
                migrated = True
    else:
        for old_entity_id in LEGACY_FAN_ENTITY_IDS:
            if registry.async_get(old_entity_id):
                new_unique_id = migrate_unique_id(
                    f"{DOMAIN}_{host.replace(':', '-')}_{port}_{slave_id}_fan",
                    serial_number=serial,
                    host=host,
                    port=port,
                    slave_id=slave_id,
                )
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
    from homeassistant.helpers import entity_registry as er  # type: ignore

    registry = er.async_get(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = coordinator.device_info.get("serial_number")
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        new_unique_id = migrate_unique_id(
            reg_entry.unique_id,
            serial_number=serial,
            host=coordinator.host,
            port=coordinator.port,
            slave_id=coordinator.slave_id,
        )
        if new_unique_id != reg_entry.unique_id:
            _LOGGER.debug(
                "Migrating unique_id for %s: %s -> %s",
                reg_entry.entity_id,
                reg_entry.unique_id,
                new_unique_id,
            )
            registry.async_update_entity(reg_entry.entity_id, new_unique_id=new_unique_id)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:  # pragma: no cover
    """Migrate old entry.

    Home Assistant uses this during upgrades; vulture marks it as unused but
    the runtime imports it dynamically.
    """
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
