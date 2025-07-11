"""Number platform for TeslaGreen Modbus Integration."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TeslaGreenCoordinator
from .entity import TeslaGreenEntity

NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="target_temperature",
        name="Temperatura docelowa",
        icon="mdi:thermometer",
        native_min_value=10,
        native_max_value=30,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    NumberEntityDescription(
        key="fan_speed_setting",
        name="Prędkość wentylatorów",
        icon="mdi:fan",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TeslaGreen number entities."""
    coordinator: TeslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TeslaGreenNumber(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    ]

    async_add_entities(entities)


class TeslaGreenNumber(TeslaGreenEntity, NumberEntity):
    """TeslaGreen number entity."""

    def __init__(
        self,
        coordinator: TeslaGreenCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = description.name

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
            
        # Temperature values are stored as int * 10 in Modbus
        if self._key == "target_temperature":
            return value / 10.0
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        # Temperature values need to be multiplied by 10 for Modbus
        if self._key == "target_temperature":
            modbus_value = int(value * 10)
        else:
            modbus_value = int(value)
            
        await self.coordinator.async_write_register(self._key, modbus_value)
