"""ThesslaGreen Modbus integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

try:
    from homeassistant.const import CONF_NAME
except ModuleNotFoundError:  # pragma: no cover - allows local tooling without HA installed
    CONF_NAME = "name"

if TYPE_CHECKING:  # pragma: no cover
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import ThesslaGreenModbusCoordinator

from .const import (
    DEFAULT_NAME,
    DOMAIN,
)
from .const import PLATFORMS as PLATFORM_DOMAINS

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    ThesslaGreenConfigEntry = ConfigEntry[ThesslaGreenModbusCoordinator]


def _get_platforms() -> list[Any]:
    from ._setup import _get_platforms as _setup_get_platforms

    return _setup_get_platforms(tuple(PLATFORM_DOMAINS))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ThesslaGreen Modbus from a config entry.

    This hook is invoked by Home Assistant during config entry setup even
    though it appears unused within the integration code itself.
    """
    _LOGGER.debug(
        "Setting up ThesslaGreen Modbus integration for %s",
        getattr(entry, "title", entry.data.get(CONF_NAME, DEFAULT_NAME)),
    )
    from ._setup import (
        async_create_coordinator,
        async_migrate_entity_unique_ids,
        async_setup_mappings,
        async_setup_platforms,
        async_start_coordinator,
    )

    coordinator = await async_create_coordinator(hass, entry)
    if not await async_start_coordinator(hass, entry, coordinator):
        return False
    entry.runtime_data = coordinator

    await async_setup_mappings(hass)
    await async_migrate_entity_unique_ids(hass, entry, coordinator)
    await async_setup_platforms(hass, entry, PLATFORM_DOMAINS)

    from .clock_sync import ClockSyncManager

    _clock_sync_manager = ClockSyncManager(hass, coordinator, entry)
    _clock_sync_manager.attach()
    coordinator._clock_sync_manager = _clock_sync_manager

    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        from .services import async_setup_services

        await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    _LOGGER.info("ThesslaGreen Modbus integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Called by Home Assistant when a config entry is removed.  Kept for the
    callback interface despite not being referenced directly.
    """
    _LOGGER.debug("Unloading ThesslaGreen Modbus integration")

    # Unload platforms
    platforms = _get_platforms()
    unload_ok = cast(bool, await hass.config_entries.async_unload_platforms(entry, platforms))

    if unload_ok:
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
            await entry.runtime_data.async_shutdown()

        # Unload services when last entry is removed
        if not hass.config_entries.async_entries(DOMAIN):
            from .services import async_unload_services

            await async_unload_services(hass)

    _LOGGER.info("ThesslaGreen Modbus integration unloaded successfully")
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change.

    A full reload is used because most options (force_full_register_list,
    safe_scan, enable_device_scan, …) affect entity creation and register
    availability, so only a reload guarantees a clean, consistent state.
    Live-patching the coordinator and then reloading would cause a redundant
    refresh cycle, so we do the reload directly.
    """
    _LOGGER.debug("Reloading ThesslaGreen Modbus integration after options update")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    from ._migrations import async_migrate_entry as _async_migrate_entry

    return await _async_migrate_entry(hass, config_entry)
