"""Modbus utility helpers."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Awaitable, Callable, Dict

_LOGGER = logging.getLogger(__name__)

# Cache which keyword ("slave" or "unit") a given function accepts
_KWARG_CACHE: Dict[Callable[..., Awaitable[Any]], str | None] = {}
# Cache function signatures to avoid repeated inspection
_SIG_CACHE: Dict[Callable[..., Awaitable[Any]], inspect.Signature] = {}


async def _call_modbus(
    func: Callable[..., Awaitable[Any]],
    slave_id: int,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Invoke a Modbus function handling ``slave``/``unit`` compatibility.

    The function signature is inspected to determine whether the wrapped
    callable expects a ``slave`` or ``unit`` keyword argument.  If neither is
    present the function is called without either keyword.  The chosen keyword
    (or lack thereof) is cached per callable for subsequent invocations.
    """

    # Fetch and cache the function signature
    signature = _SIG_CACHE.get(func)
    if signature is None:
        signature = inspect.signature(func)
        _SIG_CACHE[func] = signature

    # Map positional arguments to keyword-only parameters so that any values
    # intended for keyword-only parameters (e.g. ``count``) are moved into
    # ``kwargs``.
    params = signature.parameters
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

    kwarg = _KWARG_CACHE.get(func)
    if kwarg is None:
        # Determine which keyword the function accepts
        if "slave" in params and params["slave"].kind is not inspect.Parameter.POSITIONAL_ONLY:
            kwarg = "slave"
        elif "unit" in params and params["unit"].kind is not inspect.Parameter.POSITIONAL_ONLY:
            kwarg = "unit"
        else:
            kwarg = ""
        _KWARG_CACHE[func] = kwarg

    if kwarg == "slave":
        return await func(*positional, slave=slave_id, **kwargs)
    if kwarg == "unit":
        return await func(*positional, unit=slave_id, **kwargs)
    return await func(*positional, **kwargs)
