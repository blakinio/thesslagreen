"""Compatibility facade for coordinator I/O mixin and update error handling."""

from __future__ import annotations

import logging
from typing import Any

from ._coordinator_io_mixin import _ModbusIOMixin
from ._coordinator_retry import _PermanentModbusError
from ._coordinator_update_errors import handle_update_error as _handle_update_error_impl


async def handle_update_error(
    coordinator: Any,
    exc: Exception,
    *,
    reauth_reason: str,
    message: str,
    log_level: int = logging.ERROR,
    timeout_error: bool = False,
    check_auth: bool = False,
    use_helper: bool = True,
) -> Any:
    """Shared error-handling path for coordinator update failures."""
    return await _handle_update_error_impl(
        coordinator,
        exc,
        reauth_reason=reauth_reason,
        message=message,
        log_level=log_level,
        timeout_error=timeout_error,
        check_auth=check_auth,
        use_helper=use_helper,
    )


__all__ = ["_ModbusIOMixin", "_PermanentModbusError", "handle_update_error"]
