"""Modbus utility helpers."""

from __future__ import annotations

from typing import Any, Awaitable, Callable


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
    try:  # pymodbus >=3.5 uses 'slave'
        return await func(*args, slave=slave_id, **kwargs)
    except TypeError:  # pragma: no cover - support older versions
        return await func(*args, unit=slave_id, **kwargs)
