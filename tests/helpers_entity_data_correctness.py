from __future__ import annotations

from typing import Any

from custom_components.thessla_green_modbus.binary_sensor import ThesslaGreenBinarySensor
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.number import ThesslaGreenNumber
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect
from custom_components.thessla_green_modbus.sensor import ThesslaGreenSensor


def _make_sensor(coordinator, name: str, address: int = 100) -> ThesslaGreenSensor:
    """Create a ThesslaGreenSensor using the live entity mapping for *name*."""
    defn = ENTITY_MAPPINGS["sensor"].get(name, {"translation_key": name})
    return ThesslaGreenSensor(coordinator, name, address, defn)


def _make_binary_sensor(
    coordinator,
    sensor_def: dict[str, Any],
    register_name: str | None = None,
    address: int = 100,
) -> ThesslaGreenBinarySensor:
    reg = register_name or sensor_def.get("register", next(iter(sensor_def.keys())))
    return ThesslaGreenBinarySensor(coordinator, reg, address, sensor_def)


def _make_number(coordinator, register_name: str) -> ThesslaGreenNumber:
    config = ENTITY_MAPPINGS["number"][register_name]
    return ThesslaGreenNumber(coordinator, register_name, config)


def _make_select(coordinator, register_name: str) -> ThesslaGreenSelect:
    defn = ENTITY_MAPPINGS["select"][register_name]
    address = coordinator.get_register_map(defn["register_type"]).get(register_name, 100)
    return ThesslaGreenSelect(coordinator, register_name, address, defn)
