"""Batch read helpers extracted from coordinator IO mixin."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException

from ..registers.read_planner import chunk_register_range
from .retry import _PermanentModbusError

_LOGGER = logging.getLogger(__name__)


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
