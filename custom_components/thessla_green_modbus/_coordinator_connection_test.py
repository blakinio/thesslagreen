"""Connection test helpers for coordinator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_transport import BaseModbusTransport


async def run_connection_test(
    *,
    ensure_connection: Callable[[], Awaitable[None]],
    get_transport: Callable[[], BaseModbusTransport | None],
    slave_id: int,
    test_addresses: Iterable[int],
    is_cancelled_error: Callable[[Exception], bool],
    logger: Any,
) -> None:
    """Execute initial modbus connection/read probe sequence."""

    try:
        await ensure_connection()

        transport = get_transport()
        if transport is None:
            raise ConnectionException("Modbus transport is not connected")

        for addr in test_addresses:
            response = await transport.read_input_registers(
                slave_id,
                addr,
                count=1,
            )
            if response is None:
                raise ConnectionException(f"Cannot read register {addr}")

        if not transport.is_connected():
            raise ConnectionException("Modbus transport is not connected")

        response = await transport.read_input_registers(
            slave_id,
            0,
            count=1,
        )
        if response is None:
            raise ConnectionException("Cannot read basic register")
        logger.debug("Connection test successful")
    except ModbusIOException as exc:
        if is_cancelled_error(exc):
            logger.warning("Connection test skipped — device busy after scan: %s", exc)
            return
        logger.exception("Connection test failed: %s", exc)
        raise
    except (ModbusException, ConnectionException) as exc:
        logger.exception("Connection test failed: %s", exc)
        raise
    except TimeoutError as exc:
        logger.warning("Connection test timed out: %s", exc)
        raise
    except OSError as exc:
        logger.exception("Unexpected error during connection test: %s", exc)
        raise
