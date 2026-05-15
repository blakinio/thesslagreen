"""Core Modbus call dispatch machinery."""

from __future__ import annotations

import asyncio
import inspect
import logging
import random
import weakref
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pymodbus.exceptions import ModbusIOException

from .frame_logging import _log_modbus_request, _log_modbus_response

_LOGGER = logging.getLogger(__name__)

# Cache which keyword variant a given function accepts
_KWARG_CACHE: weakref.WeakKeyDictionary[Callable[..., Awaitable[Any]], str | None] = (
    weakref.WeakKeyDictionary()
)
# Cache function signatures to avoid repeated inspection
_SIG_CACHE: weakref.WeakKeyDictionary[Callable[..., Awaitable[Any]], inspect.Signature] = (
    weakref.WeakKeyDictionary()
)


def _get_signature(func: Callable[..., Awaitable[Any]]) -> inspect.Signature | None:
    """Return a cached signature when introspection is available."""

    signature = _SIG_CACHE.get(func)
    if signature is not None:
        return signature

    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return None

    _SIG_CACHE[func] = signature
    return signature


def _should_apply_external_timeout(func: Callable[..., Awaitable[Any]]) -> bool:
    """Return whether ``asyncio.wait_for`` should wrap ``func`` calls.

    Pymodbus clients already implement their own timeout and cancellation
    handling. Wrapping those calls in an external ``wait_for`` can cancel
    requests mid-flight, leaving stale transaction IDs and causing follow-up
    "request ask for transaction_id" desynchronization errors.
    """

    module_name = getattr(func, "__module__", "") or ""
    return not module_name.startswith("pymodbus")


async def async_maybe_await(result: Any) -> Any:
    """Await a result only if it is awaitable."""

    if inspect.isawaitable(result):
        return await result
    return result


def _calculate_backoff_delay(
    *,
    base: float,
    attempt: int,
    jitter: float | tuple[float, float] | None,
) -> float:
    """Return the delay for the given ``attempt`` including optional jitter."""

    if base <= 0 or attempt <= 1:
        return 0.0

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

    return float(max(delay, 0.0))


