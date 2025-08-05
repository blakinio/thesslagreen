"""Enhanced sensor platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ERROR_CODES, WARNING_CODES
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up enhanced sensor platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    available_regs = coordinator.available_registers.get("input_registers", set())

    # Enhanced Temperature sensors (HA 2025.7+ Compatible)
    temp_sensors = [
        ("outside_temperature", "Outside Temperature", "mdi:thermometer", "TZ1 - External air temperature"),
        ("supply_temperature", "Supply Temperature", "mdi:thermometer-lines", "TN1 - Supply air temperature after heat recovery"),
        ("exhaust_temperature", "Exhaust Temperature", "mdi:thermometer-lines", "TP - Exhaust air temperature"),
        ("fpx_temperature", "FPX Temperature", "mdi:thermometer-alert", "TZ2 - Post-heater temperature"),
        ("duct_supply_temperature", "Duct Temperature", "mdi:thermometer-lines", "TN2 - Supply duct temperature"),
        ("gwc_temperature", "GWC Temperature", "mdi:thermometer-chevron-down", "TZ3 - Ground Heat Exchanger temperature"),
        ("ambient_temperature", "Ambient Temperature", "mdi:home-thermometer", "TO - Room temperature"),
        ("gwc_inlet_temperature", "GWC Inlet Temperature", "mdi:thermometer-minus", "GWC inlet temperature"),
        ("gwc_outlet_temperature", "GWC Outlet Temperature", "mdi:thermometer-plus", "GWC outlet temperature"),
        ("bypass_inlet_temperature", "Bypass Inlet Temperature", "mdi:thermometer", "Bypass inlet temperature"),
        ("bypass_outlet_temperature", "Bypass Outlet Temperature", "mdi:thermometer", "Bypass outlet temperature"),
    ]
    
    for sensor_key, name, icon, description in temp_sensors:
        if sensor_key in available_regs:
            entities.append(
                ThesslaGreenTemperatureSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )

    # Enhanced Flow rate sensors (HA 2025.7+ Compatible)
    flow_sensors = [
        ("supply_flowrate", "Supply Flow Rate", "mdi:fan", "Current supply air flow rate", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("exhaust_flowrate", "Exhaust Flow Rate", "mdi:fan-auto", "Current exhaust air flow rate", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("supply_air_flow", "Supply Air Flow", "mdi:air-filter", "Supply air stream measurement", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("exhaust_air_flow", "Exhaust Air Flow", "mdi:air-filter", "Exhaust air stream measurement", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("constant_flow_supply", "CF Supply Flow", "mdi:chart-line", "Constant Flow supply measurement", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("constant_flow_exhaust", "CF Exhaust Flow", "mdi:chart-line", "Constant Flow exhaust measurement", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("constant_flow_supply_setpoint", "CF Supply Setpoint", "mdi:chart-line-stacked", "Constant Flow supply target", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
        ("constant_flow_exhaust_setpoint", "CF Exhaust Setpoint", "mdi:chart-line-stacked", "Constant Flow exhaust target", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
    ]
    
    for sensor_key, name, icon, description, unit in flow_sensors:
        if sensor_key in available_regs:
            entities.append(
                ThesslaGreenFlowSensor(
                    coordinator, sensor_key, name, icon, description, unit
                )
            )

    # Enhanced Performance sensors (HA 2025.7+ Compatible)
    performance_sensors = [
        ("supply_percentage", "Supply Intensity", "mdi:gauge", "Supply fan intensity percentage", PERCENTAGE),
        ("exhaust_percentage", "Exhaust Intensity", "mdi:gauge", "Exhaust fan intensity percentage", PERCENTAGE),
        ("heat_recovery_efficiency", "Heat Recovery Efficiency", "mdi:heat-pump", "Current heat recovery efficiency", PERCENTAGE),
        ("heating_efficiency", "Heating Efficiency", "mdi:radiator", "Heating system efficiency", PERCENTAGE),
        ("gwc_efficiency", "GWC Efficiency", "mdi:earth", "Ground Heat Exchanger efficiency", PERCENTAGE),
        ("bypass_position", "Bypass Position", "mdi:valve", "Current bypass damper position", PERCENTAGE),
        ("computed_effectiveness", "Heat Recovery Effectiveness", "mdi:calculator", "Computed heat recovery effectiveness", PERCENTAGE),
    ]
    
    for sensor_key, name, icon, description, unit in performance_sensors:
        if sensor_key in available_regs or sensor_key in coordinator.data:
            entities.append(
                ThesslaGreenPerformanceSensor(
                    coordinator, sensor_key, name, icon, description, unit
                )
            )

    # Enhanced System status sensors (HA 2025.7+ Compatible)
    status_sensors = [
        ("operating_hours", "Operating Hours", "mdi:clock-outline", "Total system operating hours", UnitOfTime.HOURS),
        ("filter_time_remaining", "Filter Time Remaining", "mdi:air-filter", "Days until filter replacement", UnitOfTime.DAYS),
        ("boost_time_remaining", "Boost Time Remaining", "mdi:timer", "Minutes remaining in boost mode", UnitOfTime.MINUTES),
        ("temporary_time_remaining", "Temporary Time Remaining", "mdi:timer-outline", "Minutes remaining in temporary mode", UnitOfTime.MINUTES),
        ("antifreeze_stage", "Antifreeze Stage", "mdi:snowflake-variant", "Current antifreeze protection stage", None),
    ]
    
    for sensor_key, name, icon, description, unit in status_sensors:
        if sensor_key in available_regs:
            entities.append(
                ThesslaGreenStatusSensor(
                    coordinator, sensor_key, name, icon, description, unit
                )
            )

    # Enhanced Power and Energy sensors (HA 2025.7+ New Features)
    power_energy_sensors = [
        ("actual_power_consumption", "Power Consumption", "mdi:flash", "Current power consumption", UnitOfPower.WATT),
        ("cumulative_power_consumption", "Energy Consumption", "mdi:flash", "Total energy consumption", UnitOfEnergy.KILO_WATT_HOUR),
        ("power_efficiency", "Power Efficiency", "mdi:leaf", "Power efficiency (W per % intensity)", "W/%"),
    ]
    
    for sensor_key, name, icon, description, unit in power_energy_sensors:
        if sensor_key in available_regs or sensor_key in coordinator.data:
            entities.append(
                ThesslaGreenPowerSensor(
                    coordinator, sensor_key, name, icon, description, unit
                )
            )

    # Enhanced Error and Warning sensors (HA 2025.7+ Compatible)
    if "error_code" in available_regs:
        entities.append(
            ThesslaGreenErrorSensor(coordinator, "error_code", "Error Code", "mdi:alert-circle")
        )
    
    if "warning_code" in available_regs:
        entities.append(
            ThesslaGreenErrorSensor(coordinator, "warning_code", "Warning Code", "mdi:alert")
        )

    # Enhanced Device information sensors (HA 2025.7+ Compatible)
    device_sensors = [
        ("firmware_version", "Firmware Version", "mdi:chip", "Device firmware version", None),
        ("device_serial", "Serial Number", "mdi:barcode", "Device serial number", None),
    ]
    
    for sensor_key, name, icon, description, unit in device_sensors:
        if sensor_key in available_regs:
            entities.append(
                ThesslaGreenDeviceSensor(
                    coordinator, sensor_key, name, icon, description, unit
                )
            )

    if entities:
        _LOGGER.debug("Adding %d enhanced sensor entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenBaseSensor(CoordinatorEntity, SensorEntity):
    """Enhanced base sensor for ThesslaGreen - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
    ) -> None:
        """Initialize the enhanced base sensor."""
        super().__init__(coordinator)
        self._key = key
        
        # Enhanced device info handling
        device_info = coordinator.data.get("device_info", {}) if coordinator.data else {}
        device_name = device_info.get("device_name", f"ThesslaGreen {coordinator.host}")
        
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"
        
        # Enhanced entity description for HA 2025.7+ - using SensorEntityDescription
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
        )
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "register_key": self._key,
            "description": getattr(self, '_attr_entity_description', ''),
        }
        
        # Add last update timestamp
        if hasattr(self.coordinator, 'last_update_success_time'):
            attributes["last_updated"] = self.coordinator.last_update_success_time.isoformat()
            
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self._key in self.coordinator.data
        )


