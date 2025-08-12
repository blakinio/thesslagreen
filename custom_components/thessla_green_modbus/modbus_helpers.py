"""Modbus utility helpers."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Awaitable, Callable


_LOGGER = logging.getLogger(__name__)


async def _call_modbus(
    func: Callable[..., Awaitable[Any]],
    slave_id: int,
    *args: Any,
    **kwargs: Any,
):
    """Invoke a Modbus function handling slave/unit compatibility.

    This helper ensures compatibility between pymodbus versions that expect either
    ``slave`` or ``unit`` as the keyword for the target device.
    """
    params = inspect.signature(func).parameters
    if "slave" in params:
        kwarg = "slave"
    elif "unit" in params:
        kwarg = "unit"
    else:
        kwarg = None

    try:
        if kwarg is not None:
            _LOGGER.debug(
                "Calling %s with %s keyword", getattr(func, "__name__", repr(func)), kwarg
            )
            return await func(*args, **{kwarg: slave_id}, **kwargs)

        _LOGGER.debug(
            "Calling %s without address keyword", getattr(func, "__name__", repr(func))
        )
        return await func(*args, **kwargs)
    except Exception as err:  # pragma: no cover - log unexpected errors
        _LOGGER.error("Modbus call %s failed: %s", getattr(func, "__name__", repr(func)), err)
        raise
