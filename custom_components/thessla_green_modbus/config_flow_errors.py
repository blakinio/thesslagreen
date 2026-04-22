"""Error classification helpers for config flow validation."""

from __future__ import annotations

import socket

from .error_policy import should_log_timeout_traceback as _should_log_timeout_traceback_impl


def classify_os_error(exc: OSError) -> str:
    """Classify network-related OS errors to config-flow reason keys."""
    if isinstance(exc, socket.gaierror):
        return "dns_failure"
    if isinstance(exc, ConnectionRefusedError):
        return "connection_refused"
    return "cannot_connect"


def should_log_timeout_traceback(exc: BaseException) -> bool:
    """Return whether timeout traceback should be logged for this error."""
    return _should_log_timeout_traceback_impl(exc)
