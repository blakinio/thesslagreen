"""Button platform for ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .clock_sync import async_perform_clock_sync
from .const import (
    CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
)
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    coordinator: ThesslaGreenModbusCoordinator = entry.runtime_data  # pragma: no cover
    async_add_entities([SyncDeviceClockButton(coordinator, entry)])  # pragma: no cover


class SyncDeviceClockButton(ThesslaGreenEntity, ButtonEntity):
    """Button that synchronises the device RTC to HA local time."""

    _attr_translation_key = "sync_device_clock"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, "sync_device_clock", None)
        self._entry = entry

    @property
    def available(self) -> bool:
        """Return True whenever the coordinator is connected."""
        return self._coordinator_connected()

    async def async_press(self) -> None:
        """Handle button press: force-sync device clock to HA time."""
        opts = getattr(self._entry, "options", {}) or {}
        max_drift = int(
            opts.get(
                CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
                DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
            )
        )
        try:
            ok = await async_perform_clock_sync(
                self.coordinator,
                force=True,
                max_drift_seconds=max_drift,
                logger=_LOGGER,
            )
        except HomeAssistantError:
            raise
        except Exception as exc:
            raise HomeAssistantError(f"Clock sync failed: {exc}") from exc

        if not ok:
            raise HomeAssistantError("Failed to write device clock registers")
