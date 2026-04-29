"""Shared coordinator update error-handling helpers."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.update_coordinator import UpdateFailed

_LOGGER = logging.getLogger(__name__)


def apply_update_failure_state(
    coordinator: Any,
    exc: Exception,
    *,
    timeout_error: bool,
) -> None:
    """Apply standard state/statistics changes after an update failure."""
    coordinator.statistics["failed_reads"] += 1
    if timeout_error:
        coordinator.statistics["timeout_errors"] += 1
    coordinator.statistics["last_error"] = str(exc)
    coordinator._consecutive_failures += 1
    coordinator.offline_state = True


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
) -> UpdateFailed:
    """Shared error-handling path for coordinator update failures."""
    from ..errors import is_invalid_auth_error

    apply_update_failure_state(coordinator, exc, timeout_error=timeout_error)
    await coordinator._disconnect()

    if coordinator._consecutive_failures >= coordinator._max_failures:
        _LOGGER.error("Too many consecutive failures, disconnecting")
        coordinator._trigger_reauth(reauth_reason)

    if check_auth and is_invalid_auth_error(exc):
        coordinator._trigger_reauth("invalid_auth")

    _LOGGER.log(log_level, "%s: %s", message, exc)
    full_message = f"{message}: {exc}"
    if use_helper and hasattr(coordinator, "_resolve_update_failure"):
        return coordinator._resolve_update_failure(exc, default_message=full_message)
    return UpdateFailed(full_message)
