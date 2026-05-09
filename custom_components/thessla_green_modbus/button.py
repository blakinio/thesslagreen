"""Button platform for ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .clock_sync import async_sync_device_clock, clock_sync_options
from .const import (
    CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    device_unique_id_prefix,
)
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen button entities from config entry."""
    coordinator: ThesslaGreenModbusCoordinator = entry.runtime_data
    async_add_entities([ThesslaGreenSyncClockButton(coordinator, entry)], update_before_add=False)


class ThesslaGreenSyncClockButton(ButtonEntity):
    """Button that synchronises the device RTC to Home Assistant local time.

    Pressing this button always triggers a clock write regardless of whether
    automatic synchronisation is enabled in options.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "sync_device_clock"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-check"

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_device_info = coordinator.get_device_info()
        device_info = getattr(coordinator, "device_info", {}) or {}
        serial_number = device_info.get("serial_number")
        prefix = device_unique_id_prefix(
            serial_number,
            getattr(coordinator, "host", ""),
            getattr(coordinator, "port", 0),
        )
        slave_id = getattr(coordinator, "slave_id", 1)
        self._attr_unique_id = f"{prefix}_{slave_id}_sync_device_clock_button"

    @property
    def available(self) -> bool:
        """Button is available when coordinator has last succeeded."""
        return bool(getattr(self._coordinator, "last_update_success", False))

    async def async_press(self) -> None:
        """Write current local time to device RTC registers."""
        opts = clock_sync_options(self._entry.options)
        max_drift = int(
            opts.get(CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS, DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS)
        )
        now = dt_util.now().replace(tzinfo=None)
        _LOGGER.info("Manual device clock sync triggered via button")
        await async_sync_device_clock(
            self._coordinator,
            now,
            max_drift,
            raise_on_failure=True,
            entity_id=self.entity_id or "",
        )
