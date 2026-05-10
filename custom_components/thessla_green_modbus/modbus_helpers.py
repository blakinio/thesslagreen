"""Compatibility re-exports - functions have moved to focused modules.

This module is kept for backwards compatibility. All functions are now
implemented in focused modules under ``modbus/`` and ``registers/``.
"""

from __future__ import annotations

from .modbus.call import (
    _KWARG_CACHE,
    _PreparedCall,
    _SIG_CACHE,
    _apply_attempt_delay,
    _calculate_backoff_delay,
    _calculate_batch_size,
    _call_modbus,
    _classify_modbus_exception,
    _dispatch_modbus_call,
    _get_signature,
    _invoke_with_slave_kwarg,
    _normalize_positional_and_keyword_args,
    _prepare_modbus_call,
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
from .modbus.framer import get_rtu_framer
from .registers.read_planner import (
    chunk_register_range,
    chunk_register_values,
    group_reads,
)

__all__ = [
    "_KWARG_CACHE",
    "_PreparedCall",
    "_SIG_CACHE",
    "_apply_attempt_delay",
    "_build_request_frame",
    "_calculate_backoff_delay",
    "_calculate_batch_size",
    "_call_modbus",
    "_classify_modbus_exception",
    "_dispatch_modbus_call",
    "_get_signature",
    "_invoke_with_slave_kwarg",
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
