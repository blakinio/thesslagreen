# mypy: ignore-errors
"""Risk-focused coverage for connection and coordinator lifecycle helpers."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    device_info,
)
from custom_components.thessla_green_modbus.coordinator import (
    update as update_module,
)
from custom_components.thessla_green_modbus.core import connection, connection_lifecycle
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymodbus.exceptions import ConnectionException, ModbusException


class _AsyncCloseScanner:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.closed = False

    def scan_device(self):
        if self.error is not None:
            raise self.error
        return self.result

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_run_device_scan_sync_and_async_results_and_errors() -> None:
    logger = Mock()
    applied = Mock()

    scanner = _AsyncCloseScanner({"register_count": 1})
    await device_info.run_device_scan(
        create_scanner=AsyncMock(return_value=scanner),
        apply_scan_result=applied,
        logger=logger,
    )
    applied.assert_called_once_with({"register_count": 1})
    assert scanner.closed is True

    async_scanner = SimpleNamespace(
        scan_device=AsyncMock(return_value={"register_count": 2}),
        close=Mock(return_value=None),
    )
    await device_info.run_device_scan(
        create_scanner=AsyncMock(return_value=async_scanner),
        apply_scan_result=applied,
        logger=logger,
    )
    async_scanner.scan_device.assert_awaited_once_with()
    async_scanner.close.assert_called_once_with()

    for error in (
        ModbusException("modbus"),
        ConnectionException("connection"),
        TimeoutError("timeout"),
        OSError("os"),
        ValueError("value"),
    ):
        failing = _AsyncCloseScanner(error=error)
        with pytest.raises(type(error)):
            await device_info.run_device_scan(
                create_scanner=AsyncMock(return_value=failing),
                apply_scan_result=Mock(),
                logger=logger,
            )
        assert failing.closed is True

    with pytest.raises(asyncio.CancelledError):
        await device_info.run_device_scan(
            create_scanner=AsyncMock(side_effect=asyncio.CancelledError()),
            apply_scan_result=Mock(),
            logger=logger,
        )


def test_warn_missing_device_info_all_missing_fields_and_slave_shapes() -> None:
    logger = Mock()
    config = SimpleNamespace(host="192.0.2.10", port=502, slave_id=None)
    device_info.warn_missing_device_info(
        device_info={"model": "Known", "firmware": "4.85"},
        config=config,
        device_name="AirPack",
        logger=logger,
        unknown_model="Unknown",
    )
    logger.debug.assert_not_called()

    device_info.warn_missing_device_info(
        device_info={"model": "Unknown", "firmware": "Unknown"},
        config=config,
        device_name="AirPack",
        logger=logger,
        unknown_model="Unknown",
    )
    assert logger.debug.call_count == 3

    logger.reset_mock()
    config.slave_id = 10
    device_info.warn_missing_device_info(
        device_info={"model": "Unknown", "firmware": "Unknown"},
        config=config,
        device_name="AirPack",
        logger=logger,
        unknown_model="Unknown",
    )
    assert logger.debug.call_count == 3


class _Transport:
    def __init__(self, states):
        self._states = iter(states)
        self.client = object()
        self.close = AsyncMock()

    def is_connected(self):
        return next(self._states)

    async def ensure_connected(self):
        return None


@pytest.mark.asyncio
async def test_run_update_cycle_connection_guards_and_reconnect() -> None:
    start = update_module._utcnow()

    disconnected = _Transport([False])
    coordinator = SimpleNamespace(
        _ensure_connection=AsyncMock(),
        device_client=SimpleNamespace(
            _transport=disconnected,
            client=object(),
            _read_all_register_data=AsyncMock(return_value={}),
        ),
    )
    with pytest.raises(ConnectionException, match="transport is not connected"):
        await update_module.run_update_cycle(coordinator, start)

    coordinator.device_client._transport = None
    coordinator.device_client.client = None
    with pytest.raises(ConnectionException, match="client is not connected"):
        await update_module.run_update_cycle(coordinator, start)

    reconnecting = _Transport([True, False, True])
    coordinator.device_client._transport = reconnecting
    coordinator.device_client.client = object()
    coordinator.device_client._read_all_register_data = AsyncMock(return_value={"x": 1})
    with patch.object(update_module, "apply_success_result", return_value={"ok": True}) as apply:
        assert await update_module.run_update_cycle(coordinator, start) == {"ok": True}
    assert coordinator._ensure_connection.await_count >= 2
    apply.assert_called_once_with(coordinator, start_time=start, data={"x": 1})

    failed_reconnect = _Transport([True, False, False])
    coordinator.device_client._transport = failed_reconnect
    coordinator.device_client._read_all_register_data = AsyncMock(return_value={})
    with pytest.raises(ConnectionException, match="transport is not connected"):
        await update_module.run_update_cycle(coordinator, start)


@pytest.mark.asyncio
async def test_async_update_data_shutdown_and_unexpected_error_path() -> None:
    coordinator = SimpleNamespace(
        _shutting_down=True,
        data={"cached": 1},
        device_client=SimpleNamespace(_write_lock=asyncio.Lock()),
    )
    assert await update_module.async_update_data(coordinator) == {"cached": 1}

    coordinator._shutting_down = False
    mapped = UpdateFailed("mapped")
    with (
        patch.object(update_module, "begin_update_cycle", return_value=None),
        patch.object(update_module, "finish_update_cycle") as finish,
        patch.object(
            update_module,
            "run_update_cycle",
            new=AsyncMock(side_effect=OSError("boom")),
        ),
        patch.object(
            update_module,
            "handle_update_error",
            new=AsyncMock(return_value=mapped),
        ) as handle,
    ):
        with pytest.raises(UpdateFailed, match="mapped"):
            await update_module.async_update_data(coordinator)
    handle.assert_awaited_once()
    assert handle.call_args.kwargs["use_helper"] is False
    finish.assert_called_once_with(coordinator)


@pytest.mark.asyncio
async def test_reconnect_client_if_needed_all_runtime_shapes() -> None:
    assert await connection.reconnect_client_if_needed(SimpleNamespace(connected=True)) is True
    assert await connection.reconnect_client_if_needed(SimpleNamespace(connected=False)) is False

    sync_client = SimpleNamespace(connected=False, connect=Mock(return_value=True))
    assert await connection.reconnect_client_if_needed(sync_client) is True
    assert sync_client.connected is True

    async_client = SimpleNamespace(connected=False, connect=AsyncMock(return_value=False))
    assert await connection.reconnect_client_if_needed(async_client) is False
    async_client.connect.assert_awaited_once_with()

    sets_connected = SimpleNamespace(connected=False)

    def _connect():
        sets_connected.connected = True
        return False

    sets_connected.connect = _connect
    assert await connection.reconnect_client_if_needed(sets_connected) is True


def test_transport_builders_forward_runtime_settings() -> None:
    with patch.object(connection, "RtuModbusTransport", return_value="rtu") as rtu_cls:
        assert connection.build_rtu_transport(
            serial_port="/dev/ttyUSB0",
            baudrate=9600,
            parity="N",
            stopbits=1,
            retry=2,
            backoff=0.1,
            max_backoff=1.0,
            timeout=2.0,
            offline_state=False,
        ) == "rtu"
    assert rtu_cls.call_args.kwargs["max_retries"] == 2

    with (
        patch.object(connection, "RawRtuOverTcpTransport", return_value="raw") as raw_cls,
        patch.object(connection, "TcpModbusTransport", return_value="tcp") as tcp_cls,
    ):
        common = dict(
            host="host",
            port=502,
            retry=2,
            backoff=0.1,
            max_backoff=1.0,
            timeout=2.0,
            offline_state=False,
            connection_type_tcp="tcp",
            connection_mode_tcp_rtu="tcp_rtu",
        )
        assert connection.build_tcp_transport(mode="tcp_rtu", **common) == "raw"
        assert connection.build_tcp_transport(mode="tcp", **common) == "tcp"
    raw_cls.assert_called_once()
    tcp_cls.assert_called_once()


@pytest.mark.asyncio
async def test_connect_direct_tcp_client_constructor_and_connect_shapes() -> None:
    class Parameterless:
        def __init__(self, *args, **kwargs):
            if args:
                raise TypeError("parameterless")
            self.connected = False

        async def connect(self):
            return True

    client = await connection.connect_direct_tcp_client(
        host="host",
        port=502,
        timeout=1.0,
        tcp_client_cls=Parameterless,
        allow_parameterless_ctor=True,
    )
    assert client is not None
    assert client.host == "host"
    assert client.port == 502

    class NoConnect:
        def __init__(self, host, *, port, timeout):
            self.connected = False

    client = await connection.connect_direct_tcp_client(
        host="host",
        port=502,
        timeout=1.0,
        tcp_client_cls=NoConnect,
        allow_parameterless_ctor=False,
    )
    assert client is not None
    assert client.connected is True

    class FailedConnect:
        def __init__(self, host, *, port, timeout):
            self.connected = False

        def connect(self):
            return False

    assert (
        await connection.connect_direct_tcp_client(
            host="host",
            port=502,
            timeout=1.0,
            tcp_client_cls=FailedConnect,
            allow_parameterless_ctor=False,
        )
        is None
    )


@pytest.mark.asyncio
async def test_setup_client_with_retry_normalizes_expected_failures() -> None:
    logger = Mock()
    assert (
        await connection.setup_client_with_retry(
            ensure_connection=AsyncMock(return_value=None), logger=logger
        )
        is True
    )
    for error in (
        ModbusException("modbus"),
        ConnectionException("connection"),
        TimeoutError("timeout"),
        OSError("os"),
    ):
        assert (
            await connection.setup_client_with_retry(
                ensure_connection=AsyncMock(side_effect=error), logger=logger
            )
            is False
        )


@pytest.mark.asyncio
async def test_ensure_transport_selected_all_selection_paths() -> None:
    current = object()
    common = dict(
        connection_type="tcp",
        connection_mode="tcp",
        host="host",
        port=502,
        serial_port="/dev/ttyUSB0",
        baudrate=9600,
        parity="N",
        stopbits=1,
        retry=1,
        backoff=0.1,
        max_backoff=1.0,
        timeout=1.0,
        offline_state=False,
        connection_type_rtu="rtu",
        connection_mode_auto="auto",
        connection_mode_tcp="tcp",
        build_rtu_transport_fn=Mock(return_value="rtu-transport"),
        build_tcp_transport_fn=Mock(return_value="tcp-transport"),
        select_auto_transport_fn=AsyncMock(return_value=("auto-transport", "tcp_rtu")),
    )
    assert await connection.ensure_transport_selected(
        current_transport=current, **common
    ) == (current, None)

    rtu = dict(common)
    rtu["connection_type"] = "rtu"
    assert await connection.ensure_transport_selected(
        current_transport=None, **rtu
    ) == ("rtu-transport", None)

    auto = dict(common)
    auto["connection_mode"] = "auto"
    assert await connection.ensure_transport_selected(
        current_transport=None, **auto
    ) == ("auto-transport", "tcp_rtu")

    no_mode = dict(common)
    no_mode["connection_mode"] = None
    assert await connection.ensure_transport_selected(
        current_transport=None, **no_mode
    ) == ("tcp-transport", "tcp")


@pytest.mark.asyncio
async def test_connect_transport_or_client_guards_disconnected_states() -> None:
    transport = _Transport([False])
    with pytest.raises(ConnectionException, match="transport is not connected"):
        await connection.connect_transport_or_client(transport=transport, client=None)
    with pytest.raises(ConnectionException, match="not available"):
        await connection.connect_transport_or_client(transport=None, client=None)
    client = object()
    assert await connection.connect_transport_or_client(transport=None, client=client) is client


@pytest.mark.asyncio
async def test_ensure_connected_runtime_fast_paths_success_and_failures() -> None:
    connected = _Transport([True])
    client = object()
    noop = AsyncMock()
    assert await connection.ensure_connected_runtime(
        current_transport=connected,
        current_client=client,
        reconnect_client_if_needed_fn=AsyncMock(),
        disconnect_locked_fn=noop,
        get_runtime_state_fn=Mock(),
        ensure_transport_selected_fn=AsyncMock(),
        connect_transport_or_client_fn=AsyncMock(),
        mark_connection_established_fn=Mock(),
        mark_connection_failure_fn=Mock(),
        logger=Mock(),
    ) == (connected, client, None)

    reconnect = AsyncMock(return_value=True)
    assert await connection.ensure_connected_runtime(
        current_transport=None,
        current_client=client,
        reconnect_client_if_needed_fn=reconnect,
        disconnect_locked_fn=noop,
        get_runtime_state_fn=Mock(),
        ensure_transport_selected_fn=AsyncMock(),
        connect_transport_or_client_fn=AsyncMock(),
        mark_connection_established_fn=Mock(),
        mark_connection_failure_fn=Mock(),
        logger=Mock(),
    ) == (None, client, None)
    reconnect.assert_awaited_once_with(client)

    state = [None, None]
    selected = object()
    established = Mock()
    result = await connection.ensure_connected_runtime(
        current_transport=None,
        current_client=None,
        reconnect_client_if_needed_fn=AsyncMock(return_value=False),
        disconnect_locked_fn=AsyncMock(),
        get_runtime_state_fn=Mock(return_value=tuple(state)),
        ensure_transport_selected_fn=AsyncMock(return_value=(selected, "tcp_rtu")),
        connect_transport_or_client_fn=AsyncMock(return_value="client"),
        mark_connection_established_fn=established,
        mark_connection_failure_fn=Mock(),
        logger=Mock(),
    )
    assert result == (selected, "client", "tcp_rtu")
    established.assert_called_once_with()

    for error in (
        ConnectionException("connection"),
        ModbusException("modbus"),
        TimeoutError("timeout"),
        OSError("os"),
    ):
        failure = Mock()
        with pytest.raises(type(error)):
            await connection.ensure_connected_runtime(
                current_transport=None,
                current_client=None,
                reconnect_client_if_needed_fn=AsyncMock(return_value=False),
                disconnect_locked_fn=AsyncMock(),
                get_runtime_state_fn=Mock(return_value=(None, None)),
                ensure_transport_selected_fn=AsyncMock(return_value=(None, None)),
                connect_transport_or_client_fn=AsyncMock(side_effect=error),
                mark_connection_established_fn=Mock(),
                mark_connection_failure_fn=failure,
                logger=Mock(),
            )
        failure.assert_called_once_with()


@pytest.mark.asyncio
async def test_connection_lifecycle_state_close_and_disconnect_paths() -> None:
    setter = Mock()
    statistics = {"connection_errors": 0}
    connection_lifecycle.mark_connection_established(offline_state_setter=setter)
    connection_lifecycle.mark_connection_failure(
        statistics=statistics, offline_state_setter=setter
    )
    connection_lifecycle.mark_connection_disconnected(offline_state_setter=setter)
    assert statistics["connection_errors"] == 1
    assert setter.call_args_list == [
        ((False,),),
        ((True,),),
        ((True,),),
    ]

    logger = Mock()
    sync_client = SimpleNamespace(close=Mock(return_value=None))
    await connection_lifecycle.close_client_connection(client=sync_client, logger=logger)
    sync_client.close.assert_called_once_with()

    async_client = SimpleNamespace(close=AsyncMock(return_value=None))
    await connection_lifecycle.close_client_connection(client=async_client, logger=logger)
    async_client.close.assert_awaited_once_with()

    future = asyncio.get_running_loop().create_future()
    future.set_result(None)
    awaitable_client = SimpleNamespace(close=Mock(return_value=future))
    await connection_lifecycle.close_client_connection(client=awaitable_client, logger=logger)

    for error in (ModbusException("modbus"), ConnectionException("connection"), OSError("os")):
        failing = SimpleNamespace(close=Mock(side_effect=error))
        await connection_lifecycle.close_client_connection(client=failing, logger=logger)

    marked = Mock()
    transport = SimpleNamespace(close=AsyncMock(side_effect=OSError("close")))
    await connection_lifecycle.disconnect_locked(
        transport=transport,
        client=None,
        close_client_connection_fn=AsyncMock(),
        mark_connection_disconnected_fn=marked,
        logger=logger,
    )
    marked.assert_called_once_with()

    marked.reset_mock()
    close_client = AsyncMock()
    await connection_lifecycle.disconnect_locked(
        transport=None,
        client=object(),
        close_client_connection_fn=close_client,
        mark_connection_disconnected_fn=marked,
        logger=logger,
    )
    close_client.assert_awaited_once()
    marked.assert_called_once_with()
