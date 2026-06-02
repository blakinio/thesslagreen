"""Tests for coordinator/scan_result.py (apply_scan_result)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator.scan_result import apply_scan_result


class _FakeCaps:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_coord(*, skip_missing: bool = False, connection_mode: str = "tcp"):
    dc = SimpleNamespace(
        config=SimpleNamespace(connection_mode=connection_mode),
        skip_missing_registers=skip_missing,
        _device_name="TestDevice",
        _resolved_connection_mode=None,
        last_scan=None,
        available_registers={},
        device_info={},
        capabilities=None,
        unknown_registers={},
        scanned_registers={},
        device_scan_result=None,
    )
    coord = MagicMock()
    coord.device_client = dc
    coord._normalise_available_registers = lambda d: {k: set(v) for k, v in d.items()}
    coord._store_scan_cache = MagicMock()
    return coord


def _call(coord, scan_result, *, skip_missing_registers=None):
    apply_scan_result(
        coord,
        scan_result,
        connection_mode_auto="auto",
        known_missing_registers=skip_missing_registers or {},
        device_capabilities_cls=_FakeCaps,
        cannot_connect_exc=Exception,
        now_fn=lambda: "now",
        logger=MagicMock(),
        unknown_model="Unknown",
    )


def _base_result(*, caps=None, serial_number=None):
    info = {"model": "AirPack4", "firmware": "5.0"}
    if serial_number is not None:
        info["serial_number"] = serial_number
    if caps is None:
        caps = _FakeCaps()
    return {
        "available_registers": {
            "input_registers": ["reg_a"],
            "holding_registers": ["hold_a"],
            "coil_registers": [],
            "discrete_inputs": [],
        },
        "device_info": info,
        "capabilities": caps,
        "unknown_registers": {},
        "scanned_registers": {"input_registers": 1},
        "register_count": 2,
    }


# ---------------------------------------------------------------------------
# Basic state updates
# ---------------------------------------------------------------------------


def test_stores_device_info():
    coord = _make_coord()
    _call(coord, _base_result())
    assert coord.device_client.device_info.get("model") == "AirPack4"


def test_stores_scan_result():
    coord = _make_coord()
    result = _base_result()
    _call(coord, result)
    assert coord.device_client.device_scan_result is result


def test_sets_last_scan():
    coord = _make_coord()
    _call(coord, _base_result())
    assert coord.device_client.last_scan == "now"


def test_populates_available_registers():
    coord = _make_coord()
    _call(coord, _base_result())
    assert "reg_a" in coord.device_client.available_registers["input_registers"]
    assert "hold_a" in coord.device_client.available_registers["holding_registers"]


def test_calls_store_scan_cache():
    coord = _make_coord()
    _call(coord, _base_result())
    coord._store_scan_cache.assert_called_once()


def test_defaults_device_name_when_not_in_scan():
    coord = _make_coord()
    result = _base_result()
    result["device_info"] = {}
    _call(coord, result)
    assert coord.device_client.device_info.get("device_name") == "TestDevice"


def test_does_not_overwrite_existing_device_name():
    coord = _make_coord()
    result = _base_result()
    result["device_info"]["device_name"] = "Custom Name"
    _call(coord, result)
    assert coord.device_client.device_info.get("device_name") == "Custom Name"


# ---------------------------------------------------------------------------
# serial_number register
# ---------------------------------------------------------------------------


def test_adds_serial_number_register_when_present():
    coord = _make_coord()
    _call(coord, _base_result(serial_number="SN-12345"))
    assert "serial_number" in coord.device_client.available_registers["input_registers"]


def test_no_serial_number_register_when_unknown():
    coord = _make_coord()
    _call(coord, _base_result(serial_number="Unknown"))
    assert "serial_number" not in coord.device_client.available_registers["input_registers"]


def test_no_serial_number_register_when_absent():
    coord = _make_coord()
    _call(coord, _base_result())
    assert "serial_number" not in coord.device_client.available_registers["input_registers"]


# ---------------------------------------------------------------------------
# skip_missing_registers
# ---------------------------------------------------------------------------


def test_skip_missing_removes_known_missing():
    coord = _make_coord(skip_missing=True)
    _call(coord, _base_result(), skip_missing_registers={"input_registers": {"reg_a"}})
    assert "reg_a" not in coord.device_client.available_registers["input_registers"]


def test_skip_missing_false_keeps_registers():
    coord = _make_coord(skip_missing=False)
    _call(coord, _base_result(), skip_missing_registers={"input_registers": {"reg_a"}})
    assert "reg_a" in coord.device_client.available_registers["input_registers"]


# ---------------------------------------------------------------------------
# capabilities handling
# ---------------------------------------------------------------------------


def test_caps_from_instance_stored_directly():
    coord = _make_coord()
    caps = _FakeCaps(constant_flow=True)
    _call(coord, _base_result(caps=caps))
    assert coord.device_client.capabilities is caps


def test_caps_from_dict_instantiated():
    coord = _make_coord()
    _call(coord, _base_result(caps={"constant_flow": True}))
    assert isinstance(coord.device_client.capabilities, _FakeCaps)
    assert coord.device_client.capabilities.constant_flow is True


def test_caps_none_creates_default_instance():
    coord = _make_coord()
    result = _base_result()
    result["capabilities"] = None
    _call(coord, result)
    assert isinstance(coord.device_client.capabilities, _FakeCaps)


def test_caps_invalid_type_raises():
    coord = _make_coord()
    with pytest.raises(Exception, match="invalid_capabilities"):
        _call(coord, _base_result(caps=42))


# ---------------------------------------------------------------------------
# resolved connection mode
# ---------------------------------------------------------------------------


def test_resolved_connection_mode_set_when_auto():
    coord = _make_coord(connection_mode="auto")
    result = _base_result()
    result["resolved_connection_mode"] = "tcp"
    _call(coord, result)
    assert coord.device_client._resolved_connection_mode == "tcp"


def test_resolved_connection_mode_not_set_when_not_auto():
    coord = _make_coord(connection_mode="tcp")
    result = _base_result()
    result["resolved_connection_mode"] = "rtu"
    _call(coord, result)
    assert coord.device_client._resolved_connection_mode is None
