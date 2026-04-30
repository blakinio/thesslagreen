"""Split coordinator coverage tests by behavior area."""

from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock

import pytest
from custom_components.thessla_green_modbus.const import (
    SENSOR_UNAVAILABLE,
    SENSOR_UNAVAILABLE_REGISTERS,
)
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.registers.loader import get_register_definition


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


@pytest.fixture
def coordinator():
    """Create a test coordinator."""
    coordinator = _make_coordinator()
    coordinator.available_registers = {
        "holding_registers": {"mode", "air_flow_rate_manual", "special_mode"},
        "input_registers": {"outside_temperature", "supply_temperature"},
        "coil_registers": {"system_on_off"},
        "discrete_inputs": set(),
    }
    return coordinator


def test_get_device_info_model_from_entry():
    """get_device_info uses entry.options when device_info has no model (line 2539)."""
    coord = _make_coordinator()
    from unittest.mock import MagicMock

    entry = MagicMock()
    entry.options = {"model": "Thessla Air 350"}
    entry.data = {}
    coord.entry = entry
    coord.device_scan_result = {}
    coord.device_info = {}
    info = coord.get_device_info()
    assert info["model"] == "Thessla Air 350"

def test_compat_device_info_getattr_key_error():
    """_CompatDeviceInfo.__getattr__ raises AttributeError for missing key (lines 2552-2555)."""
    coord = _make_coordinator()
    info = coord.get_device_info()
    with pytest.raises(AttributeError):
        _ = info.nonexistent_attribute_xyz



# Moved from test_coordinator.py
def test_device_info(coordinator):
    """Test device info property."""
    coordinator.device_info = {"model": "AirPack Home"}
    device_info = coordinator.get_device_info()
    assert device_info["manufacturer"] == "ThesslaGreen"
    assert device_info["model"] == "AirPack Home"


def test_get_device_info_fallback(monkeypatch):
    """get_device_info should work without HA DeviceInfo."""
    import importlib

    import custom_components.thessla_green_modbus as _thg_pkg

    # Track the coordinator package attribute so monkeypatch restores it after the test.
    # Without this, importlib.import_module below sets thg_pkg.coordinator = M_new and
    # subsequent tests that use string-path monkeypatching would patch the wrong module.
    if hasattr(_thg_pkg, "coordinator"):
        monkeypatch.setattr(_thg_pkg, "coordinator", _thg_pkg.coordinator)

    # Simulate missing device_registry module
    monkeypatch.delitem(sys.modules, "homeassistant.helpers.device_registry", raising=False)
    monkeypatch.delitem(
        sys.modules, "custom_components.thessla_green_modbus.coordinator", raising=False
    )
    coordinator_module = importlib.import_module(
        "custom_components.thessla_green_modbus.coordinator"
    )
    hass = MagicMock()
    coord = coordinator_module.ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=10,
        retry=3,
    )
    coord.device_info = {"model": "AirPack Home"}
    device_info = coord.get_device_info()
    assert device_info["manufacturer"] == "ThesslaGreen"
    assert device_info["model"] == "AirPack Home"


def test_register_value_processing(coordinator):
    """Test register value processing."""
    temp_result = coordinator._process_register_value("outside_temperature", 250)
    assert temp_result == 25.0

    heating_result = coordinator._process_register_value("heating_temperature", 250)
    assert heating_result == 25.0

    invalid_temp = coordinator._process_register_value("outside_temperature", 32768)
    assert invalid_temp is None

    percentage_result = coordinator._process_register_value("supply_percentage", 75)
    assert percentage_result == 75

    mode_result = coordinator._process_register_value("mode", 1)
    assert mode_result == 1

    time_result = coordinator._process_register_value("schedule_summer_mon_1", 2069)
    assert time_result == "08:15"


def test_dac_value_processing(coordinator, caplog):
    """Test DAC register value processing and validation."""
    # Valid mid-range value converts to approximately 5V
    result = coordinator._process_register_value("dac_supply", 2048)
    assert result == pytest.approx(5.0, abs=0.01)

    # Zero value stays zero
    result = coordinator._process_register_value("dac_supply", 0)
    assert result == 0

    # Invalid values outside 0-4095 are rejected
    with caplog.at_level(logging.WARNING):
        assert coordinator._process_register_value("dac_supply", 5000) is None
        assert coordinator._process_register_value("dac_supply", -1) is None
        assert "out of range" in caplog.text


@pytest.mark.parametrize(
    "register_name",
    sorted(SENSOR_UNAVAILABLE_REGISTERS),
    ids=sorted(SENSOR_UNAVAILABLE_REGISTERS),
)
def test_process_register_value_sensor_unavailable(coordinator, register_name):
    """Return sentinel when sensors report unavailable for known sensor registers."""
    result = coordinator._process_register_value(register_name, SENSOR_UNAVAILABLE)
    if "temperature" in register_name:
        assert result is None
    else:
        assert result == SENSOR_UNAVAILABLE


@pytest.mark.parametrize(
    ("register_name", "value", "expected"),
    [
        ("supply_flow_rate", 65531, -5),
        ("outside_temperature", 32768, None),
    ],
)
def test_process_register_value_extremes(coordinator, register_name, value, expected):
    """Handle extreme raw register values correctly."""
    result = coordinator._process_register_value(register_name, value)
    assert result == expected


def test_process_register_value_no_magic_number_in_source():
    """Regression guard against reintroducing literal 32768 in coordinator logic."""
    import inspect

    src = inspect.getsource(ThesslaGreenModbusCoordinator._process_register_value)
    assert "32768" not in src


@pytest.mark.parametrize(
    "register_name",
    ["dac_supply", "dac_exhaust", "dac_heater", "dac_cooler"],
    ids=["supply", "exhaust", "heater", "cooler"],
)
@pytest.mark.parametrize(
    "value",
    [0, 4095, -1, 5000],
    ids=["min", "max", "below_min", "above_max"],
)
def test_process_register_value_dac_boundaries(coordinator, register_name, value):
    """Process DAC registers across boundary and out-of-range values."""
    expected = get_register_definition(register_name).decode(value)
    result = coordinator._process_register_value(register_name, value)
    assert result == pytest.approx(expected)


def test_register_value_logging(coordinator, caplog):
    """Test debug and warning logging for register processing."""

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.thessla_green_modbus.coordinator"
    ):
        caplog.clear()
        coordinator._process_register_value("outside_temperature", 250)
        assert "raw=250" in caplog.text
        assert "value=25.0" in caplog.text

    with caplog.at_level(
        logging.WARNING, logger="custom_components.thessla_green_modbus.coordinator"
    ):
        caplog.clear()
        coordinator._process_register_value("outside_temperature", SENSOR_UNAVAILABLE)
        assert not caplog.records
