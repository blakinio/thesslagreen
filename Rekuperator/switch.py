"""Switch platform for TeslaGreen Modbus Integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TeslaGreenCoordinator
from .entity import TeslaGreenEntity

SWITCH_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="bypass_control",
        name="Bypass letni",
        icon="mdi:valve",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TeslaGreen switches."""
    coordinator: TeslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TeslaGreenSwitch(coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    ]

    async_add_entities(entities)


class TeslaGreenSwitch(TeslaGreenEntity, SwitchEntity):
    """TeslaGreen switch entity."""

    def __init__(
        self,
        coordinator: TeslaGreenCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = description.name

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return bool(self.coordinator.data.get(self._key, 0))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.async_write_register(self._key, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.async_write_register(self._key, 0)
