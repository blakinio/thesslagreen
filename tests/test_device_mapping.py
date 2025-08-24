from collections.abc import Mapping

from custom_components.thessla_green_modbus.scanner_core import (
    ScannerDeviceInfo,
    DeviceCapabilities,
)


def test_device_info_mapping_and_values() -> None:
    info = ScannerDeviceInfo(
        model="m", firmware="f", serial_number="s", capabilities=["c"]
    )
    assert isinstance(info, Mapping)
    assert list(info.values()) == list(info.as_dict().values())


def test_device_capabilities_mapping_and_values() -> None:
    caps = DeviceCapabilities(basic_control=True, temperature_sensors={"t1"})
    assert isinstance(caps, Mapping)
    assert list(caps.values()) == list(caps.as_dict().values())
