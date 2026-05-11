"""Write-path orchestration helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException

_LOGGER = logging.getLogger(__name__)


def encode_write_value(
    register_name: str,
    definition: Any,
    value: float | str | list[int] | tuple[int, ...],
    offset: int,
) -> tuple[list[int] | None, Any]:
    """Encode *value* for writing. Returns (encoded_values, scalar_value).

    For multi-register definitions, returns (list[int], original_value).
    For single-register definitions, returns (None, int_value).
    Logs an error and returns (None, None) on validation failure.
    """
    if definition.length > 1:
        if isinstance(value, list | tuple) and not isinstance(value, bytes | bytearray | str):
            if len(value) + offset > definition.length:
                _LOGGER.error(
                    "Register %s expects at most %d values starting at offset %d",
                    register_name,
                    definition.length - offset,
                    offset,
                )
                return None, None
            if offset == 0 and len(value) != definition.length:
                _LOGGER.error(
                    "Register %s requires exactly %d values",
                    register_name,
                    definition.length,
                )
                return None, None
            try:
                return [int(v) for v in value], value
            except (TypeError, ValueError):
                _LOGGER.error("Register %s expects integer values", register_name)
                return None, None
        else:
            encoded = definition.encode(value)
            if isinstance(encoded, list):
                encoded_values: list[int] = [int(v) for v in encoded]
            else:
                encoded_values = [int(encoded)]
            if offset >= definition.length:
                _LOGGER.error(
                    "Register %s expects at most %d values starting at offset %d",
                    register_name,
                    definition.length - offset,
                    offset,
                )
                return None, None
            return encoded_values[offset:], value
    else:
        if isinstance(value, list | tuple) and not isinstance(value, bytes | bytearray | str):
            _LOGGER.error("Register %s expects a single value", register_name)
            return None, None
        return None, int(definition.encode(value))


@dataclass(slots=True)
class SingleWritePlan:
    register_name: str
    address: int
    encoded_values: list[int] | None
    scalar_value: Any
    original_value: float | str | list[int] | tuple[int, ...]


async def run_single_write_attempts(
    coordinator: Any, definition: Any, plan: SingleWritePlan, refresh: bool
) -> tuple[bool, bool]:
    """Execute retry loop for single-register write."""
    refresh_after_write = False
    for attempt in range(1, coordinator.retry + 1):
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
                    is_final_attempt=attempt == coordinator.retry,
                    final_error_message="Error writing to register %s: %s",
                    retry_message=f"Retrying write to register {plan.register_name}",
                    error_args=(plan.register_name, response),
                )
                if not should_retry:
                    return False, False
                continue

            refresh_after_write = coordinator._handle_successful_single_register_write(
                register_name=plan.register_name,
                original_value=plan.original_value,
                refresh=refresh,
            )
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
    for attempt in range(1, coordinator.retry + 1):
        try:
            response, success = await coordinator._execute_multi_register_chunks(
                coordinator._plan_multi_register_chunks(
                    start_address, values, require_single_request
                ),
                attempt,
            )
            if not success:
                should_retry = coordinator._handle_write_response_failure(
                    is_final_attempt=attempt == coordinator.retry,
                    final_error_message="Error writing registers at %s: %s",
                    retry_message=f"Retrying multi-register write at {start_address}",
                    error_args=(start_address, response),
                )
                if not should_retry:
                    return False, False
                await coordinator._disconnect()
                continue
            refresh_after_write = refresh
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
                return False, False
            continue
    return True, refresh_after_write


async def finalize_write_result(coordinator: Any, refresh_after_write: bool) -> bool:
    """Finish write operation with optional refresh."""
    if refresh_after_write:
        await coordinator._safe_request_refresh()
    return True
