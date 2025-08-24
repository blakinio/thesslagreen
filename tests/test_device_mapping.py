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


def test_device_info_assignment_and_as_dict() -> None:
    info = ScannerDeviceInfo()
    info.device_name = "Unit"
    info.model = "Model"
    info.firmware = "1.0"
    info.serial_number = "123"
    info.capabilities.append("cap")

    assert info.device_name == "Unit"
    assert info.as_dict() == {
        "device_name": "Unit",
        "model": "Model",
        "firmware": "1.0",
        "serial_number": "123",
        "firmware_available": True,
        "capabilities": ["cap"],
    }


def test_device_capabilities_mapping_and_values() -> None:
    caps = DeviceCapabilities(basic_control=True, temperature_sensors={"t1"})
    assert isinstance(caps, Mapping)
    assert list(caps.values()) == list(caps.as_dict().values())
