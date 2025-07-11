"""Sensor platform for TeslaGreen Modbus Integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE, CONCENTRATION_PARTS_PER_MILLION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TeslaGreenCoordinator
from .entity import TeslaGreenEntity

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temp_supply",
        name="Temperatura powietrza doprowadzanego",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer-plus",
    ),
    SensorEntityDescription(
        key="temp_extract",
        name="Temperatura powietrza wyciąganego",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer-minus",
    ),
    SensorEntityDescription(
        key="temp_outdoor",
        name="Temperatura zewnętrzna",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="temp_exhaust",
        name="Temperatura powietrza wywiewanego",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer-low",
    ),
    SensorEntityDescription(
        key="fan_supply_speed",
        name="Prędkość wentylatora nawiewu",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="RPM",
        icon="mdi:fan",
    ),
    SensorEntityDescription(
        key="fan_extract_speed",
        name="Prędkość wentylatora wyciągu",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="RPM",
        icon="mdi:fan",
    ),
    SensorEntityDescription(
        key="co2_level",
        name="Poziom CO2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:molecule-co2",
    ),
    SensorEntityDescription(
        key="humidity",
        name="Wilgotność",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="air_quality_index",
        name="Indeks jakości powietrza",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TeslaGreen sensors."""
    coordinator: TeslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TeslaGreenSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class TeslaGreenSensor(TeslaGreenEntity, SensorEntity):
    """TeslaGreen sensor entity."""

    def __init__(
        self,
        coordinator: TeslaGreenCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = description.name

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._key)
