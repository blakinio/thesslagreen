from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
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


def test_process_register_value_sensor_unavailable_temperature():
    from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE

    c = _make_coordinator()
    d = MagicMock()
    d.is_temperature.return_value = True
    d.enum = None
    d.decode.return_value = 0
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=d,
    ):
        assert c._process_register_value("outside_temperature", SENSOR_UNAVAILABLE) is None


def test_process_register_value_sensor_unavailable_non_temperature():
    from custom_components.thessla_green_modbus.const import (
        SENSOR_UNAVAILABLE,
        SENSOR_UNAVAILABLE_REGISTERS,
    )

    c = _make_coordinator()
    reg = next((r for r in SENSOR_UNAVAILABLE_REGISTERS if "temperature" not in r), None)
    if reg is None:
        pytest.skip("No non-temperature register in SENSOR_UNAVAILABLE_REGISTERS")
    d = MagicMock()
    d.is_temperature.return_value = False
    d.enum = None
    d.decode.return_value = 0
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=d,
    ):
        assert c._process_register_value(reg, SENSOR_UNAVAILABLE) == SENSOR_UNAVAILABLE


def test_process_register_value_decoded_equals_sensor_unavailable():
    from custom_components.thessla_green_modbus import _coordinator_register_processing as rp
    from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE

    c = _make_coordinator()
    d = MagicMock()
    d.is_temperature.return_value = False
    d.enum = None
    d.decode.return_value = SENSOR_UNAVAILABLE
    with patch.object(rp, "get_register_definitions", return_value={"mode": d}):
        assert c._process_register_value("mode", 1) == SENSOR_UNAVAILABLE


def test_process_register_value_unknown_register():
    assert (
        _make_coordinator()._process_register_value("definitely_not_a_real_register_xyz", 42)
        is False
    )
