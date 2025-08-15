"""Sensors for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any
from importlib import resources

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from . import registers

_LOGGER = logging.getLogger(__name__)


@dataclass
class SensorDefinition:
    """Dataclass representing sensor metadata."""

    translation_key: str
    register_type: str
    unit: str | None
    icon: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    value_map: dict[int, str] | None = None


UNIT_MAP = {
    "°C": UnitOfTemperature.CELSIUS,
    "m³/h": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "m3/h": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "%": PERCENTAGE,
    "V": UnitOfElectricPotential.VOLT,
}

DEVICE_CLASS_MAP = {
    UnitOfTemperature.CELSIUS: SensorDeviceClass.TEMPERATURE,
    UnitOfElectricPotential.VOLT: SensorDeviceClass.VOLTAGE,
}

VALUE_MAPS: dict[str, dict[int, str]] = {
    "mode": {0: "auto", 1: "manual", 2: "temporary"},
    "season_mode": {0: "winter", 1: "summer"},
    "filter_change": {
        1: "presostat",
        2: "flat_filters",
        3: "cleanpad",
        4: "cleanpad_pure",
    },
    "gwc_mode": {0: "off", 1: "auto", 2: "forced"},
    "bypass_mode": {0: "auto", 1: "open", 2: "closed"},
}


def _load_translation_keys() -> set[str]:
    """Load sensor translation keys from the English translation file."""
    path = resources.files(__package__).joinpath("translations/en.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("entity", {}).get("sensor", {}))


def load_sensor_definitions() -> dict[str, dict[str, Any]]:
    """Generate SENSOR_DEFINITIONS from the registers CSV."""
    sensor_keys = _load_translation_keys()
    csv_path = resources.files(__package__).joinpath("data/modbus_registers.csv")
    definitions: dict[str, dict[str, Any]] = {}
    with csv_path.open(encoding="utf-8") as csvfile:
        reader = csv.DictReader(row for row in csvfile if not row.startswith("#"))
        for row in reader:
            name = row["Register_Name"]
            if name not in sensor_keys:
                continue
            unit_raw = row["Unit"].strip()
            unit = UNIT_MAP.get(unit_raw) if unit_raw else None
            device_class = DEVICE_CLASS_MAP.get(unit)
            state_class = SensorStateClass.MEASUREMENT if unit is not None else None
            register_type = (
                "input_registers"
                if name in registers.INPUT_REGISTERS
                else "holding_registers"
            )
            definition = SensorDefinition(
                translation_key=name,
                register_type=register_type,
                unit=unit,
                device_class=device_class,
                state_class=state_class,
                value_map=VALUE_MAPS.get(name),
            )
            definitions[name] = asdict(definition)
    return definitions


SENSOR_DEFINITIONS = load_sensor_definitions()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen sensor entities based on available registers."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Create sensors only for available registers (autoscan result)
    for register_name, sensor_def in SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]

        # Check if this register is available on the device
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenSensor(coordinator, register_name, sensor_def))
            _LOGGER.debug("Created sensor: %s", sensor_def["translation_key"])

    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Created %d sensor entities for %s", len(entities), coordinator.device_name)
    else:
        _LOGGER.warning("No sensor entities created - no compatible registers found")


class ThesslaGreenSensor(ThesslaGreenEntity, SensorEntity):
    """Sensor entity for ThesslaGreen device."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        sensor_definition: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, register_name)
        self._attr_device_info = coordinator.get_device_info()

        self._register_name = register_name
        self._sensor_def = sensor_definition

        # Sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        self._attr_native_unit_of_measurement = sensor_definition.get("unit")
        self._attr_device_class = sensor_definition.get("device_class")
        self._attr_state_class = sensor_definition.get("state_class")

        # Translation setup
        self._attr_translation_key = sensor_definition.get("translation_key")

        _LOGGER.debug(
            "Sensor initialized: %s (%s)",
            sensor_definition.get("translation_key"),
            register_name,
        )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self._register_name)

        if value is None:
            return None
        value_map = self._sensor_def.get("value_map")
        if value_map is not None:
            return value_map.get(value, value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}

        # Add register address for debugging
        if hasattr(self.coordinator, "device_scan_result") and self.coordinator.device_scan_result:
            attrs["register_name"] = self._register_name
            attrs["register_type"] = self._sensor_def["register_type"]

        # Add raw value for diagnostic purposes
        raw_value = self.coordinator.data.get(self._register_name)
        if raw_value is not None and isinstance(raw_value, (int, float)):
            attrs["raw_value"] = raw_value

        return attrs