def _normalize_positional_and_keyword_args(
    signature: inspect.Signature | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[list[Any], dict[str, inspect.Parameter]]:
    """Move positional values targeting keyword-only params into ``kwargs``."""
    params: dict[str, inspect.Parameter] = (
        dict(signature.parameters) if signature is not None else {}
    )
    positional: list[Any] = []
    if signature is None:
        return list(args), params

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
    return positional, params


def _resolve_slave_kwarg(
    func: Callable[..., Awaitable[Any]],
    params: dict[str, inspect.Parameter],
    signature: inspect.Signature | None,
) -> str:
    """Return cached keyword variant supported by Modbus client callable."""
    kwarg = _KWARG_CACHE.get(func)
    if kwarg is not None:
        return kwarg

    if "device_id" in params and params["device_id"].kind is not inspect.Parameter.POSITIONAL_ONLY:
        kwarg = "device_id"
    elif "slave" in params and params["slave"].kind is not inspect.Parameter.POSITIONAL_ONLY:
        kwarg = "slave"
    elif "unit" in params and params["unit"].kind is not inspect.Parameter.POSITIONAL_ONLY:
        kwarg = "unit"
    else:
        kwarg = "slave" if signature is None else ""

    _KWARG_CACHE[func] = kwarg
    return kwarg


async def _invoke_with_slave_kwarg(
    func: Callable[..., Awaitable[Any]],
    positional: list[Any],
    kwargs: dict[str, Any],
    kwarg: str,
    slave_id: int,
) -> Any:
    """Invoke wrapped callable using detected slave keyword convention."""
    if kwarg == "device_id":
        return await async_maybe_await(func(*positional, device_id=slave_id, **kwargs))
    if kwarg == "slave":
        return await async_maybe_await(func(*positional, slave=slave_id, **kwargs))
    if kwarg == "unit":
        return await async_maybe_await(func(*positional, unit=slave_id, **kwargs))
    return await async_maybe_await(func(*positional, **kwargs))


def _calculate_batch_size(kwargs: dict[str, Any]) -> int:
    """Calculate batch size metadata for request logging."""
    return kwargs.get("count") or len(kwargs.get("values", [])) or 1


@dataclass(frozen=True, slots=True)
class _PreparedCall:
    positional: list[Any]
    kwarg: str
    func_name: str
    batch_size: int
    delay: float


def _prepare_modbus_call(
    func: Callable[..., Awaitable[Any]],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    attempt: int,
    backoff: float,
    backoff_jitter: float | tuple[float, float] | None,
    apply_backoff: bool,
) -> tuple[list[Any], str, str, int, float]:
    """Prepare call metadata for ``_call_modbus`` without mutating behavior."""

    signature = _get_signature(func)
    positional, params = _normalize_positional_and_keyword_args(signature, args, kwargs)
    kwarg = _resolve_slave_kwarg(func, params, signature)
    func_name = getattr(func, "__name__", repr(func))
    batch_size = _calculate_batch_size(kwargs)
    delay = (
        _calculate_backoff_delay(base=backoff, attempt=attempt, jitter=backoff_jitter)
        if apply_backoff
        else 0.0
    )
    return positional, kwarg, func_name, batch_size, delay


def _classify_modbus_exception(err: Exception) -> str:
    """Return exception class for Modbus call logging."""
    if isinstance(err, ModbusIOException) and "request cancelled" in str(err).lower():
        return "cancelled"
    return "failed"


async def _dispatch_modbus_call(
    func: Callable[..., Awaitable[Any]],
    positional: list[Any],
    kwargs: dict[str, Any],
    kwarg: str,
    slave_id: int,
    timeout: float | None,
) -> Any:
    """Dispatch a Modbus callable with optional external timeout."""

    async def _invoke() -> Any:
        return await _invoke_with_slave_kwarg(func, positional, kwargs, kwarg, slave_id)

    if timeout is not None and _should_apply_external_timeout(func):
        return await asyncio.wait_for(_invoke(), timeout=timeout)
    return await _invoke()


async def _apply_attempt_delay(
    *,
    delay: float,
    func_name: str,
    attempt: int,
    max_attempts: int,
) -> None:
    """Apply pre-attempt delay while preserving cancellation diagnostics."""
    if delay <= 0:
        return

    _LOGGER.debug(
        "Delaying %.3fs before attempt %s/%s of %s",
        delay,
        attempt,
        max_attempts,
        func_name,
    )
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        _LOGGER.debug(
            "Sleep cancelled before calling %s attempt %s/%s",
            func_name,
            attempt,
            max_attempts,
        )
        raise


def _log_call_attempt(
    prepared: _PreparedCall,
    *,
    slave_id: int,
    attempt: int,
    max_attempts: int,
    kwargs: dict[str, Any],
) -> None:
    """Log the outgoing call summary and request frame."""
    _LOGGER.debug(
        "Calling %s on slave %s (batch=%s attempt %s/%s)",
        prepared.func_name,
        slave_id,
        prepared.batch_size,
        attempt,
        max_attempts,
    )
    _log_modbus_request(
        func_name=prepared.func_name,
        slave_id=slave_id,
        positional=prepared.positional,
        kwargs=kwargs,
    )


def _raise_mapped_call_exception(
    err: Exception,
    *,
    func_name: str,
    attempt: int,
    max_attempts: int,
) -> None:
    """Log call classification and re-raise preserving existing behavior."""
    if isinstance(err, TimeoutError):
        _LOGGER.debug("Call to %s timed out on attempt %s/%s", func_name, attempt, max_attempts)
        raise TimeoutError("Modbus request timed out") from err

    classification = _classify_modbus_exception(err)
    if classification == "cancelled":
        _LOGGER.debug("Call to %s cancelled on attempt %s/%s", func_name, attempt, max_attempts)
    else:
        _LOGGER.debug("Call to %s failed on attempt %s/%s", func_name, attempt, max_attempts)
    raise


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
    """Invoke a Modbus function handling Modbus client keyword variants.

    The function signature is inspected to determine whether the wrapped
    callable expects a ``device_id`` or ``slave`` keyword argument.  If neither is
    present the function is called without either keyword.  The chosen keyword
    (or lack thereof) is cached per callable for subsequent invocations.
    """

    positional, kwarg, func_name, batch_size, delay = _prepare_modbus_call(
        func,
        args,
        kwargs,
        attempt=attempt,
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        apply_backoff=apply_backoff,
    )

    prepared = _PreparedCall(positional, kwarg, func_name, batch_size, delay)
    await _apply_attempt_delay(
        delay=prepared.delay,
        func_name=prepared.func_name,
        attempt=attempt,
        max_attempts=max_attempts,
    )

    _log_call_attempt(
        prepared,
        slave_id=slave_id,
        attempt=attempt,
        max_attempts=max_attempts,
        kwargs=kwargs,
    )

    try:
        response = await _dispatch_modbus_call(
            func=func,
            positional=prepared.positional,
            kwargs=kwargs,
            kwarg=prepared.kwarg,
            slave_id=slave_id,
            timeout=timeout,
        )
    except TimeoutError as err:
        _raise_mapped_call_exception(
            err, func_name=prepared.func_name, attempt=attempt, max_attempts=max_attempts
        )
    except asyncio.CancelledError:
        _LOGGER.debug(
            "Call to %s cancelled on attempt %s/%s", prepared.func_name, attempt, max_attempts
        )
        raise
    except (
        AttributeError,
        ModbusIOException,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as err:
        _raise_mapped_call_exception(
            err, func_name=prepared.func_name, attempt=attempt, max_attempts=max_attempts
        )

    _log_modbus_response(prepared.func_name, response)
    return response
