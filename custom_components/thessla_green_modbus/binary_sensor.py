"""Binary sensor platform for ThesslaGreen Modbus integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    """Set up binary sensor platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Coil registers (outputs)
    coil_regs = coordinator.available_registers.get("coil_registers", set())
    
    coil_sensors = [
        ("power_supply_fans", "Zasilanie wentylatorów", "mdi:fan", BinarySensorDeviceClass.RUNNING),
        ("bypass", "Bypass", "mdi:valve", None),
        ("gwc", "GWC", "mdi:heat-pump", BinarySensorDeviceClass.RUNNING),
        ("hood", "Okap", "mdi:kitchen", BinarySensorDeviceClass.RUNNING),
        ("heating_cable", "Kabel grzejny", "mdi:cable-data", BinarySensorDeviceClass.HEAT),
        ("work_permit", "Pozwolenie pracy", "mdi:check-circle", None),
        ("info", "Potwierdzenie pracy", "mdi:information", None),
        ("duct_water_heater_pump", "Pompa nagrzewnicy", "mdi:pump", BinarySensorDeviceClass.RUNNING),
    ]
    
    for sensor_key, name, icon, device_class in coil_sensors:
        if sensor_key in coil_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class
                )
            )
    
    # Discrete input registers
    discrete_regs = coordinator.available_registers.get("discrete_inputs", set())
    
    discrete_sensors = [
        ("expansion", "Moduł Expansion", "mdi:expansion-card", BinarySensorDeviceClass.CONNECTIVITY),
        ("duct_heater_protection", "Zabezpieczenie nagrzewnicy", "mdi:shield-alert", BinarySensorDeviceClass.SAFETY),
        ("dp_ahu_filter_overflow", "Przepełnienie filtra", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM),
        ("dp_duct_filter_overflow", "Przepełnienie filtra kanałowego", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM),
        ("ahu_filter_protection", "Zabezpieczenie FPX", "mdi:shield-alert", BinarySensorDeviceClass.SAFETY),
        ("hood_input", "Wejście okap", "mdi:kitchen", None),
        ("contamination_sensor", "Czujnik jakości powietrza", "mdi:air-filter", None),
        ("airing_sensor", "Czujnik wilgotności", "mdi:water-percent", BinarySensorDeviceClass.MOISTURE),
        ("airing_switch", "Przełącznik wietrzenia", "mdi:toggle-switch", None),
        ("fireplace", "Kominek", "mdi:fireplace", None),
        ("fire_alarm", "Alarm pożarowy", "mdi:fire-alert", BinarySensorDeviceClass.SAFETY),
        ("empty_house", "Pusty dom", "mdi:home-minus", None),
        ("airing_mini", "Wietrzenie AirS", "mdi:fan-auto", None),
        ("fan_speed_1", "1 bieg AirS", "mdi:fan-speed-1", None),
        ("fan_speed_2", "2 bieg AirS", "mdi:fan-speed-2", None),
        ("fan_speed_3", "3 bieg AirS", "mdi:fan-speed-3", None),
    ]
    
    for sensor_key, name, icon, device_class in discrete_sensors:
        if sensor_key in discrete_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class
                )
            )
    
    # System status from input/holding registers
    input_regs = coordinator.available_registers.get("input_registers", set())
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # Constant Flow status
    if "constant_flow_active" in input_regs:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator, "constant_flow_active", "Constant Flow", "mdi:fan-auto", BinarySensorDeviceClass.RUNNING
            )
        )
    
    # Water removal status
    if "water_removal_active" in input_regs:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator, "water_removal_active", "HEWR", "mdi:water-pump", BinarySensorDeviceClass.RUNNING
            )
        )
    
    # FPX status
    if "antifreeze_mode" in holding_regs:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator, "antifreeze_mode", "System FPX", "mdi:snowflake-alert", BinarySensorDeviceClass.RUNNING
            )
        )
    
    # GWC regeneration
    if "gwc_regen_flag" in holding_regs:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator, "gwc_regen_flag", "Regeneracja GWC", "mdi:refresh", BinarySensorDeviceClass.RUNNING
            )
        )
    
    # Device on/off status
    if "on_off_panel_mode" in holding_regs:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator, "on_off_panel_mode", "Urządzenie włączone", "mdi:power", BinarySensorDeviceClass.POWER
            )
        )
    
    # Alarm sensors
    alarm_sensors = [
        ("alarm_flag", "Alarmy ostrzeżeń (E)", "mdi:alert", BinarySensorDeviceClass.PROBLEM),
        ("error_flag", "Alarmy błędów (S)", "mdi:alert-circle", BinarySensorDeviceClass.PROBLEM),
    ]
    
    for sensor_key, name, icon, device_class in alarm_sensors:
        if sensor_key in holding_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class
                )
            )

    _LOGGER.debug("Adding %d binary sensor entities", len(entities))
    async_add_entities(entities)


class ThesslaGreenBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """ThesslaGreen binary sensor."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        sensor_key: str,
        name: str,
        icon: str,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class
        
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
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.data.get(self._sensor_key)
        if value is None:
            return None
        return bool(value)