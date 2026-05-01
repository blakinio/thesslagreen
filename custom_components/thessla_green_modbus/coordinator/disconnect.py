"""Coordinator disconnect orchestration helpers."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from ..modbus_exceptions import ConnectionException, ModbusException


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
