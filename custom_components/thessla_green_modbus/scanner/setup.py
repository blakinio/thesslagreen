"""Connection/setup routines for the scanner runtime."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from ..const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_TYPE_RTU,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_PARITY,
    DEFAULT_STOP_BITS,
    HOLDING_BATCH_BOUNDARIES,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
)
from ..modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from ..modbus_helpers import group_reads as _group_reads
from ..modbus_transport import BaseModbusTransport, RtuModbusTransport
from ..scanner_helpers import SAFE_REGISTERS
from ..scanner_register_maps import REGISTER_DEFINITIONS
from ..utils import default_connection_mode
from .io import is_request_cancelled_error

_LOGGER = logging.getLogger(__name__)


async def verify_connection(
    scanner: Any,
    *,
    safe_registers: list[tuple[int, str]] = SAFE_REGISTERS,
    register_definitions: dict[str, Any] = REGISTER_DEFINITIONS,
    holding_batch_boundaries: frozenset[int] = HOLDING_BATCH_BOUNDARIES,
    group_reads: Any = _group_reads,
    rtu_transport_cls: Any = RtuModbusTransport,
) -> None:
    """Verify basic Modbus connectivity by reading a few safe registers."""
    safe_input: list[int] = []
    safe_holding: list[int] = []
    for func, name in safe_registers:
        reg = register_definitions.get(name)
        if reg is None:
            continue
        if func == 4:
            safe_input.append(reg.address)
        else:
            safe_holding.append(reg.address)

    attempts: list[tuple[str | None, BaseModbusTransport, float]] = []
    if scanner.connection_type == CONNECTION_TYPE_RTU:
        if not scanner.serial_port:
            raise ConnectionException("Serial port not configured")
        parity = SERIAL_PARITY_MAP.get(scanner.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])
        stop_bits = SERIAL_STOP_BITS_MAP.get(
            scanner.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]
        )
        attempts.append(
            (
                None,
                rtu_transport_cls(
                    serial_port=scanner.serial_port,
                    baudrate=scanner.baud_rate,
                    parity=parity,
                    stopbits=stop_bits,
                    max_retries=scanner.retry,
                    base_backoff=scanner.backoff,
                    max_backoff=DEFAULT_MAX_BACKOFF,
                    timeout=scanner.timeout,
                ),
                scanner.timeout,
            )
        )
    elif scanner.connection_mode == CONNECTION_MODE_AUTO:
        attempts.extend(scanner._build_auto_tcp_attempts())
    else:
        mode = scanner.connection_mode or default_connection_mode(scanner.port)
        attempts.append((mode, scanner._build_tcp_transport(mode), scanner.timeout))

    last_error: Exception | None = None
    closed_transports: set[int] = set()
    for mode_name, transport, timeout in attempts:
        try:
            _LOGGER.info(
                "verify_connection: connecting to %s:%s (mode=%s, timeout=%s)",
                scanner.host,
                scanner.port,
                mode_name or scanner.connection_type,
                timeout,
            )
            await asyncio.wait_for(transport.ensure_connected(), timeout=timeout)

            for start, count in group_reads(safe_input, max_block_size=scanner.effective_batch):
                _LOGGER.debug(
                    "verify_connection: read_input_registers start=%s count=%s",
                    start,
                    count,
                )
                await transport.read_input_registers(scanner.slave_id, start, count=count)

            for start, count in group_reads(
                safe_holding,
                max_block_size=scanner.effective_batch,
                boundaries=holding_batch_boundaries,
            ):
                _LOGGER.debug(
                    "verify_connection: read_holding_registers start=%s count=%s",
                    start,
                    count,
                )
                await transport.read_holding_registers(scanner.slave_id, start, count=count)

            if mode_name is not None:
                if scanner.connection_mode == CONNECTION_MODE_AUTO:
                    _LOGGER.info(
                        "verify_connection: auto-selected Modbus transport %s for %s:%s",
                        mode_name,
                        scanner.host,
                        scanner.port,
                    )
                scanner._resolved_connection_mode = mode_name
            return
        except asyncio.CancelledError:
            raise
        except ModbusIOException as exc:
            last_error = exc
            if is_request_cancelled_error(exc):
                _LOGGER.info("Modbus request cancelled during verify_connection.")
                raise TimeoutError("Modbus request cancelled") from exc
        except TimeoutError as exc:
            last_error = exc
            _LOGGER.warning("Timeout during verify_connection: %s", exc)
        except (ConnectionException, ModbusException, OSError) as exc:
            last_error = exc
        finally:
            try:
                transport_id = id(transport)
                if transport_id not in closed_transports:
                    close_result = transport.close()
                    if inspect.isawaitable(close_result):
                        await close_result
                    closed_transports.add(transport_id)
            except (OSError, ConnectionException, ModbusIOException):
                _LOGGER.warning(
                    "Error closing Modbus transport during verify_connection", exc_info=True
                )

    if last_error:
        raise last_error
