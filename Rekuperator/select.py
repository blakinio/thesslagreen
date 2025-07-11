"""Select platform for TeslaGreen Modbus Integration."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TeslaGreenCoordinator
from .entity import TeslaGreenEntity

SELECT_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="mode_selection",
        name="Tryb pracy",
        icon="mdi:cog",
        options=["Wyłączony", "Wentylacja", "Auto", "Nocny", "Boost", "Nieobecność"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TeslaGreen select entities."""
    coordinator: TeslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TeslaGreenSelect(coordinator, description)
        for description in SELECT_DESCRIPTIONS
    ]

    async_add_entities(entities)


class TeslaGreenSelect(TeslaGreenEntity, SelectEntity):
    """TeslaGreen select entity."""

    def __init__(
        self,
        coordinator: TeslaGreenCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = description.name

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        value = self.coordinator.data.get(self._key, 0)
        
        if self._key == "mode_selection":
            mode_map = {
                0: "Wyłączony",
                1: "Wentylacja",
                2: "Auto",
                3: "Nocny",
                4: "Boost",
                5: "Nieobecność",
            }
            return mode_map.get(value, "Wyłączony")
        
        return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if self._key == "mode_selection":
            option_map = {
                "Wyłączony": 0,
                "Wentylacja": 1,
                "Auto": 2,
                "Nocny": 3,
                "Boost": 4,
                "Nieobecność": 5,
            }
            if option in option_map:
                await self.coordinator.async_write_register(self._key, option_map[option])
