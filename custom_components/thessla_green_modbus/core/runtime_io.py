"""Shared runtime I/O helpers for coordinator mixin delegation."""

from __future__ import annotations

from typing import Any, cast

from pymodbus.exceptions import ConnectionException

from ..modbus.call import _call_modbus


async def call_modbus(
    device_client: Any,
    func: Any,
    *args: Any,
    attempt: int = 1,
    **kwargs: Any,
) -> Any:
    """Wrapper around Modbus calls injecting the slave ID."""
    if device_client._transport is None:
        if not device_client.client:
            raise ConnectionException("Modbus client is not connected")
        return await _call_modbus(
            func,
            device_client.slave_id,
            *args,
            attempt=attempt,
            max_attempts=device_client.retry,
            timeout=device_client.timeout,
            backoff=device_client.backoff,
            backoff_jitter=device_client.backoff_jitter,
            **kwargs,
        )
    return await device_client._transport.call(
        func,
        device_client.slave_id,
        *args,
        attempt=attempt,
        max_attempts=device_client.retry,
        backoff=device_client.backoff,
        backoff_jitter=device_client.backoff_jitter,
        **kwargs,
    )


async def read_all_register_data(device_client: Any) -> dict[str, Any]:
    """Read all mapped register groups and run post-processing."""
    data: dict[str, Any] = {}
    data.update(await device_client._read_input_registers_optimized())
    data.update(await device_client._read_holding_registers_optimized())
    data.update(await device_client._read_coil_registers_optimized())
    data.update(await device_client._read_discrete_inputs_optimized())
    return cast(dict[str, Any], cast(Any, device_client)._post_process_data(data))