class ThesslaGreenTemperatureSensor(ThesslaGreenBaseSensor):
    """Enhanced temperature sensor - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
    ) -> None:
        """Initialize the enhanced temperature sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Enhanced entity description for temperature sensors
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced temperature context (HA 2025.7+)
        temp_value = self.native_value
        if temp_value is not None:
            # Temperature category
            if temp_value < 0:
                attributes["temperature_category"] = "freezing"
            elif temp_value < 10:
                attributes["temperature_category"] = "cold"
            elif temp_value < 20:
                attributes["temperature_category"] = "cool"
            elif temp_value < 25:
                attributes["temperature_category"] = "comfortable"
            elif temp_value < 30:
                attributes["temperature_category"] = "warm"
            else:
                attributes["temperature_category"] = "hot"
        
        # Add related temperature comparisons
        if self._key == "outside_temperature":
            supply_temp = self.coordinator.data.get("supply_temperature")
            if supply_temp is not None and temp_value is not None:
                attributes["temperature_rise"] = round(supply_temp - temp_value, 1)
        
        elif self._key == "supply_temperature":
            outside_temp = self.coordinator.data.get("outside_temperature")
            exhaust_temp = self.coordinator.data.get("exhaust_temperature")
            if outside_temp is not None and temp_value is not None:
                attributes["heating_provided"] = round(temp_value - outside_temp, 1)
            if exhaust_temp is not None and temp_value is not None:
                attributes["heat_recovery_delta"] = round(temp_value - outside_temp, 1)
        
        return attributes


