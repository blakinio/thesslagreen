"""Binary sensor platform for TeslaGreen Modbus Integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TeslaGreenCoordinator
from .entity import TeslaGreenEntity

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="system_status",
        name="Status systemu",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:check-circle",
    ),
    BinarySensorEntityDescription(
        key="filter_status",
        name="Stan filtra",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:air-filter",
    ),
    BinarySensorEntityDescription(
        key="bypass_status",
        name="Status bypass",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve-open",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TeslaGreen binary sensors."""
    coordinator: TeslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TeslaGreenBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class TeslaGreenBinarySensor(TeslaGreenEntity, BinarySensorEntity):
    """TeslaGreen binary sensor entity."""

    def __init__(
        self,
        coordinator: TeslaGreenCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = description.name

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        return bool(value)
