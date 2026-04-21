"""Error classification helpers for config flow validation."""

from __future__ import annotations

import socket


def classify_os_error(exc: OSError) -> str:
    """Classify network-related OS errors to config-flow reason keys."""
    if isinstance(exc, socket.gaierror):
        return "dns_failure"
    if isinstance(exc, ConnectionRefusedError):
        return "connection_refused"
    return "cannot_connect"


def should_log_timeout_traceback(exc: BaseException) -> bool:
    """Return whether timeout traceback should be logged for this error."""
    return "modbus request cancelled" not in str(exc).lower()
