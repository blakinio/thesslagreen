"""Focused tests for the production-wired bound adapter functions in config_flow_validation."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

import pytest
import voluptuous as vol
from custom_components.thessla_green_modbus._config_flow.validation import (
    process_scan_capabilities_bound,
    validate_rtu_config_bound,
    validate_tcp_config_bound,
)
from custom_components.thessla_green_modbus.const import (
    CONF_BAUD_RATE,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
)
from custom_components.thessla_green_modbus.errors import CannotConnect

# --- validate_tcp_config_bound ---


def test_validate_tcp_config_bound_valid_ip():
    data: dict[str, Any] = {"host": "192.168.1.1", "port": 502, CONF_SLAVE_ID: 1}
    host, port = validate_tcp_config_bound(data)
    assert host == "192.168.1.1"
    assert port == 502


def test_validate_tcp_config_bound_valid_hostname():
    data: dict[str, Any] = {"host": "modbus.local", "port": 502, CONF_SLAVE_ID: 1}
    host, port = validate_tcp_config_bound(data)
    assert host == "modbus.local"
    assert port == 502


def test_validate_tcp_config_bound_missing_host_raises():
    with pytest.raises(vol.Invalid):
        validate_tcp_config_bound({"port": 502})


def test_validate_tcp_config_bound_invalid_port_raises():
    with pytest.raises(vol.Invalid):
        validate_tcp_config_bound({"host": "192.168.1.1", "port": 99999})


def test_validate_tcp_config_bound_no_dot_hostname_raises():
    with pytest.raises(vol.Invalid):
        validate_tcp_config_bound({"host": "nodothost", "port": 502})


# --- validate_rtu_config_bound ---


def test_validate_rtu_config_bound_valid():
    data: dict[str, Any] = {
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUD_RATE: 9600,
        CONF_PARITY: "none",
        CONF_STOP_BITS: 1,
    }
    validate_rtu_config_bound(data)
    assert data[CONF_SERIAL_PORT] == "/dev/ttyUSB0"
    assert data[CONF_BAUD_RATE] == 9600


def test_validate_rtu_config_bound_missing_serial_port_raises():
    with pytest.raises(vol.Invalid):
        validate_rtu_config_bound({CONF_SERIAL_PORT: "", CONF_BAUD_RATE: 9600})


def test_validate_rtu_config_bound_normalizes_parity_prefix():
    data: dict[str, Any] = {
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUD_RATE: 9600,
        CONF_PARITY: "modbus_parity_even",
        CONF_STOP_BITS: 1,
    }
    validate_rtu_config_bound(data)
    assert data[CONF_PARITY] == "even"


def test_validate_rtu_config_bound_normalizes_baud_rate_string():
    data: dict[str, Any] = {
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUD_RATE: "19200",
        CONF_PARITY: "none",
        CONF_STOP_BITS: 1,
    }
    validate_rtu_config_bound(data)
    assert data[CONF_BAUD_RATE] == 19200


# --- process_scan_capabilities_bound ---


def test_process_scan_capabilities_bound_valid_dataclass():
    @dataclasses.dataclass
    class Caps:
        supported: bool = True

    scan_result: dict[str, Any] = {"capabilities": Caps(supported=True)}
    result = process_scan_capabilities_bound(scan_result, Caps)
    assert result == {"supported": True}


def test_process_scan_capabilities_bound_valid_dict():
    @dataclasses.dataclass
    class Caps:
        supported: bool = False

    scan_result: dict[str, Any] = {"capabilities": {"supported": False}}
    result = process_scan_capabilities_bound(scan_result, Caps)
    assert result == {"supported": False}


def test_process_scan_capabilities_bound_missing_caps_raises():
    @dataclasses.dataclass
    class Caps:
        x: int = 0

    with pytest.raises(CannotConnect):
        process_scan_capabilities_bound({}, Caps)


def test_process_scan_capabilities_bound_accepts_custom_logger():
    @dataclasses.dataclass
    class Caps:
        y: str = "ok"

    logger = logging.getLogger("test.bound")
    scan_result: dict[str, Any] = {"capabilities": Caps(y="ok")}
    result = process_scan_capabilities_bound(scan_result, Caps, logger=logger)
    assert result["y"] == "ok"
