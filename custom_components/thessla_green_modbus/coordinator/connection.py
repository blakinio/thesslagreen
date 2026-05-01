"""Connection helpers for coordinator runtime."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from ..modbus_exceptions import ConnectionException, ModbusException
from ..modbus_transport import (
    BaseModbusTransport,
    RawRtuOverTcpTransport,
    RtuModbusTransport,
    TcpModbusTransport,
)


async def reconnect_client_if_needed(client: Any) -> bool:
    """Try reconnecting an existing client instance if it has connect()."""

    if bool(getattr(client, "connected", False)):
        return True

    connect_method = getattr(client, "connect", None)
    if not callable(connect_method):
        return False

    connect_result = connect_method()
    if inspect.isawaitable(connect_result):
        connect_result = await connect_result
    if bool(connect_result) or bool(getattr(client, "connected", False)):
        client.connected = True
        return True
    return False


def build_rtu_transport(
    *,
    serial_port: str,
    baudrate: int,
    parity: str,
    stopbits: int,
    retry: int,
    backoff: float,
    max_backoff: float,
    timeout: float,
    offline_state: bool,
) -> RtuModbusTransport:
    """Build RTU transport with coordinator runtime settings."""

    return RtuModbusTransport(
        serial_port=serial_port,
        baudrate=baudrate,
        parity=parity,
        stopbits=stopbits,
        max_retries=retry,
        base_backoff=backoff,
        max_backoff=max_backoff,
        timeout=timeout,
        offline_state=offline_state,
    )


async def connect_direct_tcp_client(
    *,
    host: str,
    port: int,
    timeout: float,
    tcp_client_cls: Any,
    allow_parameterless_ctor: bool,
) -> Any | None:
    """Try direct AsyncModbusTcpClient connect and return connected client."""

    if allow_parameterless_ctor:
        try:
            direct_client = tcp_client_cls(host, port=port, timeout=timeout)
        except TypeError:
            direct_client = tcp_client_cls()
            direct_client.host = host
            direct_client.port = port
    else:
        direct_client = tcp_client_cls(host, port=port, timeout=timeout)

    connect_method = getattr(direct_client, "connect", None)
    if callable(connect_method):
        connect_result = connect_method()
        if inspect.isawaitable(connect_result):
            connect_result = await connect_result
    else:
        connect_result = True
        direct_client.connected = True

    if bool(connect_result) or bool(getattr(direct_client, "connected", False)):
        return direct_client
    return None


def build_tcp_transport(
    *,
    mode: str,
    host: str,
    port: int,
    retry: int,
    backoff: float,
    max_backoff: float,
    timeout: float,
    offline_state: bool,
    connection_type_tcp: str,
    connection_mode_tcp_rtu: str,
) -> BaseModbusTransport:
    """Build TCP or RTU-over-TCP transport for coordinator runtime settings."""

    if mode == connection_mode_tcp_rtu:
        return RawRtuOverTcpTransport(
            host=host,
            port=port,
            max_retries=retry,
            base_backoff=backoff,
            max_backoff=max_backoff,
            timeout=timeout,
            offline_state=offline_state,
        )
    return TcpModbusTransport(
        host=host,
        port=port,
        connection_type=connection_type_tcp,
        max_retries=retry,
        base_backoff=backoff,
        max_backoff=max_backoff,
        timeout=timeout,
        offline_state=offline_state,
    )


async def setup_client_with_retry(*, ensure_connection: Any, logger: logging.Logger) -> bool:
    """Set up Modbus client and normalize transient setup failures."""

    try:
        await ensure_connection()
        return True
    except (ModbusException, ConnectionException) as exc:
        logger.exception("Failed to set up Modbus client: %s", exc)
        return False
    except TimeoutError as exc:
        logger.warning("Setting up Modbus client timed out: %s", exc)
        return False
    except OSError as exc:
        logger.exception("Unexpected error setting up Modbus client: %s", exc)
        return False


async def ensure_transport_selected(
    *,
    current_transport: BaseModbusTransport | None,
    connection_type: str,
    connection_mode: str | None,
    host: str,
    port: int,
    serial_port: str,
    baudrate: int,
    parity: str,
    stopbits: int,
    retry: int,
    backoff: float,
    max_backoff: float,
    timeout: float,
    offline_state: bool,
    connection_type_rtu: str,
    connection_mode_auto: str,
    connection_mode_tcp: str,
    build_rtu_transport_fn: Callable[..., RtuModbusTransport],
    build_tcp_transport_fn: Callable[[str], BaseModbusTransport],
    select_auto_transport_fn: Callable[
        [], Awaitable[tuple[BaseModbusTransport | None, str | None]]
    ],
) -> tuple[BaseModbusTransport | None, str | None]:
    """Ensure transport instance exists and resolve mode for AUTO when needed."""

    if current_transport is not None:
        return current_transport, None

    if connection_type == connection_type_rtu:
        return (
            build_rtu_transport_fn(
                serial_port=serial_port,
                baudrate=baudrate,
                parity=parity,
                stopbits=stopbits,
                retry=retry,
                backoff=backoff,
                max_backoff=max_backoff,
                timeout=timeout,
                offline_state=offline_state,
            ),
            None,
        )

    if connection_mode == connection_mode_auto:
        return await select_auto_transport_fn()

    mode = connection_mode or connection_mode_tcp
    return build_tcp_transport_fn(mode), mode


async def connect_transport_or_client(
    *,
    transport: BaseModbusTransport | None,
    client: Any,
) -> Any:
    """Ensure transport/client is connected and return active client handle."""

    if transport is not None:
        await transport.ensure_connected()
        resolved_client = getattr(transport, "client", None)
        if not transport.is_connected():
            raise ConnectionException("Modbus transport is not connected")
        return resolved_client
    if client is None:
        raise ConnectionException("Modbus transport is not available")
    return client


async def ensure_connected_runtime(
    *,
    current_transport: BaseModbusTransport | None,
    current_client: Any,
    reconnect_client_if_needed_fn: Callable[[Any], Awaitable[bool]],
    disconnect_locked_fn: Callable[[], Awaitable[None]],
    get_runtime_state_fn: Callable[[], tuple[BaseModbusTransport | None, Any]],
    ensure_transport_selected_fn: Callable[
        [], Awaitable[tuple[BaseModbusTransport | None, str | None]]
    ],
    connect_transport_or_client_fn: Callable[..., Awaitable[Any]],
    mark_connection_established_fn: Callable[[], None],
    mark_connection_failure_fn: Callable[[], None],
    logger: logging.Logger,
) -> tuple[BaseModbusTransport | None, Any, str | None]:
    """Orchestrate coordinator connection/reconnect transitions."""

    if current_transport is not None and current_transport.is_connected():
        return current_transport, current_client, None

    if current_transport is None and current_client is not None:
        if await reconnect_client_if_needed_fn(current_client):
            return current_transport, current_client, None

    if current_transport is not None or current_client is not None:
        await disconnect_locked_fn()
        current_transport, current_client = get_runtime_state_fn()

    try:
        selected_transport, selected_mode = await ensure_transport_selected_fn()
        current_transport, current_client = get_runtime_state_fn()
        if selected_transport is not None:
            current_transport = selected_transport

        current_client = await connect_transport_or_client_fn(
            transport=current_transport,
            client=current_client,
        )
        logger.debug("Modbus connection established")
        mark_connection_established_fn()
        return current_transport, current_client, selected_mode
    except (ModbusException, ConnectionException):
        mark_connection_failure_fn()
        raise
    except TimeoutError:
        mark_connection_failure_fn()
        raise
    except OSError:
        mark_connection_failure_fn()
        raise
