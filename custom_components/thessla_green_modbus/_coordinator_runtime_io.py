"""Shared runtime I/O helpers for coordinator mixin delegation."""

from __future__ import annotations

from typing import Any, cast

from .modbus_exceptions import ConnectionException
from .modbus_helpers import _call_modbus


async def call_modbus(
    coordinator: Any,
    func: Any,
    *args: Any,
    attempt: int = 1,
    **kwargs: Any,
) -> Any:
    """Wrapper around Modbus calls injecting the slave ID."""
    if coordinator._transport is None:
        if not coordinator.client:
            raise ConnectionException("Modbus client is not connected")
        return await _call_modbus(
            func,
            coordinator.slave_id,
            *args,
            attempt=attempt,
            max_attempts=coordinator.retry,
            timeout=coordinator.timeout,
            backoff=coordinator.backoff,
            backoff_jitter=coordinator.backoff_jitter,
            **kwargs,
        )
    return await coordinator._transport.call(
        func,
        coordinator.slave_id,
        *args,
        attempt=attempt,
        max_attempts=coordinator.retry,
        backoff=coordinator.backoff,
        backoff_jitter=coordinator.backoff_jitter,
        **kwargs,
    )


async def read_all_register_data(coordinator: Any) -> dict[str, Any]:
    """Read all mapped register groups and run post-processing."""
    data: dict[str, Any] = {}
    data.update(await coordinator._read_input_registers_optimized())
    data.update(await coordinator._read_holding_registers_optimized())
    data.update(await coordinator._read_coil_registers_optimized())
    data.update(await coordinator._read_discrete_inputs_optimized())
    return cast(dict[str, Any], cast(Any, coordinator)._post_process_data(data))
