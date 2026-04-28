"""Validate SENSOR_DEFINITIONS register mapping."""

import pytest
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.registers.loader import (
    get_registers_by_function,
)

SENSOR_DEFINITIONS = ENTITY_MAPPINGS.get("sensor", {})

INPUT_REGISTERS = {r.name for r in get_registers_by_function("04")}
HOLDING_REGISTERS = {r.name for r in get_registers_by_function("03")}


def test_sensor_register_mapping() -> None:
    """Each sensor must map to the correct register dictionary."""
    for register_name, sensor_def in SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]
        if register_type == "input_registers":
            assert register_name in INPUT_REGISTERS
            assert register_name not in HOLDING_REGISTERS
        elif register_type == "holding_registers":
            assert register_name in HOLDING_REGISTERS
            assert register_name not in INPUT_REGISTERS
        elif register_type == "calculated":
            assert register_name not in INPUT_REGISTERS
            assert register_name not in HOLDING_REGISTERS
        else:
            pytest.fail(f"Unknown register_type {register_type} for {register_name}")
