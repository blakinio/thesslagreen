"""Verify that every HA platform module declares PARALLEL_UPDATES = 1.

Serialised Modbus I/O (one DeviceClient connection) must not allow HA to
dispatch concurrent entity updates, so each platform module must set
PARALLEL_UPDATES = 1 at module level.
"""

from __future__ import annotations

import importlib

import pytest

PLATFORM_MODULES = [
    "custom_components.thessla_green_modbus.sensor",
    "custom_components.thessla_green_modbus.binary_sensor",
    "custom_components.thessla_green_modbus.number",
    "custom_components.thessla_green_modbus.switch",
    "custom_components.thessla_green_modbus.select",
    "custom_components.thessla_green_modbus.climate",
    "custom_components.thessla_green_modbus.fan",
    "custom_components.thessla_green_modbus.time",
    "custom_components.thessla_green_modbus.text",
    "custom_components.thessla_green_modbus.button",
]


@pytest.mark.parametrize("module_path", PLATFORM_MODULES)
def test_parallel_updates_is_one(module_path: str) -> None:
    """Each platform module must expose PARALLEL_UPDATES == 1."""
    module = importlib.import_module(module_path)
    assert hasattr(module, "PARALLEL_UPDATES"), f"{module_path} is missing PARALLEL_UPDATES"
    assert module.PARALLEL_UPDATES == 1, (
        f"{module_path}.PARALLEL_UPDATES == {module.PARALLEL_UPDATES!r}, expected 1"
    )
