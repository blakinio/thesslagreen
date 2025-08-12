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
    kwarg = "slave" if "slave" in params else "unit"

    # Map passed positional arguments to parameter names so that any values intended
    # for keyword-only parameters (e.g. ``count``) are moved into ``kwargs``.
    positional: list[Any] = []
    param_iter = iter(params.values())
    for arg in args:
        try:
            param = next(param_iter)
        except StopIteration:
            positional.append(arg)
            continue

        if param.kind is inspect.Parameter.KEYWORD_ONLY:
            kwargs[param.name] = arg
        else:
            positional.append(arg)

    try:
        return await func(*positional, **{kwarg: slave_id}, **kwargs)
    except Exception as err:  # pragma: no cover - log unexpected errors
        _LOGGER.error(
            "Modbus call %s failed: %s", getattr(func, "__name__", repr(func)), err
        )
        raise
