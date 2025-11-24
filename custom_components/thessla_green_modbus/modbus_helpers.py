"""Utility helpers for Modbus communication and read grouping."""

from __future__ import annotations

import asyncio
import inspect
import logging
import random
import weakref
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from . import const

_LOGGER = logging.getLogger(__name__)

# Cache which keyword ("slave" or "unit") a given function accepts
_KWARG_CACHE: weakref.WeakKeyDictionary[Callable[..., Awaitable[Any]], str | None] = (
    weakref.WeakKeyDictionary()
)
# Cache function signatures to avoid repeated inspection
_SIG_CACHE: weakref.WeakKeyDictionary[Callable[..., Awaitable[Any]], inspect.Signature] = (
    weakref.WeakKeyDictionary()
)


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
            return bytes([slave_id, 0x04, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF])
        if func_name == "read_holding_registers":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 0x03, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF])
        if func_name == "read_coils":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 0x01, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF])
        if func_name == "read_discrete_inputs":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 0x02, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF])
        if func_name == "write_register":
            addr = int(kwargs.get("address", positional[0]))
            value = int(kwargs.get("value", positional[1] if len(positional) > 1 else 0))
            return bytes([slave_id, 0x06, addr >> 8, addr & 0xFF, value >> 8, value & 0xFF])
        if func_name == "write_registers":
            addr = int(kwargs.get("address", positional[0]))
            values = [
                int(v) for v in kwargs.get("values", positional[1] if len(positional) > 1 else [])
            ]
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
            value = (
                0xFF00
                if kwargs.get("value", positional[1] if len(positional) > 1 else False)
                else 0x0000
            )
            return bytes([slave_id, 0x05, addr >> 8, addr & 0xFF, value >> 8, value & 0xFF])
    except (ValueError, TypeError, IndexError) as err:
        _LOGGER.debug("Failed to build request frame: %s", err)
        return b""
    except Exception as err:  # pragma: no cover - unexpected
        _LOGGER.exception("Unexpected error building request frame: %s", err)
        return b""

    return b""


def _calculate_backoff_delay(
    *,
    base: float,
    attempt: int,
    jitter: float | tuple[float, float] | None,
) -> float:
    """Return the delay for the given ``attempt`` including optional jitter."""

    if base <= 0 or attempt <= 1:
        delay = 0.0
    else:
        delay = float(base) * (2 ** (attempt - 2))

    if jitter:
        if isinstance(jitter, int | float):
            jitter_min = 0.0
            jitter_max = float(jitter)
        else:
            jitter_min, jitter_max = (float(jitter[0]), float(jitter[1]))
        if jitter_max < jitter_min:
            jitter_min, jitter_max = jitter_max, jitter_min
        delay += random.uniform(jitter_min, jitter_max)

    return max(delay, 0.0)


async def _call_modbus(
    func: Callable[..., Awaitable[Any]],
    slave_id: int,
    *args: Any,
    attempt: int = 1,
    max_attempts: int = 1,
    timeout: float | None = None,
    backoff: float = 0.0,
    backoff_jitter: float | tuple[float, float] | None = None,
    apply_backoff: bool = True,
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

    delay = 0.0
    if apply_backoff:
        delay = _calculate_backoff_delay(
            base=backoff,
            attempt=attempt,
            jitter=backoff_jitter,
        )

    if delay > 0:
        _LOGGER.debug(
            "Delaying %.3fs before attempt %s/%s of %s", delay, attempt, max_attempts, func_name
        )
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            _LOGGER.debug(
                "Sleep cancelled before calling %s attempt %s/%s", func_name, attempt, max_attempts
            )
            raise

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
            _LOGGER.debug(
                "Sending %s to slave %s: args=%s kwargs=%s", func_name, slave_id, positional, kwargs
            )

    async def _invoke() -> Any:
        if kwarg == "slave":
            return await func(*positional, slave=slave_id, **kwargs)
        if kwarg == "unit":
            return await func(*positional, unit=slave_id, **kwargs)
        return await func(*positional, **kwargs)

    try:
        if timeout is not None:
            response = await asyncio.wait_for(_invoke(), timeout=timeout)
        else:
            response = await _invoke()
    except Exception:
        _LOGGER.debug("Call to %s failed on attempt %s/%s", func_name, attempt, max_attempts)
        raise

    if _LOGGER.isEnabledFor(logging.DEBUG):
        try:
            encoded = response.encode() if hasattr(response, "encode") else b""
        except (AttributeError, ValueError, TypeError, UnicodeError) as err:
            _LOGGER.debug("Failed to encode Modbus response: %s", err)
            encoded = b""
        except Exception as err:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected error encoding Modbus response: %s", err)
            encoded = b""
        if encoded:
            _LOGGER.debug("Modbus response: %s", _mask_frame(encoded))
        else:
            _LOGGER.debug("Received from %s: %s", func_name, response)
    return response


def group_reads(
    addresses: Iterable[int],
    max_block_size: int | None = None,
) -> list[tuple[int, int]]:
    """Group raw register addresses into contiguous read blocks.

    The addresses are sorted and sequential ranges are merged up to
    ``max_block_size`` entries.  The returned list contains ``(start, length)``
    tuples suitable for bulk Modbus read operations.
    """

    if max_block_size is None:
        max_block_size = const.MAX_BATCH_REGISTERS
    max_block_size = min(max_block_size, const.MAX_BATCH_REGISTERS)
    sorted_addresses = sorted(set(addresses))
    if not sorted_addresses:
        return []

    groups: list[tuple[int, int]] = []
    start = prev = sorted_addresses[0]
    for addr in sorted_addresses[1:]:
        if addr == prev + 1 and (addr - start + 1) <= max_block_size:
            prev = addr
            continue
        groups.append((start, prev - start + 1))
        start = prev = addr
    groups.append((start, prev - start + 1))
    return groups
