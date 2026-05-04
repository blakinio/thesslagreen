"""Runtime helper behavior tests for config flow validation."""

import pytest
from custom_components.thessla_green_modbus.config_flow_device_validation import (
    _build_validation_result,
    _create_scanner,
    _require_verify_connection,
)
from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities


def test_device_capabilities_serialization():
    caps = DeviceCapabilities(
        basic_control=True, bypass_system=True, temperature_sensors={"t2", "t1"}
    )
    serialized = caps.as_dict()
    assert serialized["basic_control"] is True
    assert serialized["bypass_system"] is True
    assert serialized["temperature_sensors"] == ["t1", "t2"]
    assert list(caps) == list(serialized.keys())
    assert list(caps.keys()) == list(serialized.keys())
    assert list(caps.items()) == list(serialized.items())
    assert list(caps.values()) == list(serialized.values())


def test_require_verify_connection_rejects_missing_method():
    with pytest.raises(AttributeError, match="verify_connection"):
        _require_verify_connection(object())


def test_build_validation_result_attaches_capabilities():
    scan_result = {"device_info": {"model": "x"}}

    def _fake_caps(result, cls):
        assert result is scan_result
        assert cls is DeviceCapabilities
        return {"basic_control": True}

    payload = _build_validation_result(
        name="Test Device",
        scan_result=scan_result,
        capabilities_cls=DeviceCapabilities,
        process_scan_capabilities=_fake_caps,
    )

    assert payload["title"] == "Test Device"
    assert payload["device_info"] == {"model": "x"}
    assert payload["scan_result"]["capabilities"] == {"basic_control": True}


@pytest.mark.asyncio
async def test_create_scanner_uses_normalized_params():
    recorded: dict[str, object] = {}

    class _FakeScanner:
        async def verify_connection(self):
            return None

        async def scan_device(self):
            return {"device_info": {"model": "ok"}}

    class _FakeScannerCls:
        @staticmethod
        async def create(**kwargs):
            recorded.update(kwargs)
            return _FakeScanner()

    async def _run_with_retry(func, retries, backoff):
        return await func()

    scanner = await _create_scanner(
        scanner_cls=_FakeScannerCls,
        hass=object(),
        params={
            "host": "127.0.0.1",
            "port": 502,
            "slave_id": 10,
            "timeout": 5.0,
            "deep_scan": True,
            "connection_type": "tcp",
            "connection_mode": None,
            "serial_port": None,
            "baud_rate": None,
            "parity": "N",
            "stop_bits": 1,
        },
        default_retry=3,
        config_flow_backoff=0.1,
        run_with_retry=_run_with_retry,
    )

    assert scanner is not None
    assert recorded["host"] == "127.0.0.1"
    assert recorded["port"] == 502
    assert recorded["slave_id"] == 10
