"""Transport auto-selection helpers for coordinator."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from .const import CONNECTION_MODE_TCP, CONNECTION_MODE_TCP_RTU, DEFAULT_PORT
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_transport import BaseModbusTransport


async def select_auto_transport(
    *,
    resolved_connection_mode: str | None,
    build_tcp_transport: Callable[[str], BaseModbusTransport],
    try_direct_client_connect: Callable[[bool], Awaitable[bool]],
    port: int,
    timeout: float,
    slave_id: int,
    host: str,
    logger: logging.Logger,
) -> tuple[BaseModbusTransport | None, str | None]:
    """Attempt auto-detection between RTU-over-TCP and Modbus TCP."""

    if resolved_connection_mode:
        return build_tcp_transport(resolved_connection_mode), resolved_connection_mode

    prefer_tcp = port == DEFAULT_PORT
    mode_order = (
        [CONNECTION_MODE_TCP, CONNECTION_MODE_TCP_RTU]
        if prefer_tcp
        else [CONNECTION_MODE_TCP_RTU, CONNECTION_MODE_TCP]
    )
    attempts: list[tuple[str, float]] = []
    for mode in mode_order:
        mode_timeout = 5.0 if mode == CONNECTION_MODE_TCP_RTU else min(max(timeout, 5.0), 10.0)
        attempts.append((mode, mode_timeout))
    last_error: Exception | None = None

    try:
        if await try_direct_client_connect(True):
            return None, None
    except (
        ModbusException,
        ConnectionException,
        ModbusIOException,
        TimeoutError,
        OSError,
        TypeError,
        ValueError,
        AttributeError,
    ) as exc:
        logger.debug("Direct client connect attempt failed, trying transports: %s", exc)

    for mode, mode_timeout in attempts:
        transport = build_tcp_transport(mode)
        try:
            await asyncio.wait_for(transport.ensure_connected(), timeout=3.0)
            try:
                await asyncio.wait_for(
                    transport.read_holding_registers(slave_id, 0, count=2),
                    timeout=mode_timeout,
                )
            except (ModbusIOException, ConnectionException):
                raise
            except ModbusException as exc:
                logger.debug("Protocol probe: Modbus error code = valid protocol (%s)", exc)
        except (
            ModbusException,
            ConnectionException,
            ModbusIOException,
            TimeoutError,
            OSError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:  # pragma: no cover - network dependent
            last_error = exc
            await transport.close()
            continue

        logger.info("Auto-selected Modbus transport %s for %s:%s", mode, host, port)
        return transport, mode

    raise ConnectionException("Auto-detect Modbus transport failed") from last_error
