"""Tests for transport reset before scanner fallback after cancelled batch read.

Root cause: when a Modbus TCP batch read is cancelled/timed out, the underlying
TCP connection may carry a stale in-flight response. If the scanner immediately
reuses the same connection for individual fallback probes, pymodbus may receive
the late response from the old request and log a transaction_id mismatch:
  "request ask for transaction_id=55 but got id=54, Skipping"

Fix: before individual fallback probes start, close and reconnect the transport.
This ensures pymodbus starts with a clean transaction ID sequence.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.scanner.registers import (
    _reset_transport_before_fallback,
    scan_register_batch,
)


def _make_scanner(*, transport=None, client=None, retry=3):
    """Build a minimal scanner mock for register scan tests."""
    scanner = MagicMock()
    scanner.retry = retry
    scanner.backoff = 0
    scanner.backoff_jitter = None
    scanner.slave_id = 1
    scanner._transport = transport
    scanner._client = client
    scanner.failed_addresses = {
        "modbus_exceptions": {
            "holding_registers": set(),
            "input_registers": set(),
            "invalid_values": {},
        },
        "invalid_values": {
            "holding_registers": set(),
            "input_registers": set(),
        },
        "batch_failures": {
            "holding_registers": set(),
            "input_registers": set(),
        },
    }
    scanner.available_registers = {"holding_registers": set(), "input_registers": set()}
    scanner._group_registers_for_batch_read = MagicMock(return_value=[(4262, 3)])
    scanner._is_valid_register_value = MagicMock(return_value=True)
    scanner._log_invalid_value = MagicMock()
    return scanner


def _make_transport(*, close_raises=None, ensure_raises=None, client=None):
    """Build a minimal transport mock."""
    transport = MagicMock()
    transport.close = AsyncMock(side_effect=close_raises) if close_raises else AsyncMock()
    transport.ensure_connected = (
        AsyncMock(side_effect=ensure_raises) if ensure_raises else AsyncMock()
    )
    transport.client = client if client is not None else MagicMock(name="transport_client")
    return transport


@pytest.mark.asyncio
async def test_scanner_reconnects_before_fallback_after_cancelled_batch():
    """Batch read failure triggers transport reset before individual fallback probes."""
    new_client = MagicMock(name="new_client")
    transport = _make_transport(client=new_client)
    old_client = MagicMock(name="old_client")
    scanner = _make_scanner(transport=transport, client=old_client)

    addr_to_names = {4262: {"reg_a"}, 4263: {"reg_b"}, 4264: {"reg_c"}}

    async def read_fn(start, count, *, skip_cache=False):
        if count > 1:
            return None
        return [42]

    await scan_register_batch(
        scanner, "holding_registers", addr_to_names, [4262, 4263, 4264], read_fn
    )

    transport.close.assert_awaited_once()
    transport.ensure_connected.assert_awaited_once()
    assert scanner._client is new_client, (
        "scanner._client must be updated to the new transport.client after reconnect"
    )


@pytest.mark.asyncio
async def test_scanner_cancelled_batch_fallback_success_has_no_error_log(caplog):
    """No ERROR is logged when batch read fails but individual fallback succeeds."""
    transport = _make_transport()
    scanner = _make_scanner(transport=transport)

    addr_to_names = {4262: {"reg_a"}}
    scanner._group_registers_for_batch_read = MagicMock(return_value=[(4262, 1)])

    async def read_fn(start, count, *, skip_cache=False):
        if not skip_cache:
            return None
        return [42]

    with caplog.at_level(logging.ERROR):
        await scan_register_batch(scanner, "holding_registers", addr_to_names, [4262], read_fn)

    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert not error_records, f"Unexpected ERROR log entries: {[r.message for r in error_records]}"


@pytest.mark.asyncio
async def test_scanner_successful_batch_does_not_reset_transport():
    """A successful batch read must NOT trigger transport close or reconnect."""
    transport = _make_transport()
    scanner = _make_scanner(transport=transport)

    addr_to_names = {4262: {"reg_a"}, 4263: {"reg_b"}}
    scanner._group_registers_for_batch_read = MagicMock(return_value=[(4262, 2)])

    async def read_fn(start, count, *, skip_cache=False):
        return [42, 43]

    await scan_register_batch(scanner, "holding_registers", addr_to_names, [4262, 4263], read_fn)

    transport.close.assert_not_awaited()
    transport.ensure_connected.assert_not_awaited()


@pytest.mark.asyncio
async def test_scanner_fallback_failure_still_logs_failure(caplog):
    """When both batch and individual fallback fail, failures are still reported."""
    transport = _make_transport()
    scanner = _make_scanner(transport=transport)

    addr_to_names = {4262: {"reg_a"}}
    scanner._group_registers_for_batch_read = MagicMock(return_value=[(4262, 1)])

    async def read_fn(start, count, *, skip_cache=False):
        return None

    with caplog.at_level(logging.WARNING):
        await scan_register_batch(scanner, "holding_registers", addr_to_names, [4262], read_fn)

    messages = [r.message for r in caplog.records]
    assert any("failed" in msg.lower() or "probing" in msg.lower() for msg in messages), (
        f"Expected failure/probing log entry, got: {messages}"
    )


@pytest.mark.asyncio
async def test_scanner_fallback_probe_uses_new_connection_not_old():
    """After cancelled batch, individual probes must see the updated scanner._client.

    This is the key regression test: after transport reset scanner._client must
    be the new connection object, not the old stale one that may carry a pending
    pymodbus transaction response.
    """
    old_client = MagicMock(name="old_client")
    new_client = MagicMock(name="new_client")
    transport = _make_transport(client=new_client)
    scanner = _make_scanner(transport=transport, client=old_client)

    addr_to_names = {4262: {"reg_a"}}
    scanner._group_registers_for_batch_read = MagicMock(return_value=[(4262, 1)])

    client_at_probe_time: list = []

    async def read_fn(start, count, *, skip_cache=False):
        if not skip_cache:
            return None
        client_at_probe_time.append(scanner._client)
        return [42]

    await scan_register_batch(scanner, "holding_registers", addr_to_names, [4262], read_fn)

    assert len(client_at_probe_time) >= 1, "Individual probe must have been called"
    assert old_client not in client_at_probe_time, (
        "Individual probe used the old (potentially stale) connection object; "
        "expected the new connection after transport reset"
    )
    assert new_client in client_at_probe_time, (
        "Individual probe must use the new transport.client after reset"
    )


@pytest.mark.asyncio
async def test_scanner_no_transport_fallback_does_not_raise():
    """When scanner has no transport, fallback probes still run without error."""
    scanner = _make_scanner(transport=None, client=None)

    addr_to_names = {4262: {"reg_a"}}
    scanner._group_registers_for_batch_read = MagicMock(return_value=[(4262, 1)])

    async def read_fn(start, count, *, skip_cache=False):
        if not skip_cache:
            return None
        return [42]

    await scan_register_batch(scanner, "holding_registers", addr_to_names, [4262], read_fn)

    assert "reg_a" in scanner.available_registers["holding_registers"]


@pytest.mark.asyncio
async def test_reset_transport_before_fallback_no_transport_is_noop():
    """_reset_transport_before_fallback is a no-op when scanner has no transport."""
    scanner = _make_scanner(transport=None, client=MagicMock())
    original_client = scanner._client

    await _reset_transport_before_fallback(scanner, "holding_registers", 4262, 4264)

    assert scanner._client is original_client, "Client must not change when no transport present"


@pytest.mark.asyncio
async def test_reset_transport_before_fallback_updates_client():
    """_reset_transport_before_fallback closes transport and updates scanner._client."""
    new_client = MagicMock(name="new_client")
    transport = _make_transport(client=new_client)
    scanner = _make_scanner(transport=transport, client=MagicMock(name="old"))

    await _reset_transport_before_fallback(scanner, "holding_registers", 4262, 4264)

    transport.close.assert_awaited_once()
    transport.ensure_connected.assert_awaited_once()
    assert scanner._client is new_client


@pytest.mark.asyncio
async def test_reset_transport_before_fallback_close_exception_handled(caplog):
    """close() exception during reset is caught and logged at DEBUG, not propagated."""
    transport = _make_transport(close_raises=OSError("close failed"))
    scanner = _make_scanner(transport=transport)

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.thessla_green_modbus.scanner.registers"
    ):
        await _reset_transport_before_fallback(scanner, "holding_registers", 4262, 4264)

    assert any(
        "close" in r.message.lower() and r.levelno == logging.DEBUG for r in caplog.records
    ), "close() exception should be logged at DEBUG level"
    transport.ensure_connected.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_transport_before_fallback_ensure_connected_exception_handled(caplog):
    """ensure_connected() exception during reset is caught and logged at DEBUG."""
    transport = _make_transport(ensure_raises=OSError("connect failed"))
    scanner = _make_scanner(transport=transport)

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.thessla_green_modbus.scanner.registers"
    ):
        await _reset_transport_before_fallback(scanner, "holding_registers", 4262, 4264)

    assert any(
        "reconnect" in r.message.lower() and r.levelno == logging.DEBUG for r in caplog.records
    ), "ensure_connected() exception should be logged at DEBUG level"
