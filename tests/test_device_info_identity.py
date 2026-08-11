"""Device registry identity regressions."""

from types import SimpleNamespace

from custom_components.thessla_green_modbus.const import (
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DOMAIN,
)
from custom_components.thessla_green_modbus.coordinator.diagnostics import (
    _stable_device_identifier,
    get_device_info,
)


def _coordinator(
    *,
    host: str,
    serial: str | None,
    entry_id: str = "entry-123",
    connection_type: str = CONNECTION_TYPE_TCP,
):
    device_info = {
        "device_name": "AirPack",
        "firmware": "1.2.3",
        "model": "AirPack 4",
    }
    if serial is not None:
        device_info["serial_number"] = serial
    device_client = SimpleNamespace(
        config=SimpleNamespace(
            host=host,
            port=8899,
            slave_id=10,
            connection_type=connection_type,
        ),
        device_info=device_info,
        device_scan_result=None,
        _device_name="AirPack",
    )
    return SimpleNamespace(
        device_client=device_client,
        entry=SimpleNamespace(entry_id=entry_id, data={}, options={}),
        data={},
    )


def test_device_identifier_prefers_serial_and_ignores_endpoint() -> None:
    """Changing host/port must not change a serial-backed device identity."""
    first = _coordinator(host="192.168.1.10", serial=" AP4-ABC ")
    second = _coordinator(host="192.168.1.99", serial=" AP4-ABC ")

    assert _stable_device_identifier(first) == "serial:ap4-abc"
    assert _stable_device_identifier(second) == "serial:ap4-abc"


def test_device_identifier_falls_back_to_config_entry_not_endpoint() -> None:
    """Devices without a usable serial remain stable across endpoint changes."""
    first = _coordinator(host="airpack.local", serial="Unknown")
    second = _coordinator(host="airpack-new.local", serial=None)

    assert _stable_device_identifier(first) == "entry:entry-123"
    assert _stable_device_identifier(second) == "entry:entry-123"


def test_get_device_info_uses_native_mapping_and_stable_identifier() -> None:
    """DeviceInfo is a normal mapping and no compatibility attribute shim is required."""
    coordinator = _coordinator(host="airpack.local", serial=" AP4-42 ")

    info = get_device_info(coordinator)

    assert info["identifiers"] == {(DOMAIN, "serial:ap4-42")}
    assert info["serial_number"] == "AP4-42"
    assert info["configuration_url"] == "http://airpack.local"
    assert not hasattr(info, "name")


def test_rtu_device_info_omits_invalid_configuration_url() -> None:
    """Serial RTU devices must not publish an empty HTTP configuration URL."""
    coordinator = _coordinator(
        host="",
        serial="AP4-RTU",
        connection_type=CONNECTION_TYPE_RTU,
    )

    info = get_device_info(coordinator)

    assert info["identifiers"] == {(DOMAIN, "serial:ap4-rtu")}
    assert "configuration_url" not in info
