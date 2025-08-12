"""Modbus utility helpers."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Awaitable, Callable, Dict


_LOGGER = logging.getLogger(__name__)

# Cache which keyword ("slave" or "unit") a given function accepts
_KWARG_CACHE: Dict[Callable[..., Awaitable[Any]], str | None] = {}


async def _call_modbus(
    func: Callable[..., Awaitable[Any]],
    slave_id: int,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Invoke a Modbus function handling slave/unit compatibility.

    The call is first attempted using ``slave=<id>``.  If the underlying
    function does not accept the ``slave`` keyword (raising ``TypeError``),
    the helper retries with ``unit=<id>``.  The successful keyword is cached
    per function for subsequent invocations.
    """

    # Map positional arguments to keyword-only parameters so that any values
    # intended for keyword-only parameters (e.g. ``count``) are moved into
    # ``kwargs``.
    params = inspect.signature(func).parameters
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
    if kwarg == "slave":
        return await func(*positional, slave=slave_id, **kwargs)
    if kwarg == "unit":
        return await func(*positional, unit=slave_id, **kwargs)
    if kwarg == "":
        return await func(*positional, **kwargs)

    # No cached keyword: try "slave" first then "unit"
    try:
        result = await func(*positional, slave=slave_id, **kwargs)
    except TypeError as err:
        if "unexpected keyword" not in str(err):
            raise
        try:
            result = await func(*positional, unit=slave_id, **kwargs)
        except TypeError as err2:
            if "unexpected keyword" not in str(err2):
                raise
            _KWARG_CACHE[func] = ""
            return await func(*positional, **kwargs)
        else:
            _KWARG_CACHE[func] = "unit"
            return result
    else:
        _KWARG_CACHE[func] = "slave"
        return result
