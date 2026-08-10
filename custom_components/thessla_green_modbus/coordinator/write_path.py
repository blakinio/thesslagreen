"""Write-path orchestration helpers."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException

from ..core.write_path import SingleWritePlan
from ..repairs import clear_write_failure_issue, create_write_failure_issue

_LOGGER = logging.getLogger(__name__)


def _create_write_repair(coordinator: Any, register: str) -> None:
    """Best-effort repair issue creation at the Home Assistant boundary."""
    hass = getattr(coordinator, "hass", None)
    if hass is None:
        return
    try:
        create_write_failure_issue(
            hass,
            getattr(coordinator, "entry", None),
            register=register,
        )
    except (AttributeError, KeyError, TypeError, RuntimeError) as exc:
        _LOGGER.debug("Could not create write-failure repair issue: %s", exc)


def _clear_write_repair(coordinator: Any) -> None:
    """Best-effort repair issue cleanup after a confirmed successful write."""
    hass = getattr(coordinator, "hass", None)
    if hass is None:
        return
    try:
        clear_write_failure_issue(hass, getattr(coordinator, "entry", None))
    except (AttributeError, KeyError, TypeError, RuntimeError) as exc:
        _LOGGER.debug("Could not clear write-failure repair issue: %s", exc)


async def run_single_write_attempts(
    coordinator: Any, definition: Any, plan: SingleWritePlan, refresh: bool
) -> tuple[bool, bool]:
    """Execute retry loop for single-register write."""
    refresh_after_write = False
    for attempt in range(1, coordinator.device_client.retry + 1):
        try:
            response, success = await coordinator._execute_single_register_write_attempt(
                definition=definition,
                register_name=plan.register_name,
                address=plan.address,
                encoded_values=plan.encoded_values,
                scalar_value=plan.scalar_value,
                attempt=attempt,
            )
            if not success:
                should_retry = coordinator._handle_write_response_failure(
                    is_final_attempt=attempt == coordinator.device_client.retry,
                    final_error_message="Error writing to register %s: %s",
                    retry_message=f"Retrying write to register {plan.register_name}",
                    error_args=(plan.register_name, response),
                )
                if not should_retry:
                    _create_write_repair(coordinator, plan.register_name)
                    return False, False
                continue

            refresh_after_write = coordinator._handle_successful_single_register_write(
                register_name=plan.register_name,
                original_value=plan.original_value,
                refresh=refresh,
            )
            _clear_write_repair(coordinator)
            break
        except (ModbusException, ConnectionException, TimeoutError, OSError) as exc:
            should_retry = await coordinator._handle_write_attempt_exception(
                register_name=plan.register_name,
                attempt=attempt,
                exc=exc,
                timed_out_message="Writing register %s timed out (attempt %d/%d)",
                persistent_timeout_message="Persistent timeout writing register %s",
                failed_message="Failed to write register %s",
                retry_message="Retrying write to register %s after error: %s",
                unexpected_message="Unexpected error writing register %s",
            )
            if not should_retry:
                _create_write_repair(coordinator, plan.register_name)
                return False, False
            continue
    return True, refresh_after_write


async def run_multi_register_write_attempts(
    coordinator: Any,
    start_address: int,
    values: list[int],
    require_single_request: bool,
    refresh: bool,
) -> tuple[bool, bool]:
    """Execute retry loop for multi-register write. Returns (success, refresh_after_write)."""
    refresh_after_write = False
    for attempt in range(1, coordinator.device_client.retry + 1):
        try:
            response, success = await coordinator._execute_multi_register_chunks(
                coordinator._plan_multi_register_chunks(
                    start_address, values, require_single_request
                ),
                attempt,
            )
            if not success:
                should_retry = coordinator._handle_write_response_failure(
                    is_final_attempt=attempt == coordinator.device_client.retry,
                    final_error_message="Error writing registers at %s: %s",
                    retry_message=f"Retrying multi-register write at {start_address}",
                    error_args=(start_address, response),
                )
                if not should_retry:
                    _create_write_repair(coordinator, str(start_address))
                    return False, False
                await coordinator._disconnect()
                continue
            refresh_after_write = refresh
            _clear_write_repair(coordinator)
            _LOGGER.info(
                "Successfully wrote %s to registers starting at %s",
                values,
                start_address,
            )
            break
        except (ModbusException, ConnectionException, TimeoutError, OSError) as exc:
            should_retry = await coordinator._handle_write_attempt_exception(
                register_name=str(start_address),
                attempt=attempt,
                exc=exc,
                timed_out_message="Writing registers at %s timed out (attempt %d/%d)",
                persistent_timeout_message="Persistent timeout writing registers at %s",
                failed_message="Failed to write registers at %s",
                retry_message="Retrying multi-register write at %s after error: %s",
                unexpected_message="Unexpected error writing registers at %s",
            )
            if not should_retry:
                _create_write_repair(coordinator, str(start_address))
                return False, False
            continue
    return True, refresh_after_write


async def finalize_write_result(coordinator: Any, refresh_after_write: bool) -> bool:
    """Finish write operation with optional refresh."""
    if refresh_after_write:
        await coordinator._safe_request_refresh()
    return True
