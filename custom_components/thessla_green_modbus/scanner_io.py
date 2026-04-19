"""Backward compatibility shim — moved to scanner.io."""

from __future__ import annotations

from .scanner.io import (
    ensure_pymodbus_client_module,
    is_request_cancelled_error,
)

__all__ = ["ensure_pymodbus_client_module", "is_request_cancelled_error"]
