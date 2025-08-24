"""Modbus utility helpers."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, List, Tuple

_LOGGER = logging.getLogger(__name__)

# Cache which keyword ("slave" or "unit") a given function accepts
_KWARG_CACHE: dict[Callable[..., Awaitable[Any]], str | None] = {}
# Cache function signatures to avoid repeated inspection
_SIG_CACHE: dict[Callable[..., Awaitable[Any]], inspect.Signature] = {}


def _mask_frame(frame: bytes) -> str:
    """Return a hex representation of ``frame`` with the slave ID masked."""

    if not frame:
        return ""

    hex_str = frame.hex()
    if len(hex_str) >= 2:
        return f"**{hex_str[2:]}"
    return hex_str


def _build_request_frame(
    func_name: str, slave_id: int, positional: list[Any], kwargs: dict[str, Any]
) -> bytes:
    """Best-effort Modbus request frame builder for logging."""

    try:
        if func_name == "read_input_registers":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes(
                [slave_id, 0x04, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF]
            )
        if func_name == "read_holding_registers":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes(
                [slave_id, 0x03, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF]
            )
        if func_name == "read_coils":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes(
                [slave_id, 0x01, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF]
            )
        if func_name == "read_discrete_inputs":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes(
                [slave_id, 0x02, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF]
            )
        if func_name == "write_register":
            addr = int(kwargs.get("address", positional[0]))
            value = int(kwargs.get("value", positional[1] if len(positional) > 1 else 0))
            return bytes(
                [slave_id, 0x06, addr >> 8, addr & 0xFF, value >> 8, value & 0xFF]
            )
        if func_name == "write_registers":
            addr = int(kwargs.get("address", positional[0]))
            values = [int(v) for v in kwargs.get("values", positional[1] if len(positional) > 1 else [])]
            qty = len(values)
            frame = bytearray(
                [
                    slave_id,
                    0x10,
                    addr >> 8,
                    addr & 0xFF,
                    qty >> 8,
                    qty & 0xFF,
                    qty * 2,
                ]
            )
            for v in values:
                frame.extend([v >> 8, v & 0xFF])
            return bytes(frame)
        if func_name == "write_coil":
            addr = int(kwargs.get("address", positional[0]))
            value = 0xFF00 if kwargs.get("value", positional[1] if len(positional) > 1 else False) else 0x0000
            return bytes(
                [slave_id, 0x05, addr >> 8, addr & 0xFF, value >> 8, value & 0xFF]
            )
    except Exception:  # pragma: no cover - best-effort logging only
        return b""

    return b""


async def _call_modbus(
    func: Callable[..., Awaitable[Any]],
    slave_id: int,
    *args: Any,
    attempt: int = 1,
    max_attempts: int = 1,
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

    func_name = getattr(func, "__name__", repr(func))
    batch_size = kwargs.get("count") or len(kwargs.get("values", [])) or 1
    _LOGGER.info(
        "Calling %s on slave %s (batch=%s attempt %s/%s)",
        func_name,
        slave_id,
        batch_size,
        attempt,
        max_attempts,
    )

    if _LOGGER.isEnabledFor(logging.DEBUG):
        request_frame = _build_request_frame(func_name, slave_id, positional, kwargs)
        if request_frame:
            _LOGGER.debug("Modbus request: %s", _mask_frame(request_frame))
        else:
            _LOGGER.debug("Sending %s to slave %s: args=%s kwargs=%s", func_name, slave_id, positional, kwargs)

    if kwarg == "slave":
        response = await func(*positional, slave=slave_id, **kwargs)
    elif kwarg == "unit":
        response = await func(*positional, unit=slave_id, **kwargs)
    else:
        response = await func(*positional, **kwargs)

    if _LOGGER.isEnabledFor(logging.DEBUG):
        try:
            encoded = response.encode() if hasattr(response, "encode") else b""
        except Exception:  # pragma: no cover - best effort logging
            encoded = b""
        if encoded:
            _LOGGER.debug("Modbus response: %s", _mask_frame(encoded))
        else:
            _LOGGER.debug("Received from %s: %s", func_name, response)
    return response


def group_reads(addresses: Iterable[int], max_block_size: int = 16) -> List[Tuple[int, int]]:
    """Group raw register addresses into contiguous read blocks.

    The addresses are sorted and sequential ranges are merged up to
    ``max_block_size`` entries.  The returned list contains ``(start, length)``
    tuples suitable for bulk Modbus read operations.
    """

    max_block_size = min(max_block_size, 16)
    sorted_addresses = sorted(set(addresses))
    if not sorted_addresses:
        return []

    groups: List[Tuple[int, int]] = []
    start = prev = sorted_addresses[0]
    for addr in sorted_addresses[1:]:
        if addr == prev + 1 and (addr - start + 1) <= max_block_size:
            prev = addr
            continue
        groups.append((start, prev - start + 1))
        start = prev = addr
    groups.append((start, prev - start + 1))
    return groups
