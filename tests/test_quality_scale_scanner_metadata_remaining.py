# mypy: ignore-errors
"""Exercise remaining scanner metadata mapping and cache branches."""

from __future__ import annotations

from custom_components.thessla_green_modbus.scanner.device_info import (
    DeviceCapabilities,
    ScannerDeviceInfo,
)


def test_scanner_device_info_full_mapping_protocol() -> None:
    info = ScannerDeviceInfo(
        device_name="AirPack",
        model="Home 4",
        firmware="4.85",
        serial_number="ABC",
        firmware_available=True,
        capabilities=["basic_control"],
    )
    as_dict = info.as_dict()
    assert dict(info.items()) == as_dict
    assert list(info.keys()) == list(as_dict.keys())
    assert list(info.values()) == list(as_dict.values())
    assert info["firmware"] == "4.85"
    assert dict(iter((key, info[key]) for key in info)) == as_dict
    assert len(info) == len(as_dict)


def test_device_capabilities_mapping_cache_sort_and_invalidation() -> None:
    caps = DeviceCapabilities(
        basic_control=True,
        temperature_sensors={"supply", "outside"},
        flow_sensors={"exhaust", "supply"},
        special_functions={"boost", "eco"},
    )
    first = caps.as_dict()
    assert first["temperature_sensors"] == ["outside", "supply"]
    assert first["flow_sensors"] == ["exhaust", "supply"]
    assert first["special_functions"] == ["boost", "eco"]
    assert caps.as_dict() is first
    assert dict(caps.items()) == first
    assert list(caps.keys()) == list(first.keys())
    assert list(caps.values()) == list(first.values())
    assert caps["basic_control"] is True
    assert set(iter(caps)) == set(first)
    assert len(caps) == len(first)

    caps.weekly_schedule = True
    second = caps.as_dict()
    assert second is not first
    assert second["weekly_schedule"] is True


def test_device_capabilities_cache_assignment_does_not_recursively_invalidate() -> None:
    caps = DeviceCapabilities()
    cached = caps.as_dict()
    caps._as_dict_cache = cached
    assert caps._as_dict_cache is cached