class ThesslaGreenFlowSensor(ThesslaGreenBaseSensor):
    """Enhanced flow rate sensor - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str,
    ) -> None:
        """Initialize the enhanced flow sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Enhanced entity description for flow sensors
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced flow context (HA 2025.7+)
        flow_value = self.native_value
        if flow_value is not None:
            # Flow rate category for typical home units
            if flow_value < 50:
                attributes["flow_category"] = "very_low"
            elif flow_value < 100:
                attributes["flow_category"] = "low" 
            elif flow_value < 200:
                attributes["flow_category"] = "normal"
            elif flow_value < 350:
                attributes["flow_category"] = "high"
            else:
                attributes["flow_category"] = "very_high"
        
        # Add flow balance information
        if self._key == "supply_flowrate":
            exhaust_flow = self.coordinator.data.get("exhaust_flowrate")
            if exhaust_flow is not None and flow_value is not None:
                balance = flow_value - exhaust_flow
                attributes["flow_balance"] = round(balance, 0)
                attributes["flow_balance_status"] = (
                    "balanced" if abs(balance) < 10 else
                    "supply_excess" if balance > 0 else "exhaust_excess"
                )
        
        return attributes


class ThesslaGreenPerformanceSensor(ThesslaGreenBaseSensor):
    """Enhanced performance sensor - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str,
    ) -> None:
        """Initialize the enhanced performance sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Enhanced entity description for performance sensors
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced performance context (HA 2025.7+)
        perf_value = self.native_value
        if perf_value is not None and self._attr_native_unit_of_measurement == PERCENTAGE:
            # Performance rating
            if perf_value < 20:
                attributes["performance_rating"] = "very_low"
            elif perf_value < 40:
                attributes["performance_rating"] = "low"
            elif perf_value < 60:
                attributes["performance_rating"] = "medium"
            elif perf_value < 80:
                attributes["performance_rating"] = "good"
            else:
                attributes["performance_rating"] = "excellent"
        
        # Add efficiency context for heat recovery
        if self._key == "heat_recovery_efficiency" and perf_value is not None:
            if perf_value > 80:
                attributes["efficiency_status"] = "excellent"
            elif perf_value > 60:
                attributes["efficiency_status"] = "good"
            elif perf_value > 40:
                attributes["efficiency_status"] = "fair"
            else:
                attributes["efficiency_status"] = "poor"
        
        return attributes


class ThesslaGreenStatusSensor(ThesslaGreenBaseSensor):
    """Enhanced status sensor - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str | None,
    ) -> None:
        """Initialize the enhanced status sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Set appropriate device class based on unit
        device_class = None
        state_class = None
        
        if unit == UnitOfTime.HOURS:
            device_class = SensorDeviceClass.DURATION
            state_class = SensorStateClass.TOTAL_INCREASING if key == "operating_hours" else SensorStateClass.MEASUREMENT
        elif unit in [UnitOfTime.DAYS, UnitOfTime.MINUTES]:
            device_class = SensorDeviceClass.DURATION
            state_class = SensorStateClass.MEASUREMENT
        
        # Enhanced entity description for status sensors
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            device_class=device_class,
            native_unit_of_measurement=unit,
            state_class=state_class,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced status context (HA 2025.7+)
        status_value = self.native_value
        
        if self._key == "filter_time_remaining" and status_value is not None:
            if status_value <= 7:
                attributes["replacement_urgency"] = "urgent"
            elif status_value <= 30:
                attributes["replacement_urgency"] = "soon"
            elif status_value <= 90:
                attributes["replacement_urgency"] = "planned"
            else:
                attributes["replacement_urgency"] = "good"
        
        elif self._key == "operating_hours" and status_value is not None:
            # Convert to years for context
            years = status_value / (24 * 365)
            attributes["operating_years"] = round(years, 1)
            
            if years < 1:
                attributes["service_category"] = "new"
            elif years < 3:
                attributes["service_category"] = "regular"
            elif years < 5:
                attributes["service_category"] = "mature"
            else:
                attributes["service_category"] = "veteran"
        
        elif self._key == "antifreeze_stage" and status_value is not None:
            stage_descriptions = {
                0: "Inactive",
                1: "Stage 1 - Reduced flow",
                2: "Stage 2 - Preheating active", 
                3: "Stage 3 - Maximum protection"
            }
            attributes["stage_description"] = stage_descriptions.get(status_value, f"Stage {status_value}")
        
        return attributes


