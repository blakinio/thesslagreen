"""Safe Modbus client close helpers."""

from __future__ import annotations

import logging
from typing import Any

from .call import async_maybe_await

_LOGGER = logging.getLogger(__name__)


async def async_maybe_await_close(obj: Any | None) -> None:
    """Close a Modbus client safely across sync/async implementations."""

    if obj is None:
        return

    close = getattr(obj, "close", None)
    if close is None or not callable(close):
        return

    try:
        result = close()
    except (
        AttributeError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:  # pragma: no cover - defensive
        _LOGGER.debug("Error calling close on Modbus client: %s", exc)
        return

    try:
        await async_maybe_await(result)
    except (
        AttributeError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:  # pragma: no cover - defensive
        _LOGGER.debug("Error awaiting Modbus client close: %s", exc)


async def async_close_client(client: Any | None) -> None:
    """Wrapper for safe Modbus client close."""

    await async_maybe_await_close(client)
