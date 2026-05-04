"""Write-path orchestration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..modbus_exceptions import ConnectionException, ModbusException


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
