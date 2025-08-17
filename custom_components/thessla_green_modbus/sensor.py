"""Sensors for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .entity_mappings import ENTITY_MAPPINGS
from .utils import TIME_REGISTER_PREFIXES, _to_snake_case

_LOGGER = logging.getLogger(__name__)


def _load_sensor_definitions() -> Dict[str, Dict[str, Any]]:
    """Load sensor definitions from ENTITY_MAPPINGS or fallback files."""

    if ENTITY_MAPPINGS.get("sensor"):
        return ENTITY_MAPPINGS["sensor"]

    # Try JSON definition file
    json_path = Path(__file__).with_name("sensor_definitions.json")
    if json_path.exists():
        try:
            with json_path.open(encoding="utf-8") as jsonfile:
                data = json.load(jsonfile)
            return {k: v for k, v in data.items()}
        except Exception as err:  # pragma: no cover - fallback path
            _LOGGER.error("Failed to load sensor definitions from JSON: %s", err)

    # Try CSV definition file
    csv_path = Path(__file__).with_name("sensor_definitions.csv")
    definitions: Dict[str, Dict[str, Any]] = {}
    if csv_path.exists():
        try:
            with csv_path.open(encoding="utf-8", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    name = _to_snake_case(row["register_name"])
                    unit_raw = row.get("unit")
                    if unit_raw == "%":
                        unit = PERCENTAGE
                    elif unit_raw in {"°C", "C"}:
                        unit = UnitOfTemperature.CELSIUS
                    elif unit_raw in {"m3/h", "m³/h"}:
                        unit = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
                    else:
                        unit = unit_raw
                    definitions[name] = {
                        "translation_key": row.get("translation_key", name),
                        "icon": row.get("icon"),
                        "device_class": getattr(
                            SensorDeviceClass, row.get("device_class", ""), None
                        ),
                        "state_class": getattr(SensorStateClass, row.get("state_class", ""), None),
                        "unit": unit,
                        "register_type": row.get("register_type", "input_registers"),
                    }
        except Exception as err:  # pragma: no cover - fallback path
            _LOGGER.error("Failed to load sensor definitions from CSV: %s", err)

    return definitions


SENSOR_DEFINITIONS: Dict[str, Dict[str, Any]] = _load_sensor_definitions()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen sensor entities based on available registers."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    temp_created = 0
    temp_skipped = 0

    # Create sensors only for available registers (autoscan result)
    for register_name, sensor_def in SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]
        is_temp = sensor_def.get("device_class") == SensorDeviceClass.TEMPERATURE

        # Check if this register is available on the device
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenSensor(coordinator, register_name, sensor_def))
            _LOGGER.debug("Created sensor: %s", sensor_def["translation_key"])
            if is_temp:
                temp_created += 1
        elif is_temp:
            temp_skipped += 1

    if entities:
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning("Entity addition cancelled, adding without initial update")
            async_add_entities(entities, False)
        _LOGGER.info(
            "Created %d sensor entities for %s",
            len(entities),
            coordinator.device_name,
        )
    else:
        _LOGGER.warning("No sensor entities created - no compatible registers found")

    _LOGGER.info(
        "Temperature sensors: %d instantiated, %d skipped",
        temp_created,
        temp_skipped,
    )


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
        if self._register_name.startswith(TIME_REGISTER_PREFIXES):
            if isinstance(value, int):
                return f"{value // 60:02d}:{value % 60:02d}"
            return value
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
