"""Backward-compatible scanner I/O exports."""

from .io_core import (
    _call_modbus_with_fallback_fn,
    _maybe_retry_yield,
    _sleep_retry_backoff_fn,
    ensure_pymodbus_client_module,
    is_request_cancelled_error,
    log_scanner_retry,
    resolve_transport_and_client,
    track_holding_failure,
    track_input_failure,
    unpack_read_args,
)
from .io_read import (
    read_bit_registers,
    read_coil,
    read_discrete,
    read_holding,
    read_input,
    read_register_block,
)

__all__ = [
    "_call_modbus_with_fallback_fn",
    "_maybe_retry_yield",
    "_sleep_retry_backoff_fn",
    "ensure_pymodbus_client_module",
    "is_request_cancelled_error",
    "log_scanner_retry",
    "read_bit_registers",
    "read_coil",
    "read_discrete",
    "read_holding",
    "read_input",
    "read_register_block",
    "resolve_transport_and_client",
    "track_holding_failure",
    "track_input_failure",
    "unpack_read_args",
]
