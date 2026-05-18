"""Tests for the config-flow TCP-port timeout fix.

Covers the bug where AUTO mode on a non-default port tried tcp_rtu first,
consuming its full per-attempt timeout before the TCP attempt could complete,
causing the outer validation wrapper to cancel a successful TCP connection while
read_input_registers was still in flight.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.exceptions import ConnectionException, ModbusIOException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ok_response(registers=(1,)):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = list(registers)
    return resp


def _make_transport(*, ensure_side_effect=None, input_side_effect=None):
    t = MagicMock()
    t.close = AsyncMock()
    t.ensure_connected = (
        AsyncMock(side_effect=ensure_side_effect) if ensure_side_effect else AsyncMock()
    )
    t.read_input_registers = (
        AsyncMock(side_effect=input_side_effect)
        if input_side_effect
        else AsyncMock(return_value=_make_ok_response())
    )
    t.read_holding_registers = AsyncMock(return_value=_make_ok_response())
    t.is_connected = MagicMock(return_value=True)
    return t


async def _make_scanner(port=502, connection_mode="auto", **kwargs):
    from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

    return await ThesslaGreenDeviceScanner.create(
        "192.168.3.12", port, 1, connection_mode=connection_mode, **kwargs
    )


# ---------------------------------------------------------------------------
# Fix 1: build_auto_tcp_attempts always puts TCP first
# ---------------------------------------------------------------------------


def test_build_auto_tcp_attempts_tcp_first_on_default_port():
    """Standard port 502 must still try TCP before tcp_rtu."""
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP
    from custom_components.thessla_green_modbus.scanner import setup as scanner_setup

    scanner = MagicMock()
    scanner.timeout = 10
    scanner.port = 502
    scanner.host = "192.168.1.1"
    scanner.retry = 1
    scanner.backoff = 0.0

    with patch.object(scanner_setup, "build_tcp_transport", return_value=MagicMock()):
        attempts = scanner_setup.build_auto_tcp_attempts(scanner)

    assert attempts[0][0] == CONNECTION_MODE_TCP, "TCP must be tried first on port 502"


def test_build_auto_tcp_attempts_tcp_first_on_non_default_port():
    """Non-standard port 8899 must also try TCP before tcp_rtu (regression test)."""
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP
    from custom_components.thessla_green_modbus.scanner import setup as scanner_setup

    scanner = MagicMock()
    scanner.timeout = 10
    scanner.port = 8899
    scanner.host = "192.168.3.12"
    scanner.retry = 1
    scanner.backoff = 0.0

    with patch.object(scanner_setup, "build_tcp_transport", return_value=MagicMock()):
        attempts = scanner_setup.build_auto_tcp_attempts(scanner)

    assert attempts[0][0] == CONNECTION_MODE_TCP, (
        "TCP must be tried first even on non-standard port 8899"
    )
    assert len(attempts) == 2, "AUTO mode must produce exactly two attempts"


def test_build_auto_tcp_attempts_tcp_rtu_is_second():
    """tcp_rtu must still appear as the second AUTO attempt."""
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP_RTU
    from custom_components.thessla_green_modbus.scanner import setup as scanner_setup

    scanner = MagicMock()
    scanner.timeout = 10
    scanner.port = 8899
    scanner.host = "192.168.3.12"
    scanner.retry = 1
    scanner.backoff = 0.0

    with patch.object(scanner_setup, "build_tcp_transport", return_value=MagicMock()):
        attempts = scanner_setup.build_auto_tcp_attempts(scanner)

    assert attempts[1][0] == CONNECTION_MODE_TCP_RTU


# ---------------------------------------------------------------------------
# Fix 2: _compute_verify_timeout returns large enough value for AUTO mode
# ---------------------------------------------------------------------------


def test_compute_verify_timeout_non_auto_returns_base():
    """Non-AUTO scanners must get max(2, timeout) as before."""
    from custom_components.thessla_green_modbus._config_flow.device_validation import (
        _compute_verify_timeout,
    )
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP

    scanner = SimpleNamespace(connection_mode=CONNECTION_MODE_TCP)
    result = _compute_verify_timeout(scanner, 10.0)
    assert result == 10.0

    scanner_short = SimpleNamespace(connection_mode=CONNECTION_MODE_TCP)
    result_short = _compute_verify_timeout(scanner_short, 1.0)
    assert result_short == 2.0


def test_compute_verify_timeout_auto_covers_all_attempts():
    """AUTO mode outer timeout must be >= tcp_timeout + rtu_timeout."""
    from custom_components.thessla_green_modbus._config_flow.device_validation import (
        _compute_verify_timeout,
    )
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_AUTO

    scanner = SimpleNamespace(connection_mode=CONNECTION_MODE_AUTO)
    timeout = 10.0
    result = _compute_verify_timeout(scanner, timeout)

    rtu_timeout = min(max(timeout, 2.0), 5.0)  # 5.0
    tcp_timeout = min(max(timeout, 5.0), 10.0)  # 10.0
    assert result >= tcp_timeout + rtu_timeout, (
        "AUTO verify timeout must cover all per-attempt timeouts combined"
    )


def test_compute_verify_timeout_auto_includes_buffer():
    """AUTO mode outer timeout should have a buffer above the bare minimum."""
    from custom_components.thessla_green_modbus._config_flow.device_validation import (
        _compute_verify_timeout,
    )
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_AUTO

    scanner = SimpleNamespace(connection_mode=CONNECTION_MODE_AUTO)
    result = _compute_verify_timeout(scanner, 10.0)
    assert result > 15.0, "AUTO verify timeout must exceed tcp_timeout + rtu_timeout (15s)"


# ---------------------------------------------------------------------------
# Integration: verify_connection TCP-first on port 8899 (AUTO mode)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_connection_tries_tcp_first_on_port_8899():
    """PORT 8899 + connection_type=tcp: TCP transport must be attempted before tcp_rtu."""
    scanner = await _make_scanner(port=8899, connection_mode="auto")

    tcp_transport = _make_transport()
    tcp_rtu_transport = _make_transport()

    call_order: list[str] = []

    async def tcp_connect():
        call_order.append("tcp")

    async def tcp_rtu_connect():
        call_order.append("tcp_rtu")

    tcp_transport.ensure_connected = AsyncMock(side_effect=tcp_connect)
    tcp_rtu_transport.ensure_connected = AsyncMock(side_effect=tcp_rtu_connect)

    with patch.object(
        scanner,
        "_build_auto_tcp_attempts",
        return_value=[("tcp", tcp_transport, 10.0), ("tcp_rtu", tcp_rtu_transport, 5.0)],
    ):
        await scanner.verify_connection()

    assert call_order[0] == "tcp", "TCP must be the first attempt on port 8899"
    tcp_rtu_transport.ensure_connected.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: TCP success after tcp_rtu timeout must not be cancelled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_scanner_validation_auto_timeout_covers_tcp_after_rtu_timeout():
    """Outer verify timeout must not cancel a TCP read that follows a tcp_rtu failure."""
    from custom_components.thessla_green_modbus._config_flow.device_validation import (
        _run_scanner_validation,
    )
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_AUTO

    scan_result = {"device_info": {}, "available_registers": {}}
    calls: list[str] = []

    async def verify_fn():
        calls.append("verify")

    async def scan_fn():
        calls.append("scan")
        return scan_result

    scanner = SimpleNamespace(
        connection_mode=CONNECTION_MODE_AUTO,
        verify_connection=verify_fn,
        scan_device=scan_fn,
    )

    received_timeouts: list[float] = []

    async def run_scanner_call(func, timeout):
        received_timeouts.append(timeout)
        result = func()
        if asyncio.iscoroutine(result):
            return await result
        return result

    await _run_scanner_validation(
        scanner=scanner,
        timeout=10.0,
        run_scanner_call=run_scanner_call,
    )

    assert calls == ["verify", "scan"]
    # Verify timeout for AUTO must exceed the sum of per-attempt timeouts (15s)
    assert received_timeouts[0] > 15.0, (
        f"AUTO verify timeout {received_timeouts[0]} is too small; "
        "must be > tcp_timeout(10) + rtu_timeout(5)"
    )
    # Scan timeout uses the user-supplied timeout unchanged
    assert received_timeouts[1] == 10.0


# ---------------------------------------------------------------------------
# Regression: explicit tcp_rtu connection_mode still uses only tcp_rtu transport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explicit_tcp_rtu_mode_uses_only_tcp_rtu():
    """When connection_mode=tcp_rtu, only tcp_rtu transport must be attempted."""
    from custom_components.thessla_green_modbus.const import (
        CONNECTION_MODE_TCP_RTU,
        CONNECTION_TYPE_TCP,
    )
    from custom_components.thessla_green_modbus.scanner import setup as scanner_setup

    scanner = MagicMock()
    scanner.connection_type = CONNECTION_TYPE_TCP
    scanner.connection_mode = CONNECTION_MODE_TCP_RTU
    scanner.timeout = 10
    scanner.serial_port = ""

    attempts = scanner_setup.build_verification_attempts(scanner)

    assert len(attempts) == 1
    assert attempts[0][0] == CONNECTION_MODE_TCP_RTU


# ---------------------------------------------------------------------------
# Regression: missing/invalid response still surfaces timeout/cannot_connect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_connection_tcp_timeout_surfaces_error():
    """When both AUTO attempts time out, verify_connection must raise TimeoutError."""
    scanner = await _make_scanner(port=8899, connection_mode="auto")

    t1 = _make_transport(ensure_side_effect=TimeoutError("probe timeout"))
    t2 = _make_transport(ensure_side_effect=TimeoutError("probe timeout"))

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", t1, 10.0), ("tcp_rtu", t2, 5.0)],
        ),
        pytest.raises(TimeoutError),
    ):
        await scanner.verify_connection()


@pytest.mark.asyncio
async def test_verify_connection_cannot_connect_surfaces_error():
    """When both AUTO attempts fail to connect, verify_connection must raise."""
    scanner = await _make_scanner(port=8899, connection_mode="auto")

    t1 = _make_transport(ensure_side_effect=ConnectionException("refused"))
    t2 = _make_transport(ensure_side_effect=ConnectionException("refused"))

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", t1, 10.0), ("tcp_rtu", t2, 5.0)],
        ),
        pytest.raises(ConnectionException),
    ):
        await scanner.verify_connection()


@pytest.mark.asyncio
async def test_verify_connection_modbus_io_cancelled_raises_timeout_in_auto():
    """ModbusIOException 'cancelled' during AUTO probing must propagate as TimeoutError."""
    scanner = await _make_scanner(port=8899, connection_mode="auto")

    t1 = _make_transport(ensure_side_effect=ModbusIOException("Request cancelled outside pymodbus"))
    t2 = _make_transport(ensure_side_effect=ModbusIOException("Request cancelled outside pymodbus"))

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", t1, 10.0), ("tcp_rtu", t2, 5.0)],
        ),
        pytest.raises(TimeoutError),
    ):
        await scanner.verify_connection()
