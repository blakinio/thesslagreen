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
from typing import TYPE_CHECKING, cast

from homeassistant.const import CONF_NAME

if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import ThesslaGreenModbusCoordinator

from ._migrations import async_migrate_entity_ids as _async_migrate_entity_ids
from ._migrations import async_migrate_entry as _async_migrate_entry
from ._migrations import async_migrate_unique_ids as _async_migrate_unique_ids
from ._setup import (
    _apply_log_level as _setup_apply_log_level,
)
from ._setup import (
    _get_platforms as _setup_get_platforms,
)
from ._setup import (
    async_create_coordinator as _async_create_coordinator,
)
from ._setup import (
    async_setup_mappings as _async_setup_mappings,
)
from ._setup import (
    async_setup_platforms as _async_setup_platforms,
)
from ._setup import (
    async_start_coordinator as _async_start_coordinator,
)
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

if TYPE_CHECKING:  # pragma: no cover - typing only
    ThesslaGreenConfigEntry = ConfigEntry[ThesslaGreenModbusCoordinator]


_get_platforms = partial(_setup_get_platforms, PLATFORM_DOMAINS)
_apply_log_level = _setup_apply_log_level


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # pragma: no cover - defensive
    """Set up ThesslaGreen Modbus from a config entry.

    This hook is invoked by Home Assistant during config entry setup even
    though it appears unused within the integration code itself.
    """
    _LOGGER.debug(
        "Setting up ThesslaGreen Modbus integration for %s",
        getattr(entry, "title", entry.data.get(CONF_NAME, DEFAULT_NAME)),
    )

    coordinator = await _async_create_coordinator(hass, entry)
    if not await _async_start_coordinator(hass, entry, coordinator):
        return False
    entry.runtime_data = coordinator

    await _async_migrate_unique_ids(hass, entry)
    await _async_migrate_entity_ids(hass, entry)
    await _async_setup_mappings(hass)
    await _async_setup_platforms(hass, entry, PLATFORM_DOMAINS)

    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        from .services import async_setup_services

        await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    _LOGGER.info("ThesslaGreen Modbus integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # pragma: no cover - defensive
    """Unload a config entry.

    Called by Home Assistant when a config entry is removed.  Kept for the
    callback interface despite not being referenced directly.
    """
    _LOGGER.debug("Unloading ThesslaGreen Modbus integration")

    # Unload platforms
    platforms = _get_platforms()
    unload_ok = cast(bool, await hass.config_entries.async_unload_platforms(entry, platforms))

    if unload_ok:
        # Shutdown coordinator (runtime_data may not be set if setup failed early)
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is not None:
            await coordinator.async_shutdown()

        # Unload services when last entry is removed
        if not hass.config_entries.async_entries(DOMAIN):
            from .services import async_unload_services

            await async_unload_services(hass)

    _LOGGER.info("ThesslaGreen Modbus integration unloaded successfully")
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:  # pragma: no cover - defensive
    """Update options."""
    _LOGGER.debug("Updating options for ThesslaGreen Modbus integration")

    coordinator = getattr(entry, "runtime_data", None)
    if coordinator:
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
        ):  # pragma: no cover - defensive
            _LOGGER.debug("Failed to recompute register groups after option update", exc_info=True)

        await coordinator.async_request_refresh()

    await hass.config_entries.async_reload(entry.entry_id)

async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:  # pragma: no cover - defensive
    """Migrate old entry."""
    return await _async_migrate_entry(hass, config_entry)
