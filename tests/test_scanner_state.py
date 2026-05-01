"""Tests for scanner state initialization helper."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.thessla_green_modbus.const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    DEFAULT_BAUD_RATE,
    DEFAULT_PARITY,
    DEFAULT_SERIAL_PORT,
    DEFAULT_STOP_BITS,
)
from custom_components.thessla_green_modbus.scanner import state as scanner_state


def test_build_connection_state_normalizes_serial_settings() -> None:
    state = scanner_state.build_connection_state(
        connection_type="rtu",
        connection_mode=CONNECTION_MODE_TCP,
        resolved_connection_mode=CONNECTION_MODE_TCP,
        serial_port="",
        baud_rate="bad",
        parity="invalid",
        stop_bits=99,
    )

    assert state.serial_port == DEFAULT_SERIAL_PORT
    assert state.baud_rate == DEFAULT_BAUD_RATE
    assert state.parity == DEFAULT_PARITY
    assert state.stop_bits == DEFAULT_STOP_BITS


def test_build_connection_state_clears_fixed_mode_for_auto() -> None:
    state = scanner_state.build_connection_state(
        connection_type="tcp",
        connection_mode=CONNECTION_MODE_AUTO,
        resolved_connection_mode=CONNECTION_MODE_TCP,
        serial_port="/dev/ttyUSB0",
        baud_rate=19200,
        parity="e",
        stop_bits=2,
    )

    assert state.resolved_connection_mode is None


def test_apply_connection_state_assigns_scanner_attributes() -> None:
    scanner = SimpleNamespace()
    state = scanner_state.build_connection_state(
        connection_type="tcp",
        connection_mode=CONNECTION_MODE_TCP,
        resolved_connection_mode=CONNECTION_MODE_TCP,
        serial_port="/dev/ttyS0",
        baud_rate=9600,
        parity="n",
        stop_bits=1,
    )

    scanner_state.apply_connection_state(scanner, state)

    assert scanner.connection_type == "tcp"
    assert scanner.connection_mode == CONNECTION_MODE_TCP
    assert scanner._resolved_connection_mode == CONNECTION_MODE_TCP
    assert scanner.serial_port == "/dev/ttyS0"


def test_apply_register_defaults_assigns_maps() -> None:
    scanner = SimpleNamespace()
    scanner_state.apply_register_defaults(scanner, known_missing_registers={"input": {}})

    assert scanner._known_missing_registers == {"input": {}}
    assert isinstance(scanner._input_register_map, dict)
    assert isinstance(scanner._holding_register_map, dict)
    assert isinstance(scanner._coil_register_map, dict)
    assert isinstance(scanner._discrete_input_register_map, dict)
    assert isinstance(scanner._multi_register_sizes, dict)
