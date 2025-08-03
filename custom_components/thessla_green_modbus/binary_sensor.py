"""Binary sensor platform for ThesslaGreen Modbus integration."""
from __future__ import annotations

import logging
from typing import Any, Optional

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


class DeviceStatusDetector:
    """Smart device status detection using multiple indicators."""
    
    def __init__(self, coordinator_data: dict[str, Any]):
        self.data = coordinator_data
    
    def detect_device_status(self) -> Optional[bool]:
        """Detect device status using multiple methods with smart logic."""
        indicators = []
        
        # Method 1: Official panel register
        panel_mode = self.data.get("on_off_panel_mode")
        if panel_mode is not None:
            indicators.append(("panel_register", bool(panel_mode)))
        
        # Method 2: Fan power coil
        fan_power = self.data.get("power_supply_fans")
        if fan_power is not None:
            indicators.append(("fan_power", bool(fan_power)))
        
        # Method 3: Ventilation activity
        supply_pct = self.data.get("supply_percentage")
        if supply_pct is not None and supply_pct > 0:
            indicators.append(("ventilation_active", True))
        elif supply_pct is not None:
            indicators.append(("ventilation_active", False))
        
        # Method 4: Air flow measurement
        flows = [
            self.data.get("supply_flowrate"),
            self.data.get("exhaust_flowrate"),
            self.data.get("supply_air_flow"),
            self.data.get("exhaust_air_flow")
        ]
        active_flows = [f for f in flows if f is not None and f > 10]
        if active_flows:
            indicators.append(("air_flow", True))
        elif any(f is not None for f in flows):
            indicators.append(("air_flow", False))
        
        # Method 5: DAC voltages
        dac_supply = self.data.get("dac_supply")
        dac_exhaust = self.data.get("dac_exhaust")
        if (dac_supply is not None and dac_supply > 0.5) or (dac_exhaust is not None and dac_exhaust > 0.5):
            indicators.append(("dac_voltages", True))
        elif dac_supply is not None or dac_exhaust is not None:
            indicators.append(("dac_voltages", False))
        
        # Method 6: Constant Flow
        cf_active = self.data.get("constant_flow_active")
        if cf_active is not None:
            indicators.append(("constant_flow", bool(cf_active)))
        
        # Analyze indicators
        on_indicators = [name for name, status in indicators if status is True]
        off_indicators = [name for name, status in indicators if status is False]
        
        _LOGGER.debug("Device status indicators - ON: %s, OFF: %s", on_indicators, off_indicators)
        
        # Decision logic
        if on_indicators:
            # If any indicator shows activity, device is likely ON
            _LOGGER.info("Device detected as ON based on: %s", ", ".join(on_indicators))
            return True
        elif off_indicators:
            # If all indicators show no activity, device is OFF
            _LOGGER.info("Device detected as OFF - no activity detected")
            return False
        else:
            # Cannot determine
            _LOGGER.warning("Cannot determine device status - insufficient data")
            return None


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
    
    # SMART Device status - this replaces the simple on_off_panel_mode sensor
    entities.append(
        ThesslaGreenSmartDeviceStatus(coordinator)
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
    """Standard ThesslaGreen binary sensor."""

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


class ThesslaGreenSmartDeviceStatus(CoordinatorEntity, BinarySensorEntity):
    """Smart device status sensor using multiple indicators."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the smart device status sensor."""
        super().__init__(coordinator)
        self._attr_name = "Urządzenie włączone"
        self._attr_icon = "mdi:power"
        self._attr_device_class = BinarySensorDeviceClass.POWER
        
        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_device_status_smart"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the device is on using smart detection."""
        detector = DeviceStatusDetector(self.coordinator.data)
        return detector.detect_device_status()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for debugging."""
        data = self.coordinator.data
        return {
            "panel_register": data.get("on_off_panel_mode"),
            "fan_power_coil": data.get("power_supply_fans"),
            "supply_percentage": data.get("supply_percentage"),
            "exhaust_percentage": data.get("exhaust_percentage"),
            "supply_flowrate": data.get("supply_flowrate"),
            "exhaust_flowrate": data.get("exhaust_flowrate"),
            "dac_supply_voltage": data.get("dac_supply"),
            "dac_exhaust_voltage": data.get("dac_exhaust"),
            "constant_flow_active": data.get("constant_flow_active"),
            "operating_mode": data.get("mode"),
            "detection_method": "smart_multi_indicator",
        }