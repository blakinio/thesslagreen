"""Runtime helper behavior tests for config flow validation."""

from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities


def test_device_capabilities_serialization():
    caps = DeviceCapabilities(basic_control=True, bypass_system=True, temperature_sensors={"t2", "t1"})
    serialized = caps.as_dict()
    assert serialized["basic_control"] is True
    assert serialized["bypass_system"] is True
    assert serialized["temperature_sensors"] == ["t1", "t2"]
    assert list(caps) == list(serialized.keys())
    assert list(caps.keys()) == list(serialized.keys())
    assert list(caps.items()) == list(serialized.items())
    assert list(caps.values()) == list(serialized.values())
