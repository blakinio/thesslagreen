"""Connection lifecycle orchestration for device-client runtime."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException


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
