"""ThesslaGreen Modbus integration for Home Assistant."""

from __future__ import annotations

import sys as _sys

if _sys.version_info < (3, 13):  # noqa: UP036
    raise RuntimeError(
        f"ThesslaGreen Modbus requires Python 3.13+; "
        f"running on {_sys.version_info.major}.{_sys.version_info.minor}. "
        "Update Home Assistant to 2026.1.0+ which ships Python 3.13."
    )

import logging
from datetime import timedelta
from functools import partial
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
    CONF_LOG_LEVEL,
    CONF_SAFE_SCAN,
    CONF_SCAN_INTERVAL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_NAME,
    DEFAULT_SAFE_SCAN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .const import PLATFORMS as PLATFORM_DOMAINS

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    ThesslaGreenConfigEntry = ConfigEntry[ThesslaGreenModbusCoordinator]


def _get_platforms() -> list[Any]:
    from ._setup import _get_platforms as _setup_get_platforms

    return partial(_setup_get_platforms, PLATFORM_DOMAINS)()


def _apply_log_level(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    base_logger = logging.getLogger(__package__ or DOMAIN)
    base_logger.setLevel(level)


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
    """Update options."""
    _LOGGER.debug("Updating options for ThesslaGreen Modbus integration")

    coordinator = entry.runtime_data
    if coordinator is not None:
        new_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        coordinator.scan_interval = new_interval
        try:
            coordinator.async_set_update_interval(timedelta(seconds=new_interval))
        except AttributeError:
            coordinator.update_interval = timedelta(seconds=new_interval)

        new_log_level = str(entry.options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL))
        _apply_log_level(new_log_level)

        coordinator.safe_scan = bool(entry.options.get(CONF_SAFE_SCAN, DEFAULT_SAFE_SCAN))
        try:
            coordinator._compute_register_groups()
        except (
            TypeError,
            ValueError,
            AttributeError,
            RuntimeError,
            OSError,
        ):
            _LOGGER.debug("Failed to recompute register groups after option update", exc_info=True)

        await coordinator.async_request_refresh()

    await hass.config_entries.async_reload(entry.entry_id)

async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate old entry."""
    from ._migrations import async_migrate_entry as _async_migrate_entry

    return await _async_migrate_entry(hass, config_entry)
