"""Shared coordinator fixtures/helpers for split coordinator tests."""

from unittest.mock import MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function


def _make_config_entry(data: dict, options: dict | None = None) -> MagicMock:
    """Create a minimal config entry mock."""
    entry = MagicMock()
    entry.data = data
    entry.entry_id = "test"
    entry.options = options or {}
    return entry


def make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    """Create a ThesslaGreenModbusCoordinator with test-friendly defaults.

    Shared factory used across coordinator test modules to avoid repetition.
    All keyword arguments are forwarded to ``from_params`` and override defaults.
    """
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function("04")}
HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}


@pytest.fixture
def coordinator():
    """Create a test coordinator."""
    hass = MagicMock()
    available_registers = {
        "holding_registers": {"mode", "air_flow_rate_manual", "special_mode"},
        "input_registers": {"outside_temperature", "supply_temperature"},
        "coil_registers": {"system_on_off"},
        "discrete_inputs": set(),
    }
    coordinator = ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=10,
        retry=3,
    )
    coordinator.device_client.available_registers = available_registers
    return coordinator
