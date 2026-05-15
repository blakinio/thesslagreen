"""Compatibility re-exports - functions have moved to focused modules.

This module is kept for backwards compatibility. All functions are now
implemented in focused modules under ``modbus/`` and ``registers/``.
"""

from __future__ import annotations

from .modbus.call import (
    _KWARG_CACHE,
    _LOGGER,
    _SIG_CACHE,
    _apply_attempt_delay,
    _calculate_backoff_delay,
    _calculate_batch_size,
    _call_modbus,
    _classify_modbus_exception,
    _dispatch_modbus_call,
    _get_signature,
    _invoke_with_slave_kwarg,
    _log_call_attempt,
    _normalize_positional_and_keyword_args,
    _prepare_modbus_call,
    _PreparedCall,
    _raise_mapped_call_exception,
    _resolve_slave_kwarg,
    _should_apply_external_timeout,
    async_maybe_await,
)
from .modbus.client_close import async_close_client, async_maybe_await_close
from .modbus.frame_logging import (
    _build_request_frame,
    _log_modbus_request,
    _log_modbus_response,
    _mask_frame,
)
from .modbus.framer import FramerType, ModbusRtuFramer
from .registers.read_planner import (
    chunk_register_range,
    chunk_register_values,
    group_reads,
)

_FUNC_CODE_TO_NAME: dict[int, str] = {
    1: "read_coils",
    2: "read_discrete_inputs",
    3: "read_holding_registers",
    4: "read_input_registers",
    6: "write_register",
    16: "write_registers",
}


def _encode_read_frame(
    slave_id: int,
    func_code: int,
    positional: list,
    kwargs: dict,
) -> bytes:
    """Build a Modbus request frame from numeric function code."""
    func_name = _FUNC_CODE_TO_NAME.get(func_code, str(func_code))
    return _build_request_frame(func_name, slave_id, positional, kwargs)


def get_rtu_framer() -> object | None:
    """Return a Modbus RTU framer class/enum when available."""
    if FramerType is not None:
        try:
            return FramerType.RTU
        except (AttributeError, ValueError):  # pragma: no cover
            return None
    if ModbusRtuFramer is not None:
        return ModbusRtuFramer
    return None


__all__ = [
    "_KWARG_CACHE",
    "_LOGGER",
    "_SIG_CACHE",
    "FramerType",
    "ModbusRtuFramer",
    "_PreparedCall",
    "_apply_attempt_delay",
    "_build_request_frame",
    "_calculate_backoff_delay",
    "_calculate_batch_size",
    "_call_modbus",
    "_classify_modbus_exception",
    "_dispatch_modbus_call",
    "_encode_read_frame",
    "_get_signature",
    "_invoke_with_slave_kwarg",
    "_log_call_attempt",
    "_log_modbus_request",
    "_log_modbus_response",
    "_mask_frame",
    "_normalize_positional_and_keyword_args",
    "_prepare_modbus_call",
    "_raise_mapped_call_exception",
    "_resolve_slave_kwarg",
    "_should_apply_external_timeout",
    "async_close_client",
    "async_maybe_await",
    "async_maybe_await_close",
    "chunk_register_range",
    "chunk_register_values",
    "get_rtu_framer",
    "group_reads",
]
