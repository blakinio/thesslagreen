"""Batch read helpers and shared low-level read infrastructure.

Batched holding/input/coil reads plus the shared retry/error helpers (formerly
``core/read_common.py``) used by the coordinator I/O mixin's read-retry paths.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException

from ..registers.read_planner import chunk_register_range
from .retry import _PermanentModbusError

_LOGGER = logging.getLogger(__name__)
ILLEGAL_DATA_ADDRESS = 2


async def _read_holding_fallback(
    owner: Any,
    read_method: Any,
    chunk_start: int,
    register_names: list[str | None],
    data: dict[str, Any],
) -> None:
    """Call owner fallback hook when present, else default helper."""
    fallback = getattr(owner, "_read_holding_individually", None)
    if callable(fallback):
        await fallback(read_method, chunk_start, register_names, data)
        return
    await read_holding_individually(owner, read_method, chunk_start, register_names, data)


def _merge_batch_read_results(
    owner: Any,
    response: Any,
    chunk_start: int,
    data: dict[str, Any],
) -> None:
    """Merge successfully-read batch register values into data."""
    for i, value in enumerate(response.registers):
        addr = chunk_start + i
        register_name = owner._find_register_name("input_registers", addr)
        if (
            register_name
            and register_name in owner.device_client.available_registers["input_registers"]
        ):
            processed_value = owner._process_register_value(register_name, value)
            if processed_value is not None:
                data[register_name] = processed_value
                owner.device_client.statistics["total_registers_read"] += 1
                owner._clear_register_failure(register_name)


async def _fallback_individual_input_reads(
    owner: Any,
    read_method: Any,
    chunk_start: int,
    register_names: list[str | None],
    data: dict[str, Any],
) -> None:
    """Read input registers one-by-one as fallback when a batch returns empty."""
    for idx, reg_name in enumerate(register_names):
        if not reg_name:
            continue
        addr = chunk_start + idx
        try:
            single = await owner._read_with_retry(read_method, addr, 1, register_type="input")
            if single.registers:
                pv = owner._process_register_value(reg_name, single.registers[0])
                if pv is not None:
                    data[reg_name] = pv
                    owner.device_client.statistics["total_registers_read"] += 1
                    owner._clear_register_failure(reg_name)
                else:
                    owner._mark_registers_failed([reg_name])
            else:
                owner._mark_registers_failed([reg_name])
        except _PermanentModbusError:
            owner._mark_registers_failed([reg_name])
        except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError):
            owner._mark_registers_failed([reg_name])


async def _handle_batch_read_failure(
    owner: Any,
    response: Any,
    chunk_count: int,
    register_names: list[str | None],
    read_method: Any,
    chunk_start: int,
    data: dict[str, Any],
) -> None:
    """Handle a partial or empty batch response."""
    if len(response.registers) == 0:
        await _fallback_individual_input_reads(
            owner, read_method, chunk_start, register_names, data
        )
    else:
        missing = register_names[len(response.registers) :]
        owner._mark_registers_failed(missing)


async def _read_input_register_batch(
    owner: Any,
    read_method: Any,
    chunk_start: int,
    chunk_count: int,
    register_names: list[str | None],
    data: dict[str, Any],
    failed: set[str],
) -> None:
    """Read one input register chunk, with fallback on partial or empty response."""
    if all(name in failed for name in register_names if name):
        return
    try:
        response = await owner._read_with_retry(
            read_method, chunk_start, chunk_count, register_type="input"
        )
        _merge_batch_read_results(owner, response, chunk_start, data)
        if len(response.registers) < chunk_count:
            await _handle_batch_read_failure(
                owner, response, chunk_count, register_names, read_method, chunk_start, data
            )
    except _PermanentModbusError:
        owner._mark_registers_failed(register_names)
    except ConnectionException:
        raise
    except (ModbusException, TimeoutError, OSError, ValueError):
        owner._mark_registers_failed(register_names)


async def read_input_registers_optimized(owner: Any) -> dict[str, Any]:
    """Read input registers using optimized batch reading."""
    data: dict[str, Any] = {}

    if "input_registers" not in owner.device_client._register_groups:
        return data

    transport = owner.device_client._transport
    client = owner.device_client.client
    if transport is not None and transport.is_connected():
        read_method = transport.read_input_registers
    elif client is not None and getattr(client, "connected", True):

        async def read_method(slave_id: int, address: int, *, count: int, attempt: int = 1) -> Any:
            return await owner._call_modbus(
                client.read_input_registers,
                address,
                count=count,
                attempt=attempt,
            )
    else:
        raise ConnectionException("Modbus client is not connected")

    failed: set[str] = getattr(owner, "_failed_registers", set())

    for start_addr, count in owner.device_client._register_groups["input_registers"]:
        for chunk_start, chunk_count in chunk_register_range(
            start_addr, count, owner.device_client.effective_batch
        ):
            register_names = [
                owner._find_register_name("input_registers", chunk_start + i)
                for i in range(chunk_count)
            ]
            await _read_input_register_batch(
                owner, read_method, chunk_start, chunk_count, register_names, data, failed
            )

    return data


async def read_holding_individually(
    owner: Any,
    read_method: Any,
    chunk_start: int,
    register_names: list[str | None],
    data: dict[str, Any],
) -> None:
    """Read holding registers one-by-one as fallback when a batch read fails."""
    for idx, reg_name in enumerate(register_names):
        if not reg_name:
            continue
        addr = chunk_start + idx
        try:
            single = await owner._read_with_retry(read_method, addr, 1, register_type="holding")
            if single.registers:
                pv = owner._process_register_value(reg_name, single.registers[0])
                if pv is not None:
                    data[reg_name] = pv
                    owner.device_client.statistics["total_registers_read"] += 1
                    owner._clear_register_failure(reg_name)
                else:
                    owner._mark_registers_failed([reg_name])
            else:
                owner._mark_registers_failed([reg_name])
        except _PermanentModbusError:
            owner._mark_registers_failed([reg_name])
        except ConnectionException:
            raise
        except (ModbusException, TimeoutError, OSError, ValueError):
            owner._mark_registers_failed([reg_name])


async def read_holding_registers_optimized(owner: Any) -> dict[str, Any]:
    """Read holding registers using optimized batch reading."""
    data: dict[str, Any] = {}

    if "holding_registers" not in owner.device_client._register_groups:
        return data

    transport = owner.device_client._transport
    client = owner.device_client.client
    if transport is not None and transport.is_connected():
        read_method = transport.read_holding_registers
    elif client is not None and getattr(client, "connected", True):

        async def read_method(slave_id: int, address: int, *, count: int, attempt: int = 1) -> Any:
            return await owner._call_modbus(
                client.read_holding_registers,
                address,
                count=count,
                attempt=attempt,
            )
    else:
        _LOGGER.debug("Modbus client is not connected")
        return data

    failed: set[str] = getattr(owner, "_failed_registers", set())

    for start_addr, count in owner.device_client._register_groups["holding_registers"]:
        for chunk_start, chunk_count in chunk_register_range(
            start_addr, count, owner.device_client.effective_batch
        ):
            register_names = [
                owner._find_register_name("holding_registers", chunk_start + i)
                for i in range(chunk_count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            try:
                response = await owner._read_with_retry(
                    read_method,
                    chunk_start,
                    chunk_count,
                    register_type="holding",
                )

                for i, value in enumerate(response.registers):
                    addr = chunk_start + i
                    register_name = owner._find_register_name("holding_registers", addr)
                    if (
                        register_name
                        and register_name
                        in owner.device_client.available_registers["holding_registers"]
                    ):
                        processed_value = owner._process_register_value(register_name, value)
                        if processed_value is not None:
                            data[register_name] = processed_value
                            owner.device_client.statistics["total_registers_read"] += 1
                            owner._clear_register_failure(register_name)

                if len(response.registers) < chunk_count:
                    if len(response.registers) == 0:
                        await _read_holding_fallback(
                            owner, read_method, chunk_start, register_names, data
                        )
                    else:
                        tail_offset = len(response.registers)
                        tail_names = register_names[tail_offset:]
                        tail_start = chunk_start + tail_offset
                        await _read_holding_fallback(
                            owner, read_method, tail_start, tail_names, data
                        )
            except _PermanentModbusError:
                owner._mark_registers_failed(register_names)
            except ConnectionException:
                raise
            except (ModbusException, TimeoutError, OSError, ValueError):
                await _read_holding_fallback(owner, read_method, chunk_start, register_names, data)

    return data


# ---------------------------------------------------------------------------
# Shared low-level read helpers (formerly core/read_common.py)
# ---------------------------------------------------------------------------


def is_illegal_data_address_response(response: Any) -> bool:
    """Return True when response reports ILLEGAL DATA ADDRESS."""
    return getattr(response, "exception_code", None) == ILLEGAL_DATA_ADDRESS


def is_transient_error_response(response: Any) -> bool:
    """Return True when response looks transient and should be retried."""
    exception_code = getattr(response, "exception_code", None)
    return exception_code is None or exception_code != ILLEGAL_DATA_ADDRESS


async def execute_read_call(
    device_client: Any,
    read_method: Callable[..., Any],
    start_address: int,
    count: int,
    attempt: int,
) -> Any:
    """Execute one read attempt with method fallback through `_call_modbus`."""
    call_result = read_method(
        device_client.slave_id,
        start_address,
        count=count,
        attempt=attempt,
    )
    if call_result is None:
        call_result = device_client._call_modbus(
            read_method,
            start_address,
            count=count,
            attempt=attempt,
        )
    return await call_result if inspect.isawaitable(call_result) else call_result


def log_read_retry(
    device_client: Any,
    *,
    register_type: str,
    start_address: int,
    attempt: int,
    exc: Exception,
    timeout: bool = False,
) -> None:
    """Log retry information for read failures."""
    if timeout:
        _LOGGER.warning(
            "Timeout reading %s registers at %s (attempt %s/%s)",
            register_type,
            start_address,
            attempt,
            device_client.retry,
        )
    _LOGGER.debug(
        "Retrying %s registers at %s (attempt %s/%s): %s",
        register_type,
        start_address,
        attempt + 1,
        device_client.retry,
        exc,
    )


def raise_for_error_response(
    device_client: Any,
    response: Any,
    *,
    register_type: str,
    start_address: int,
) -> None:
    """Raise specific exception for Modbus error responses."""
    if not response.isError():
        return
    if is_illegal_data_address_response(response):
        raise _PermanentModbusError(
            f"Illegal data address for {register_type} registers at {start_address}"
        )
    if is_transient_error_response(response):
        raise ModbusIOException(
            f"Transient error reading {register_type} registers at {start_address}"
        )
    raise ModbusException(
        # pragma: no cover - impossible: not illegal and not transient implies illegal
        f"Failed to read {register_type} registers at {start_address}"
    )
