# mypy: ignore-errors
"""Exercise remaining diagnostics service response and isolation branches."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.services import handlers_data
from homeassistant.exceptions import HomeAssistantError
from pymodbus.exceptions import ConnectionException


def test_modbus_response_helpers_all_shapes() -> None:
    assert handlers_data._response_has_data(None) is False
    assert handlers_data._response_has_data(SimpleNamespace(registers=[1], bits=[])) is True
    assert handlers_data._response_has_data(SimpleNamespace(registers=[], bits=[True])) is True
    assert handlers_data._response_has_data(SimpleNamespace(registers=[], bits=[])) is False

    assert handlers_data._response_is_modbus_error(None) is False
    assert handlers_data._response_is_modbus_error(SimpleNamespace()) is False
    assert handlers_data._response_is_modbus_error(SimpleNamespace(isError=lambda: True)) is True
    assert handlers_data._response_is_modbus_error(
        SimpleNamespace(isError=lambda: (_ for _ in ()).throw(TypeError("bad")))
    ) is False


@pytest.mark.asyncio
async def test_read_batch_existing_client_routes_and_unknown_type() -> None:
    fn = AsyncMock()
    client = SimpleNamespace(
        _get_client_method=Mock(return_value=fn),
        _call_modbus=AsyncMock(return_value="ok"),
    )
    for reg_type, expected_method in (
        ("input_registers", "read_input_registers"),
        ("holding_registers", "read_holding_registers"),
        ("coil_registers", "read_coils"),
        ("discrete_inputs", "read_discrete_inputs"),
    ):
        assert await handlers_data._read_batch_via_existing_client(client, reg_type, 1, 2) == "ok"
        client._get_client_method.assert_called_with(expected_method)
    with pytest.raises(ValueError, match="Unknown register type"):
        await handlers_data._read_batch_via_existing_client(client, "unknown", 1, 1)


@pytest.mark.asyncio
async def test_known_register_validation_classifies_batch_and_individual_outcomes() -> None:
    lock = asyncio.Lock()
    dc = SimpleNamespace(
        _write_lock=lock,
        _register_maps={"input_registers": {"a": 1, "b": 2, "c": 3, "d": 4}},
    )
    coordinator = SimpleNamespace(device_client=dc, _ensure_connection=AsyncMock())
    response_error = SimpleNamespace(registers=[], bits=[], isError=lambda: True)
    response_empty = SimpleNamespace(registers=[], bits=[], isError=lambda: False)
    response_data = SimpleNamespace(registers=[1], bits=[], isError=lambda: False)
    with (
        patch.object(handlers_data, "group_reads", return_value=[(1, 4)]),
        patch.object(
            handlers_data,
            "_read_batch_via_existing_client",
            new=AsyncMock(
                side_effect=[
                    response_error,
                    response_data,
                    response_error,
                    response_empty,
                    ConnectionException("offline"),
                ]
            ),
        ),
    ):
        available, missing, indeterminate, faults, retried = (
            await handlers_data._read_known_registers_safe(coordinator, 4, 0)
        )
    assert available["input_registers"] == {"a"}
    assert missing["input_registers"] == {"b"}
    assert indeterminate["input_registers"] == {"c", "d"}
    assert faults["input_registers"][0]["error"] == "modbus_error_response"
    assert retried == 4
    coordinator._ensure_connection.assert_awaited_once()


@pytest.mark.asyncio
async def test_known_register_validation_batch_success_and_delay() -> None:
    dc = SimpleNamespace(
        _write_lock=asyncio.Lock(),
        _register_maps={"holding_registers": {"x": 10}},
    )
    coordinator = SimpleNamespace(device_client=dc, _ensure_connection=AsyncMock())
    response = SimpleNamespace(registers=[1], bits=[], isError=lambda: False)
    with (
        patch.object(handlers_data, "group_reads", return_value=[(10, 1)]),
        patch.object(handlers_data, "_read_batch_via_existing_client", new=AsyncMock(return_value=response)),
        patch.object(handlers_data.asyncio, "sleep", new=AsyncMock()) as sleep,
    ):
        available, *_ = await handlers_data._read_known_registers_safe(coordinator, 1, 1)
    assert available["holding_registers"] == {"x"}
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_isolated_scan_success_scan_failure_close_failure_and_restore_failure() -> None:
    cfg = SimpleNamespace(
        host="host", port=502, slave_id=10, connection_type="tcp", connection_mode="tcp",
        serial_port="", baud_rate=9600, parity="none", stop_bits=1,
    )
    dc = SimpleNamespace(
        config=cfg,
        _write_lock=asyncio.Lock(),
        timeout=1,
        retry=1,
        scan_uart_settings=False,
        async_disconnect=AsyncMock(),
        async_ensure_connected=AsyncMock(),
    )
    coordinator = SimpleNamespace(device_client=dc)
    scanner = SimpleNamespace(scan_device=AsyncMock(return_value={"ok": 1}), close=AsyncMock())
    deps = SimpleNamespace(scanner_create=AsyncMock(return_value=scanner))
    assert await handlers_data._scan_with_polling_paused(
        object(), coordinator, deps, batch=4, delay_ms=0, known_registers_only=True
    ) == {"ok": 1}
    dc.async_disconnect.assert_awaited_once()
    scanner.close.assert_awaited_once()
    dc.async_ensure_connected.assert_awaited_once()

    scanner.scan_device = AsyncMock(side_effect=RuntimeError("scan"))
    scanner.close = AsyncMock(side_effect=RuntimeError("close"))
    dc.async_ensure_connected = AsyncMock()
    with pytest.raises(HomeAssistantError, match="Register scan failed"):
        await handlers_data._scan_with_polling_paused(
            object(), coordinator, deps, batch=4, delay_ms=0, known_registers_only=False
        )

    scanner.scan_device = AsyncMock(return_value={})
    scanner.close = AsyncMock()
    dc.async_ensure_connected = AsyncMock(side_effect=ConnectionException("restore"))
    with pytest.raises(HomeAssistantError, match="could not be restored"):
        await handlers_data._scan_with_polling_paused(
            object(), coordinator, deps, batch=4, delay_ms=0, known_registers_only=True
        )


@pytest.mark.asyncio
async def test_isolated_scan_cancellation_propagates_through_scan_and_restore() -> None:
    cfg = SimpleNamespace(
        host="host", port=502, slave_id=10, connection_type="tcp", connection_mode="tcp",
        serial_port="", baud_rate=9600, parity="none", stop_bits=1,
    )
    dc = SimpleNamespace(
        config=cfg,
        _write_lock=asyncio.Lock(), timeout=1, retry=1, scan_uart_settings=False,
        async_disconnect=AsyncMock(), async_ensure_connected=AsyncMock(),
    )
    coordinator = SimpleNamespace(device_client=dc)
    scanner = SimpleNamespace(scan_device=AsyncMock(side_effect=asyncio.CancelledError()), close=AsyncMock())
    deps = SimpleNamespace(scanner_create=AsyncMock(return_value=scanner))
    with pytest.raises(asyncio.CancelledError):
        await handlers_data._scan_with_polling_paused(
            object(), coordinator, deps, batch=1, delay_ms=0, known_registers_only=True
        )
