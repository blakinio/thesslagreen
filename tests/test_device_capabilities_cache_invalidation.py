from custom_components.thessla_green_modbus.scanner_core import (
    DeviceCapabilities,
)


def test_capabilities_cache_invalidation() -> None:
    """Modifying attributes after ``as_dict`` updates the cached result."""
    caps = DeviceCapabilities(basic_control=True)
    assert caps.as_dict()["basic_control"] is True

    caps.basic_control = False
    assert caps.as_dict()["basic_control"] is False

    # Reassigning set attributes should also invalidate the cache
    caps.temperature_sensors = {"t1"}
    assert caps.as_dict()["temperature_sensors"] == ["t1"]

    caps.temperature_sensors = {"t1", "t2"}
    assert caps.as_dict()["temperature_sensors"] == ["t1", "t2"]
