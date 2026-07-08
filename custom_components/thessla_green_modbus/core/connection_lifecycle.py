"""Connection lifecycle, state, and disconnect helpers for device-client runtime."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, MutableMapping
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException


def mark_connection_established(*, offline_state_setter: Any) -> None:
    """Mark coordinator runtime as connected."""
    offline_state_setter(False)


def mark_connection_failure(
    *, statistics: MutableMapping[str, Any], offline_state_setter: Any
) -> None:
    """Record connection failure counters and switch coordinator offline."""
    statistics["connection_errors"] += 1
    offline_state_setter(True)


def mark_connection_disconnected(*, offline_state_setter: Any) -> None:
    """Mark coordinator runtime as disconnected."""
    offline_state_setter(True)


async def close_client_connection(*, client: Any, logger: logging.Logger) -> None:
    """Close client object safely for sync or async close implementations."""
    try:
        close = getattr(client, "close", None)
        if callable(close):
            if inspect.iscoroutinefunction(close):
                await close()
            else:
                result = close()
                if inspect.isawaitable(result):
                    await result
    except (ModbusException, ConnectionException):
        logger.debug("Error disconnecting", exc_info=True)
    except OSError:
        logger.exception("Unexpected error disconnecting")


async def disconnect_locked(
    *,
    transport: Any,
    client: Any,
    close_client_connection_fn: Callable[..., Any],
    mark_connection_disconnected_fn: Callable[[], None],
    logger: logging.Logger,
) -> None:
    """Disconnect from Modbus device without acquiring locks."""
    if transport is not None:
        try:
            await transport.close()
        except (ModbusException, ConnectionException):
            logger.debug("Error disconnecting", exc_info=True)
        except OSError:
            logger.exception("Unexpected error disconnecting")
    elif client is not None:
        await close_client_connection_fn(client=client, logger=logger)

    mark_connection_disconnected_fn()
    logger.debug("Disconnected from Modbus device")


async def ensure_connected_lifecycle(
    device_client: Any,
    *,
    disconnect_locked_fn: Callable[..., Any],
    ensure_connected_runtime_fn: Callable[..., Any],
    reconnect_client_if_needed_fn: Callable[..., Any],
    ensure_transport_selected_fn_factory: Callable[[], Callable[..., Any]],
    connect_transport_or_client_fn: Callable[..., Any],
    mark_connection_established_fn: Callable[[], None],
    mark_connection_failure_fn: Callable[[], None],
    logger: Any,
) -> None:
    """Drive connection establishment and state updates for device client."""
    async with device_client._client_lock:
        try:
            transport, client, selected_mode = await ensure_connected_runtime_fn(
                current_transport=device_client._transport,
                current_client=device_client.client,
                reconnect_client_if_needed_fn=reconnect_client_if_needed_fn,
                disconnect_locked_fn=disconnect_locked_fn,
                get_runtime_state_fn=lambda: (
                    device_client._transport,
                    device_client.client,
                ),
                ensure_transport_selected_fn=ensure_transport_selected_fn_factory(),
                connect_transport_or_client_fn=connect_transport_or_client_fn,
                mark_connection_established_fn=mark_connection_established_fn,
                mark_connection_failure_fn=mark_connection_failure_fn,
                logger=logger,
            )
            device_client._transport = transport
            device_client.client = client
            if selected_mode is not None:
                device_client._resolved_connection_mode = selected_mode
        except (ModbusException, ConnectionException) as exc:
            logger.exception("Failed to establish connection: %s", exc)
            raise
        except TimeoutError as exc:
            logger.warning("Connection attempt timed out: %s", exc)
            raise
        except OSError as exc:
            logger.exception("Unexpected error establishing connection: %s", exc)
            raise
