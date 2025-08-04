"""Binary sensor platform for ThesslaGreen Modbus Integration - FIXED VERSION."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
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
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen binary sensor entities."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    
    # Get available register sets
    input_regs = coordinator.available_registers.get("input_registers", set())
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    coil_regs = coordinator.available_registers.get("coil_registers", set())
    discrete_regs = coordinator.available_registers.get("discrete_inputs", set())

    # ====== MAIN DEVICE STATUS SENSOR (Enhanced) ======
    # This will use the enhanced device status detection from coordinator
    entities.append(
        ThesslaGreenDeviceStatusSensor(coordinator)
    )

    # ====== SYSTEM STATUS SENSORS ======
    
    # Constant Flow system
    if "constant_flow_active" in input_regs:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator,
                "constant_flow_active",
                "Constant Flow aktywny",
                "mdi:fan-auto",
                BinarySensorDeviceClass.RUNNING,
            )
        )

    # Water removal (HEWR) system
    if "water_removal_active" in input_regs:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator,
                "water_removal_active",
                "HEWR aktywny",
                "mdi:water-pump",
                BinarySensorDeviceClass.RUNNING,
            )
        )

    # ====== COIL SENSORS (Output status) ======
    
    coil_sensors = [
        ("power_supply_fans", "Zasilanie wentylatorów", "mdi:power", BinarySensorDeviceClass.POWER),
        ("bypass", "Bypass aktywny", "mdi:valve", None),
        ("gwc", "GWC aktywny", "mdi:heat-pump", BinarySensorDeviceClass.RUNNING),
        ("heating_cable", "Kabel grzejny", "mdi:heating-coil", BinarySensorDeviceClass.HEAT),
        ("duct_water_heater_pump", "Pompa nagrzewnicy", "mdi:pump", BinarySensorDeviceClass.RUNNING),
        ("work_permit", "Pozwolenie pracy (Expansion)", "mdi:check-circle", None),
        ("hood", "Przepustnica OKAP", "mdi:kitchen", None),
        ("info", "Sygnał potwierdzenia pracy", "mdi:information", None),
    ]

    for sensor_key, name, icon, device_class in coil_sensors:
        if sensor_key in coil_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class
                )
            )

    # ====== DISCRETE INPUT SENSORS (Input status) ======
    
    discrete_sensors = [
        ("expansion", "Moduł Expansion", "mdi:expansion-card", BinarySensorDeviceClass.CONNECTIVITY),
        ("contamination_sensor", "Czujnik jakości powietrza", "mdi:air-filter", None),
        ("airing_sensor", "Czujnik wilgotności", "mdi:water-percent", BinarySensorDeviceClass.MOISTURE),
        ("fireplace", "Kominek", "mdi:fireplace", None),
        ("hood_input", "Wejście OKAP", "mdi:kitchen", None),
        ("airing_switch", "Włącznik WIETRZENIE", "mdi:light-switch", None),
        ("airing_mini", "AirS Wietrzenie", "mdi:fan-auto", None),
        ("fan_speed_1", "AirS 1 bieg", "mdi:fan-speed-1", None),
        ("fan_speed_2", "AirS 2 bieg", "mdi:fan-speed-2", None),
        ("fan_speed_3", "AirS 3 bieg", "mdi:fan-speed-3", None),
        ("fire_alarm", "Alarm pożarowy", "mdi:fire-alert", BinarySensorDeviceClass.SAFETY),
        ("empty_house", "Pusty dom", "mdi:home-minus", BinarySensorDeviceClass.PRESENCE),
        ("dp_duct_filter_overflow", "Presostat filtra kanałowego", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM),
        ("dp_ahu_filter_overflow", "Presostat filtrów rekuperatora", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM),
        ("duct_heater_protection", "Zabezpieczenie nagrzewnicy", "mdi:shield-alert", BinarySensorDeviceClass.SAFETY),
        ("ahu_filter_protection", "Zabezpieczenie FPX", "mdi:shield-alert", BinarySensorDeviceClass.SAFETY),
    ]

    for sensor_key, name, icon, device_class in discrete_sensors:
        if sensor_key in discrete_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class
                )
            )

    # ====== SYSTEM MODE SENSORS (Based on holding registers) ======
    
    # FPX Antifreeze system
    if "antifreeze_mode" in holding_regs:
        entities.append(
            ThesslaGreenModeSensor(
                coordinator,
                "antifreeze_mode",
                "System FPX aktywny",
                "mdi:snowflake-alert",
                BinarySensorDeviceClass.RUNNING,
            )
        )

    # GWC regeneration active
    if "gwc_regen_flag" in holding_regs:
        entities.append(
            ThesslaGreenModeSensor(
                coordinator,
                "gwc_regen_flag",
                "Regeneracja GWC aktywna",
                "mdi:refresh",
                BinarySensorDeviceClass.RUNNING,
            )
        )

    # Comfort mode active
    if "comfort_mode" in holding_regs:
        entities.append(
            ThesslaGreenModeSensor(
                coordinator,
                "comfort_mode",
                "Tryb KOMFORT aktywny",
                "mdi:home-thermometer",
                BinarySensorDeviceClass.RUNNING,
            )
        )

    if entities:
        _LOGGER.debug("Adding %d binary sensor entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenDeviceStatusSensor(CoordinatorEntity, BinarySensorEntity):
    """Enhanced main device status sensor using smart detection."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the device status sensor."""
        super().__init__(coordinator)
        
        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        
        self._attr_name = f"{device_name} Status urządzenia"
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_device_status_smart"
        self._attr_icon = "mdi:air-conditioner"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        # Use the enhanced device status from coordinator
        return self.coordinator.data.get("device_status_smart")

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add diagnostic information
        panel_mode = self.coordinator.data.get("on_off_panel_mode")
        if panel_mode is not None:
            attributes["panel_mode"] = "ON" if panel_mode == 1 else "OFF"
        
        fan_power = self.coordinator.data.get("power_supply_fans")
        if fan_power is not None:
            attributes["fan_power"] = "ON" if fan_power else "OFF"
        
        supply_pct = self.coordinator.data.get("supply_percentage")
        exhaust_pct = self.coordinator.data.get("exhaust_percentage")
        if supply_pct is not None and exhaust_pct is not None:
            attributes["fan_activity"] = f"Supply: {supply_pct}%, Exhaust: {exhaust_pct}%"
        
        supply_flow = self.coordinator.data.get("supply_flowrate")
        exhaust_flow = self.coordinator.data.get("exhaust_flowrate")
        if supply_flow is not None and exhaust_flow is not None:
            attributes["air_flows"] = f"Supply: {supply_flow}m³/h, Exhaust: {exhaust_flow}m³/h"
        
        mode = self.coordinator.data.get("mode")
        if mode is not None:
            mode_names = {0: "Automatyczny", 1: "Manualny", 2: "Chwilowy"}
            attributes["operating_mode"] = mode_names.get(mode, f"Unknown({mode})")
        
        special_mode = self.coordinator.data.get("special_mode")
        if special_mode is not None and special_mode > 0:
            from .const import SPECIAL_MODES
            attributes["special_function"] = SPECIAL_MODES.get(special_mode, f"Unknown({special_mode})")
        
        # Add last update time
        import datetime
        attributes["last_update"] = datetime.datetime.now().isoformat()
        
        return attributes


class ThesslaGreenBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """General ThesslaGreen binary sensor."""

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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self._sensor_key in self.coordinator.data
        )

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add register information for debugging
        register_info = self._get_register_info()
        if register_info:
            attributes.update(register_info)
        
        # Add last seen timestamp if available
        if self.is_on is not None:
            import datetime
            attributes["last_seen"] = datetime.datetime.now().isoformat()
        
        return attributes

    def _get_register_info(self) -> dict[str, str]:
        """Get register information for debugging."""
        from .const import COIL_REGISTERS, DISCRETE_INPUT_REGISTERS, INPUT_REGISTERS, HOLDING_REGISTERS
        
        if self._sensor_key in COIL_REGISTERS:
            return {
                "modbus_address": f"0x{COIL_REGISTERS[self._sensor_key]:04X}",
                "register_type": "coil"
            }
        elif self._sensor_key in DISCRETE_INPUT_REGISTERS:
            return {
                "modbus_address": f"0x{DISCRETE_INPUT_REGISTERS[self._sensor_key]:04X}",
                "register_type": "discrete_input"
            }
        elif self._sensor_key in INPUT_REGISTERS:
            return {
                "modbus_address": f"0x{INPUT_REGISTERS[self._sensor_key]:04X}",
                "register_type": "input_register"
            }
        elif self._sensor_key in HOLDING_REGISTERS:
            return {
                "modbus_address": f"0x{HOLDING_REGISTERS[self._sensor_key]:04X}",
                "register_type": "holding_register"
            }
        return {}


class ThesslaGreenModeSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for mode-based states (holding registers with value interpretation)."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        sensor_key: str,
        name: str,
        icon: str,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the mode sensor."""
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
        """Return true if the mode is active."""
        value = self.coordinator.data.get(self._sensor_key)
        if value is None:
            return None
        
        # Interpret mode values
        if self._sensor_key == "antifreeze_mode":
            return value == 1  # 1 = active, 0 = inactive
        elif self._sensor_key == "gwc_regen_flag":
            return value == 1  # 1 = regeneration active
        elif self._sensor_key == "comfort_mode":
            return value > 0   # 1 = heating, 2 = cooling, 0 = inactive
        
        # Default: any non-zero value means active
        return value > 0

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        value = self.coordinator.data.get(self._sensor_key)
        if value is not None:
            attributes["raw_value"] = value
            
            # Add interpretation for specific sensors
            if self._sensor_key == "antifreeze_mode":
                attributes["interpretation"] = "Active" if value == 1 else "Inactive"
            elif self._sensor_key == "comfort_mode":
                interpretations = {0: "Inactive", 1: "Heating", 2: "Cooling"}
                attributes["interpretation"] = interpretations.get(value, f"Unknown({value})")
            elif self._sensor_key == "gwc_regen_flag":
                attributes["interpretation"] = "Regenerating" if value == 1 else "Normal operation"
        
        # Add register information
        from .const import HOLDING_REGISTERS
        if self._sensor_key in HOLDING_REGISTERS:
            attributes["modbus_address"] = f"0x{HOLDING_REGISTERS[self._sensor_key]:04X}"
            attributes["register_type"] = "holding_register"
        
        return attributes