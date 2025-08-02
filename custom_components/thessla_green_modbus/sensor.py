"""Sensor platform for ThesslaGreen Modbus integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    available_regs = coordinator.available_registers.get("input_registers", set())

    # Temperature sensors
    temp_sensors = [
        ("outside_temperature", "Temperatura zewnętrzna", "mdi:thermometer"),
        ("supply_temperature", "Temperatura nawiewu", "mdi:thermometer-lines"),
        ("exhaust_temperature", "Temperatura wywiewu", "mdi:thermometer-lines"),
        ("fpx_temperature", "Temperatura FPX", "mdi:thermometer-alert"),
        ("duct_supply_temperature", "Temperatura kanałowa", "mdi:thermometer-lines"),
        ("gwc_temperature", "Temperatura GWC", "mdi:thermometer-chevron-down"),
        ("ambient_temperature", "Temperatura otoczenia", "mdi:home-thermometer"),
    ]
    
    for sensor_key, name, icon in temp_sensors:
        if sensor_key in available_regs:
            entities.append(
                ThesslaGreenTemperatureSensor(
                    coordinator, sensor_key, name, icon
                )
            )

    # Flow sensors
    flow_sensors = [
        ("supply_flowrate", "Przepływ nawiewu", "mdi:fan", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("exhaust_flowrate", "Przepływ wywiewu", "mdi:fan", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("supply_air_flow", "Strumień nawiewu CF", "mdi:fan-speed-1", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("exhaust_air_flow", "Strumień wywiewu CF", "mdi:fan-speed-1", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
    ]
    
    for sensor_key, name, icon, unit in flow_sensors:
        if sensor_key in available_regs:
            entities.append(
                ThesslaGreenFlowSensor(
                    coordinator, sensor_key, name, icon, unit
                )
            )

    # Percentage sensors
    percentage_sensors = [
        ("supply_percentage", "Intensywność nawiewu", "mdi:gauge"),
        ("exhaust_percentage", "Intensywność wywiewu", "mdi:gauge"),
        ("min_percentage", "Minimalna intensywność", "mdi:gauge-low"),
        ("max_percentage", "Maksymalna intensywność", "mdi:gauge-full"),
    ]
    
    for sensor_key, name, icon in percentage_sensors:
        if sensor_key in available_regs:
            entities.append(
                ThesslaGreenPercentageSensor(
                    coordinator, sensor_key, name, icon
                )
            )

    # Voltage sensors (DAC outputs)
    voltage_sensors = [
        ("dac_supply", "Napięcie wentylatora nawiewnego", "mdi:flash"),
        ("dac_exhaust", "Napięcie wentylatora wywiewnego", "mdi:flash"),
        ("dac_heater", "Napięcie nagrzewnicy", "mdi:flash"),
        ("dac_cooler", "Napięcie chłodnicy", "mdi:flash"),
    ]
    
    for sensor_key, name, icon in voltage_sensors:
        if sensor_key in available_regs:
            entities.append(
                ThesslaGreenVoltageSensor(
                    coordinator, sensor_key, name, icon
                )
            )

    # System status sensors
    if "constant_flow_active" in available_regs:
        entities.append(
            ThesslaGreenStatusSensor(
                coordinator, "constant_flow_active", "Status Constant Flow", "mdi:fan-auto"
            )
        )

    if "water_removal_active" in available_regs:
        entities.append(
            ThesslaGreenStatusSensor(
                coordinator, "water_removal_active", "Status HEWR", "mdi:water-pump"
            )
        )

    # Firmware version
    if "firmware_major" in available_regs:
        entities.append(
            ThesslaGreenFirmwareSensor(coordinator)
        )

    # Serial number
    if all(f"serial_number_{i}" in available_regs for i in range(1, 7)):
        entities.append(
            ThesslaGreenSerialSensor(coordinator)
        )

    _LOGGER.debug("Adding %d sensor entities", len(entities))
    async_add_entities(entities)


class ThesslaGreenSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for ThesslaGreen sensors."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        sensor_key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._attr_name = name
        self._attr_icon = icon
        
        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{sensor_key}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._sensor_key)


class ThesslaGreenTemperatureSensor(ThesslaGreenSensorBase):
    """Temperature sensor for ThesslaGreen."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        sensor_key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, sensor_key, name, icon)
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_suggested_display_precision = 1


class ThesslaGreenFlowSensor(ThesslaGreenSensorBase):
    """Flow sensor for ThesslaGreen."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        sensor_key: str,
        name: str,
        icon: str,
        unit: str,
    ) -> None:
        """Initialize the flow sensor."""
        super().__init__(coordinator, sensor_key, name, icon)
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = unit
        self._attr_suggested_display_precision = 0


class ThesslaGreenPercentageSensor(ThesslaGreenSensorBase):
    """Percentage sensor for ThesslaGreen."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        sensor_key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the percentage sensor."""
        super().__init__(coordinator, sensor_key, name, icon)
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_suggested_display_precision = 0


class ThesslaGreenVoltageSensor(ThesslaGreenSensorBase):
    """Voltage sensor for ThesslaGreen."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        sensor_key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the voltage sensor."""
        super().__init__(coordinator, sensor_key, name, icon)
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_suggested_display_precision = 2


class ThesslaGreenStatusSensor(ThesslaGreenSensorBase):
    """Status sensor for ThesslaGreen."""

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self._sensor_key)
        if value is None:
            return "unknown"
        return "aktywny" if value else "nieaktywny"


class ThesslaGreenFirmwareSensor(ThesslaGreenSensorBase):
    """Firmware version sensor."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the firmware sensor."""
        super().__init__(coordinator, "firmware", "Wersja firmware", "mdi:chip")

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        major = self.coordinator.data.get("firmware_major")
        minor = self.coordinator.data.get("firmware_minor")
        patch = self.coordinator.data.get("firmware_patch")
        
        if major is not None and minor is not None:
            if patch is not None:
                return f"{major}.{minor}.{patch}"
            return f"{major}.{minor}"
        return None


class ThesslaGreenSerialSensor(ThesslaGreenSensorBase):
    """Serial number sensor."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the serial sensor."""
        super().__init__(coordinator, "serial_number", "Numer seryjny", "mdi:barcode")

    @property
    def native_value(self) -> str | None:
        """Return the serial number."""
        serial_parts = []
        for i in range(1, 7):
            part = self.coordinator.data.get(f"serial_number_{i}")
            if part is not None:
                serial_parts.append(f"{part:04x}")
            else:
                return None
        
        if len(serial_parts) == 6:
            return f"S/N: {serial_parts[0]}{serial_parts[1]} {serial_parts[2]}{serial_parts[3]} {serial_parts[4]}{serial_parts[5]}"
        return None