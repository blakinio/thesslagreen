"""Contract tests for safe diagnostics service behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus.services.handlers_data import (
    _read_known_registers_safe,
    _scan_with_polling_paused,
)
from pymodbus.exceptions import ConnectionException


class _AsyncLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_isolated_scan_disconnects_and_restores_primary_transport() -> None:
    """Diagnostic scanner never overlaps the coordinator transport."""
    events: list[str] = []
    scanner = SimpleNamespace(
        scan_device=AsyncMock(side_effect=lambda: events.append("scan") or {"register_count": 1}),
        close=AsyncMock(side_effect=lambda: events.append("scanner_close")),
    )
    scanner_create = AsyncMock(
        side_effect=lambda **kwargs: events.append("scanner_create") or scanner
    )
    cfg = SimpleNamespace(
        host="127.0.0.1",
        port=502,
        slave_id=10,
        connection_type="tcp",
        connection_mode="tcp",
        serial_port="/dev/ttyUSB0",
        baud_rate=115200,
        parity="N",
        stop_bits=1,
    )
    dc = SimpleNamespace(
        _write_lock=_AsyncLock(),
        config=cfg,
        timeout=5,
        retry=3,
        scan_uart_settings=False,
        async_disconnect=AsyncMock(side_effect=lambda: events.append("disconnect")),
        async_ensure_connected=AsyncMock(side_effect=lambda: events.append("reconnect")),
    )
    coordinator = SimpleNamespace(device_client=dc)
    deps = SimpleNamespace(scanner_create=scanner_create)

    result = await _scan_with_polling_paused(
        SimpleNamespace(),
        coordinator,
        deps,
        batch=4,
        delay_ms=0,
        known_registers_only=False,
    )

    assert result == {"register_count": 1}
    assert events == ["disconnect", "scanner_create", "scan", "scanner_close", "reconnect"]
    kwargs = scanner_create.await_args.kwargs
    assert kwargs["connection_type"] == "tcp"
    assert kwargs["serial_port"] == "/dev/ttyUSB0"


@pytest.mark.asyncio
async def test_transport_failure_is_indeterminate_not_missing(monkeypatch) -> None:
    """A connection failure must never be reported as unsupported register."""
    dc = SimpleNamespace(
        _write_lock=_AsyncLock(),
        _register_maps={"holding_registers": {"known_register": 1}},
    )
    coordinator = SimpleNamespace(
        device_client=dc,
        _ensure_connection=AsyncMock(),
    )

    async def fail_read(*args, **kwargs):
        raise ConnectionException("offline")

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.services.handlers_data._read_batch_via_existing_client",
        fail_read,
    )

    available, missing, indeterminate, _failed, _retried = await _read_known_registers_safe(
        coordinator, 1, 0
    )

    assert available["holding_registers"] == set()
    assert missing["holding_registers"] == set()
    assert indeterminate["holding_registers"] == {"known_register"}