class ThesslaGreenPowerSensor(ThesslaGreenBaseSensor):
    """Enhanced power/energy sensor - HA 2025.7+ New Feature."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str,
    ) -> None:
        """Initialize the enhanced power sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Set device class and state class based on measurement type
        device_class = None
        state_class = None
        
        if unit == UnitOfPower.WATT:
            device_class = SensorDeviceClass.POWER
            state_class = SensorStateClass.MEASUREMENT
        elif unit == UnitOfEnergy.KILO_WATT_HOUR:
            device_class = SensorDeviceClass.ENERGY
            state_class = SensorStateClass.TOTAL_INCREASING
        
        # Enhanced entity description for power sensors
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            device_class=device_class,
            native_unit_of_measurement=unit,
            state_class=state_class,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced power context (HA 2025.7+)
        power_value = self.native_value
        
        if self._key == "actual_power_consumption" and power_value is not None:
            # Power consumption rating for home ventilation units
            if power_value < 50:
                attributes["consumption_rating"] = "very_low"
            elif power_value < 100:
                attributes["consumption_rating"] = "low"
            elif power_value < 200:
                attributes["consumption_rating"] = "normal"
            elif power_value < 300:
                attributes["consumption_rating"] = "high"
            else:
                attributes["consumption_rating"] = "very_high"
            
            # Add current intensity for context
            current_intensity = self.coordinator.data.get("current_intensity")
            if current_intensity is not None and current_intensity > 0:
                attributes["power_per_percent"] = round(power_value / current_intensity, 1)
        
        elif self._key == "power_efficiency" and power_value is not None:
            if power_value < 1.0:
                attributes["efficiency_rating"] = "excellent"
            elif power_value < 2.0:
                attributes["efficiency_rating"] = "good"
            elif power_value < 3.0:
                attributes["efficiency_rating"] = "fair"
            else:
                attributes["efficiency_rating"] = "poor"
        
        return attributes


class ThesslaGreenErrorSensor(ThesslaGreenBaseSensor):
    """Enhanced error/warning sensor - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the enhanced error sensor."""
        super().__init__(coordinator, key, name, icon, f"Current {name.lower()}")
        
        # Enhanced entity description for error sensors
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced error/warning context (HA 2025.7+)
        code = self.native_value or 0
        
        if self._key == "error_code":
            description = ERROR_CODES.get(code, f"Unknown error ({code})")
            attributes["description"] = description
            attributes["severity"] = "error" if code != 0 else "none"
            attributes["active"] = code != 0
        elif self._key == "warning_code":
            description = WARNING_CODES.get(code, f"Unknown warning ({code})")
            attributes["description"] = description
            attributes["severity"] = "warning" if code != 0 else "none"
            attributes["active"] = code != 0
        
        # Add troubleshooting information
        if code != 0:
            attributes["requires_attention"] = True
            if code in [1, 2, 3, 4, 5, 6, 7]:  # Sensor errors
                attributes["category"] = "sensor"
            elif code in [8, 9]:  # Fan errors
                attributes["category"] = "fan"
            elif code == 10:  # Communication error
                attributes["category"] = "communication"
            else:
                attributes["category"] = "system"
        else:
            attributes["requires_attention"] = False
            attributes["category"] = "none"
        
        return attributes


class ThesslaGreenDeviceSensor(ThesslaGreenBaseSensor):
    """Enhanced device information sensor - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str | None,
    ) -> None:
        """Initialize the enhanced device sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Enhanced entity description for device sensors
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            native_unit_of_measurement=unit,
            entity_category="diagnostic",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced device context (HA 2025.7+)
        if self._key == "firmware_version":
            fw_version = self.native_value
            if fw_version:
                try:
                    # Parse version for comparison
                    major, minor = fw_version.split('.')
                    attributes["version_major"] = int(major)
                    attributes["version_minor"] = int(minor)
                    
                    # Version status (example thresholds)
                    if int(major) >= 5:
                        attributes["version_status"] = "current"
                    elif int(major) >= 4:
                        attributes["version_status"] = "supported"
                    else:
                        attributes["version_status"] = "outdated"
                except:
                    attributes["version_status"] = "unknown"
        
        elif self._key == "device_serial":
            serial = self.native_value
            if serial:
                # Extract information from serial if possible
                attributes["serial_length"] = len(str(serial))
        
        return attributes