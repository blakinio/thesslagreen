"""Coil/discrete batch read helpers extracted from coordinator IO mixin."""

from __future__ import annotations

from typing import Any

from ._coordinator_retry import _PermanentModbusError
from .modbus_exceptions import ConnectionException, ModbusException
from .modbus_helpers import chunk_register_range


async def read_coil_registers_optimized(owner: Any) -> dict[str, Any]:
    """Read coil registers using optimized batch reading."""
    data: dict[str, Any] = {}

    if "coil_registers" not in owner._register_groups:
        return data

    client = owner.client
    if client is None or not getattr(client, "connected", True):
        raise ConnectionException("Modbus client is not connected")

    failed: set[str] = getattr(owner, "_failed_registers", set())

    for start_addr, count in owner._register_groups["coil_registers"]:
        for chunk_start, chunk_count in chunk_register_range(
            start_addr, count, owner.effective_batch
        ):
            register_names = [
                owner._find_register_name("coil_registers", chunk_start + i)
                for i in range(chunk_count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            try:
                response = await owner._read_with_retry(
                    owner._read_coils_transport,
                    chunk_start,
                    chunk_count,
                    register_type="coil",
                )

                if not response.bits:
                    owner._mark_registers_failed(register_names)
                    raise ModbusException(f"No bits returned at {chunk_start}")

                for i in range(min(chunk_count, len(response.bits))):
                    addr = chunk_start + i
                    register_name = owner._find_register_name("coil_registers", addr)
                    if (
                        register_name
                        and register_name in owner.available_registers["coil_registers"]
                    ):
                        bit = response.bits[i]
                        data[register_name] = bit
                        owner.statistics["total_registers_read"] += 1
                        owner._clear_register_failure(register_name)

                if len(response.bits) < chunk_count:
                    missing = register_names[len(response.bits) :]
                    owner._mark_registers_failed(missing)
            except _PermanentModbusError:
                owner._mark_registers_failed(register_names)
                continue
            except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError):
                owner._mark_registers_failed(register_names)
                raise

    return data


async def read_discrete_inputs_optimized(owner: Any) -> dict[str, Any]:
    """Read discrete input registers using optimized batch reading."""
    data: dict[str, Any] = {}

    if "discrete_inputs" not in owner._register_groups:
        return data

    client = owner.client
    if client is None or not getattr(client, "connected", True):
        raise ConnectionException("Modbus client is not connected")

    failed: set[str] = getattr(owner, "_failed_registers", set())

    for start_addr, count in owner._register_groups["discrete_inputs"]:
        for chunk_start, chunk_count in chunk_register_range(
            start_addr, count, owner.effective_batch
        ):
            register_names = [
                owner._find_register_name("discrete_inputs", chunk_start + i)
                for i in range(chunk_count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            try:
                response = await owner._read_with_retry(
                    owner._read_discrete_inputs_transport,
                    chunk_start,
                    chunk_count,
                    register_type="discrete",
                )

                if not response.bits:
                    owner._mark_registers_failed(register_names)
                    raise ModbusException(f"No bits returned at {chunk_start}")

                for i in range(min(chunk_count, len(response.bits))):
                    addr = chunk_start + i
                    register_name = owner._find_register_name("discrete_inputs", addr)
                    if (
                        register_name
                        and register_name in owner.available_registers["discrete_inputs"]
                    ):
                        bit = response.bits[i]
                        data[register_name] = bit
                        owner.statistics["total_registers_read"] += 1
                        owner._clear_register_failure(register_name)

                if len(response.bits) < chunk_count:
                    missing = register_names[len(response.bits) :]
                    owner._mark_registers_failed(missing)
            except _PermanentModbusError:
                owner._mark_registers_failed(register_names)
                continue
            except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError):
                owner._mark_registers_failed(register_names)
                raise

    return data
