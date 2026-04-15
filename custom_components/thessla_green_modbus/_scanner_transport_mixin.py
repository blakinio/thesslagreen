"""Transport / connection-setup mixin for ThesslaGreenDeviceScanner."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import TYPE_CHECKING, Any

from .const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_STOP_BITS,
    HOLDING_BATCH_BOUNDARIES,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
)
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import (
    async_maybe_await_close,
)
from .modbus_helpers import (
    group_reads as _group_reads,
)
from .modbus_transport import (
    BaseModbusTransport,
    RawRtuOverTcpTransport,
    RtuModbusTransport,
    TcpModbusTransport,
)
from .scanner_helpers import SAFE_REGISTERS
from .scanner_register_maps import REGISTER_DEFINITIONS
from .utils import default_connection_mode

if TYPE_CHECKING:  # pragma: no cover
    from pymodbus.client import AsyncModbusTcpClient

    class _ScannerTransportProto:
        host: str
        port: int
        slave_id: int
        timeout: int | float
        retry: int
        backoff: float
        backoff_jitter: float | tuple[float, float] | None
        connection_type: str
        connection_mode: str | None
        serial_port: str
        baud_rate: int
        parity: str
        stop_bits: int
        effective_batch: int
        _transport: BaseModbusTransport | None
        _client: AsyncModbusTcpClient | None
        _resolved_connection_mode: str | None


_LOGGER = logging.getLogger(__name__)


class _ScannerTransportMixin:
    """Connection-setup and transport management for the device scanner."""

    # ------------------------------------------------------------------ #
    # Connection helpers                                                   #
    # ------------------------------------------------------------------ #

    async def close(self) -> None:
        """Close the underlying Modbus client connection."""

        if self._transport is not None:  # type: ignore[attr-defined]
            try:
                await self._transport.close()  # type: ignore[attr-defined]
            except (OSError, ConnectionException, ModbusIOException):
                _LOGGER.debug("Error closing Modbus transport", exc_info=True)
            finally:
                self._transport = None  # type: ignore[attr-defined]

        client = self._client  # type: ignore[attr-defined]
        if client is None:
            return

        try:
            await async_maybe_await_close(client)
        except (OSError, ConnectionException, ModbusIOException):
            _LOGGER.debug("Error closing Modbus client", exc_info=True)
        finally:
            self._client = None  # type: ignore[attr-defined]

    def _build_tcp_transport(
        self,
        mode: str,
        *,
        timeout_override: float | None = None,
    ) -> BaseModbusTransport:
        timeout = self.timeout if timeout_override is None else timeout_override  # type: ignore[attr-defined]
        if mode == CONNECTION_MODE_TCP_RTU:
            return RawRtuOverTcpTransport(
                host=self.host,  # type: ignore[attr-defined]
                port=self.port,  # type: ignore[attr-defined]
                max_retries=self.retry,  # type: ignore[attr-defined]
                base_backoff=self.backoff,  # type: ignore[attr-defined]
                max_backoff=DEFAULT_MAX_BACKOFF,
                timeout=timeout,
            )
        return TcpModbusTransport(
            host=self.host,  # type: ignore[attr-defined]
            port=self.port,  # type: ignore[attr-defined]
            connection_type=CONNECTION_TYPE_TCP,
            max_retries=self.retry,  # type: ignore[attr-defined]
            base_backoff=self.backoff,  # type: ignore[attr-defined]
            max_backoff=DEFAULT_MAX_BACKOFF,
            timeout=timeout,
        )

    def _build_auto_tcp_attempts(self) -> list[tuple[str, BaseModbusTransport, float]]:
        rtu_timeout = min(max(self.timeout, 2.0), 5.0)  # type: ignore[attr-defined]
        tcp_timeout = min(max(self.timeout, 5.0), 10.0)  # type: ignore[attr-defined]
        prefer_tcp = self.port == DEFAULT_PORT  # type: ignore[attr-defined]
        mode_order = (
            [CONNECTION_MODE_TCP, CONNECTION_MODE_TCP_RTU]
            if prefer_tcp
            else [
                CONNECTION_MODE_TCP_RTU,
                CONNECTION_MODE_TCP,
            ]
        )
        attempts: list[tuple[str, BaseModbusTransport, float]] = []
        for mode in mode_order:
            timeout = rtu_timeout if mode == CONNECTION_MODE_TCP_RTU else tcp_timeout
            attempts.append(
                (
                    mode,
                    self._build_tcp_transport(mode, timeout_override=timeout),
                    timeout,
                )
            )
        return attempts

    async def verify_connection(self) -> None:
        """Verify basic Modbus connectivity by reading a few safe registers.

        A handful of well-known registers are read from the device to confirm
        that the TCP connection and Modbus protocol are functioning. Any
        failure will raise a ``ModbusException`` or ``ConnectionException`` so
        callers can surface an appropriate error to the user.
        """

        safe_input: list[int] = []
        safe_holding: list[int] = []
        for func, name in SAFE_REGISTERS:
            reg = REGISTER_DEFINITIONS.get(name)
            if reg is None:
                continue
            if func == 4:
                safe_input.append(reg.address)
            else:
                safe_holding.append(reg.address)

        attempts: list[tuple[str | None, BaseModbusTransport, float]] = []
        if self.connection_type == CONNECTION_TYPE_RTU:  # type: ignore[attr-defined]
            if not self.serial_port:  # type: ignore[attr-defined]
                raise ConnectionException("Serial port not configured")
            parity = SERIAL_PARITY_MAP.get(self.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])  # type: ignore[attr-defined]
            stop_bits = SERIAL_STOP_BITS_MAP.get(
                self.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]  # type: ignore[attr-defined]
            )
            attempts.append(
                (
                    None,
                    RtuModbusTransport(
                        serial_port=self.serial_port,  # type: ignore[attr-defined]
                        baudrate=self.baud_rate,  # type: ignore[attr-defined]
                        parity=parity,
                        stopbits=stop_bits,
                        max_retries=self.retry,  # type: ignore[attr-defined]
                        base_backoff=self.backoff,  # type: ignore[attr-defined]
                        max_backoff=DEFAULT_MAX_BACKOFF,
                        timeout=self.timeout,  # type: ignore[attr-defined]
                    ),
                    self.timeout,  # type: ignore[attr-defined]
                )
            )
        elif self.connection_mode == CONNECTION_MODE_AUTO:  # type: ignore[attr-defined]
            attempts.extend(self._build_auto_tcp_attempts())
        else:
            mode = self.connection_mode or default_connection_mode(self.port)  # type: ignore[attr-defined]
            attempts.append((mode, self._build_tcp_transport(mode), self.timeout))  # type: ignore[attr-defined]

        last_error: Exception | None = None
        closed_transports: set[int] = set()
        for mode, transport, timeout in attempts:
            try:
                _LOGGER.info(
                    "verify_connection: connecting to %s:%s (mode=%s, timeout=%s)",
                    self.host,  # type: ignore[attr-defined]
                    self.port,  # type: ignore[attr-defined]
                    mode or self.connection_type,  # type: ignore[attr-defined]
                    timeout,
                )
                await asyncio.wait_for(transport.ensure_connected(), timeout=timeout)

                for start, count in _group_reads(safe_input, max_block_size=self.effective_batch):  # type: ignore[attr-defined]
                    _LOGGER.debug(
                        "verify_connection: read_input_registers start=%s count=%s",
                        start,
                        count,
                    )
                    await transport.read_input_registers(
                        self.slave_id,  # type: ignore[attr-defined]
                        start,
                        count=count,
                    )

                for start, count in _group_reads(
                    safe_holding,
                    max_block_size=self.effective_batch,  # type: ignore[attr-defined]
                    boundaries=HOLDING_BATCH_BOUNDARIES,
                ):
                    _LOGGER.debug(
                        "verify_connection: read_holding_registers start=%s count=%s",
                        start,
                        count,
                    )
                    await transport.read_holding_registers(
                        self.slave_id,  # type: ignore[attr-defined]
                        start,
                        count=count,
                    )
                if mode is not None:
                    if self.connection_mode == CONNECTION_MODE_AUTO:  # type: ignore[attr-defined]
                        _LOGGER.info(
                            "verify_connection: auto-selected Modbus transport %s for %s:%s",
                            mode,
                            self.host,  # type: ignore[attr-defined]
                            self.port,  # type: ignore[attr-defined]
                        )
                    self._resolved_connection_mode = mode  # type: ignore[attr-defined]
                return
            except asyncio.CancelledError:
                raise
            except ModbusIOException as exc:
                last_error = exc
                from .scanner_io import is_request_cancelled_error

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
                    _LOGGER.debug(
                        "Error closing Modbus transport during verify_connection", exc_info=True
                    )

        if last_error:
            raise last_error

    def _unpack_read_args(
        self,
        client_or_address: Any,
        address_or_count: int,
        count: int | None,
    ) -> tuple[Any, int, int]:
        """Unpack the overloaded (client, address, count) / (address, count) signatures."""
        if count is None or isinstance(client_or_address, int):
            return None, int(client_or_address), address_or_count
        return client_or_address, address_or_count, count

    def _resolve_transport_and_client(
        self,
        client: Any,
    ) -> tuple[Any, Any]:
        """Return (transport, client) ready for reads. Raises if neither available."""
        transport = self._transport if client is None else None  # type: ignore[attr-defined]
        if client is None and transport is None:
            client = self._client  # type: ignore[attr-defined]
        if client is None and transport is None:
            raise ConnectionException("Modbus transport is not connected")
        return transport, client
