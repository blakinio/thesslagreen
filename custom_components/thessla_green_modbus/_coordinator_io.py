"""Modbus I/O mixin extracted from the coordinator."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, cast

from homeassistant.helpers.update_coordinator import UpdateFailed

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import _call_modbus, chunk_register_range

if TYPE_CHECKING:
    from .modbus_transport import BaseModbusTransport

    class _PostProcessProtocol:
        def _post_process_data(self, data: dict[str, Any]) -> dict[str, Any]: ...

_LOGGER = logging.getLogger(__name__)
ILLEGAL_DATA_ADDRESS = 2


async def handle_update_error(
    coordinator: Any,
    exc: Exception,
    *,
    reauth_reason: str,
    message: str,
    log_level: int = logging.ERROR,
    timeout_error: bool = False,
    check_auth: bool = False,
    use_helper: bool = True,
) -> UpdateFailed:
    """Shared error-handling path for coordinator update failures."""
    from .errors import is_invalid_auth_error

    coordinator.statistics["failed_reads"] += 1
    if timeout_error:
        coordinator.statistics["timeout_errors"] += 1
    coordinator.statistics["last_error"] = str(exc)
    coordinator._consecutive_failures += 1
    coordinator.offline_state = True
    await coordinator._disconnect()

    if coordinator._consecutive_failures >= coordinator._max_failures:
        _LOGGER.error("Too many consecutive failures, disconnecting")
        coordinator._trigger_reauth(reauth_reason)

    if check_auth and is_invalid_auth_error(exc):
        coordinator._trigger_reauth("invalid_auth")

    _LOGGER.log(log_level, "%s: %s", message, exc)
    full_message = f"{message}: {exc}"
    if use_helper and hasattr(coordinator, "_resolve_update_failure"):
        return coordinator._resolve_update_failure(exc, default_message=full_message)
    return UpdateFailed(full_message)


class _PermanentModbusError(ModbusException):
    """Modbus error that should not be retried."""


class _ModbusIOMixin:
    """Read-path Modbus methods used by the coordinator.

    Attributes and stub methods declared below are provided by
    ``ThesslaGreenModbusCoordinator`` and sibling mixins at runtime.
    They allow mypy to type-check this mixin in isolation.
    """

    # Transport / connection
    _transport: BaseModbusTransport | None
    client: Any | None
    slave_id: int
    timeout: float
    retry: int
    backoff: float
    backoff_jitter: float | tuple[float, float] | None

    # Runtime state
    statistics: dict[str, Any]
    available_registers: dict[str, set[str]]
    _register_groups: dict[str, list[tuple[int, int]]]
    effective_batch: int
    _failed_registers: set[str]

    async def _ensure_connection(self) -> None: ...
    def _find_register_name(self, register_type: str, address: int) -> str | None: ...
    def _process_register_value(self, register_name: str, value: int) -> Any: ...
    def _clear_register_failure(self, name: str) -> None: ...
    def _mark_registers_failed(self, names: Iterable[str | None]) -> None: ...
    async def _read_coils_transport(
        self, slave_id: int, address: int, *, count: int, attempt: int = 1
    ) -> Any: ...
    async def _read_discrete_inputs_transport(
        self, slave_id: int, address: int, *, count: int, attempt: int = 1
    ) -> Any: ...

    async def _call_modbus(
        self, func: Callable[..., Any], *args: Any, attempt: int = 1, **kwargs: Any
    ) -> Any:
        """Wrapper around Modbus calls injecting the slave ID."""
        if self._transport is None:
            if not self.client:
                raise ConnectionException("Modbus client is not connected")
            return await _call_modbus(
                func,
                self.slave_id,
                *args,
                attempt=attempt,
                max_attempts=self.retry,
                timeout=self.timeout,
                backoff=self.backoff,
                backoff_jitter=self.backoff_jitter,
                **kwargs,
            )
        return await self._transport.call(
            func,
            self.slave_id,
            *args,
            attempt=attempt,
            max_attempts=self.retry,
            backoff=self.backoff,
            backoff_jitter=self.backoff_jitter,
            **kwargs,
        )

    async def _read_all_register_data(self) -> dict[str, Any]:
        """Read all mapped register groups and run post-processing."""
        data: dict[str, Any] = {}
        data.update(await self._read_input_registers_optimized())
        data.update(await self._read_holding_registers_optimized())
        data.update(await self._read_coil_registers_optimized())
        data.update(await self._read_discrete_inputs_optimized())
        return cast("_PostProcessProtocol", self)._post_process_data(data)

    @staticmethod
    def _is_illegal_data_address_response(response: Any) -> bool:
        """Return True when response reports ILLEGAL DATA ADDRESS."""
        return getattr(response, "exception_code", None) == ILLEGAL_DATA_ADDRESS

    @staticmethod
    def _is_transient_error_response(response: Any) -> bool:
        """Return True when response looks transient and should be retried."""
        exception_code = getattr(response, "exception_code", None)
        return exception_code is None or exception_code != ILLEGAL_DATA_ADDRESS

    async def _execute_read_call(
        self,
        read_method: Callable[..., Any],
        start_address: int,
        count: int,
        attempt: int,
    ) -> Any:
        """Execute one read attempt with method fallback through `_call_modbus`."""
        call_result = read_method(
            self.slave_id,
            start_address,
            count=count,
            attempt=attempt,
        )
        if call_result is None:
            call_result = self._call_modbus(
                read_method,
                start_address,
                count=count,
                attempt=attempt,
            )
        return await call_result if inspect.isawaitable(call_result) else call_result

    async def _disconnect_and_reconnect_for_retry(
        self,
        *,
        register_type: str,
        start_address: int,
        attempt: int,
    ) -> Exception | None:
        """Reset connection before retry and reconnect transport if available."""
        disconnect_cb = getattr(self, "_disconnect", None)
        if callable(disconnect_cb):
            await disconnect_cb()  # pragma: no cover

        if self._transport is None:  # pragma: no cover
            return None

        try:
            await self._ensure_connection()
        except (
            TimeoutError,
            ModbusIOException,
            ConnectionException,
            OSError,
        ) as reconnect:
            _LOGGER.debug(
                "Reconnect failed for %s registers at %s (attempt %s/%s): %s",
                register_type,
                start_address,
                attempt + 1,
                self.retry,
                reconnect,
            )
            return reconnect
        return None

    def _log_read_retry(
        self,
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
                self.retry,
            )
        _LOGGER.debug(
            "Retrying %s registers at %s (attempt %s/%s): %s",
            register_type,
            start_address,
            attempt + 1,
            self.retry,
            exc,
        )

    def _raise_for_error_response(
        self,
        response: Any,
        *,
        register_type: str,
        start_address: int,
    ) -> None:
        """Raise specific exception for Modbus error responses."""
        if not response.isError():
            return
        if self._is_illegal_data_address_response(response):
            raise _PermanentModbusError(
                f"Illegal data address for {register_type} registers at {start_address}"
            )
        if self._is_transient_error_response(response):
            raise ModbusIOException(
                f"Transient error reading {register_type} registers at {start_address}"
            )
        raise ModbusException(
            # pragma: no cover - impossible: not illegal and not transient implies illegal
            f"Failed to read {register_type} registers at {start_address}"
        )

    async def _read_with_retry(
        self,
        read_method: Callable[..., Any],
        start_address: int,
        count: int,
        *,
        register_type: str,
    ) -> Any:
        """Read registers with retry/backoff on transient transport errors."""

        last_error: Exception | None = None
        for attempt in range(1, self.retry + 1):
            try:
                response = await self._execute_read_call(
                    read_method,
                    start_address,
                    count,
                    attempt,
                )
                if response is None:
                    raise ModbusException(
                        f"Failed to read {register_type} registers at {start_address}"
                    )
                self._raise_for_error_response(
                    response,
                    register_type=register_type,
                    start_address=start_address,
                )
                return response
            except _PermanentModbusError:
                raise
            except TimeoutError as exc:
                last_error = exc
                if attempt >= self.retry:
                    raise  # pragma: no cover
                reconnect_error = await self._disconnect_and_reconnect_for_retry(
                    register_type=register_type,
                    start_address=start_address,
                    attempt=attempt,
                )
                if reconnect_error is not None:
                    last_error = reconnect_error
                    continue
                self._log_read_retry(
                    register_type=register_type,
                    start_address=start_address,
                    attempt=attempt,
                    exc=exc,
                    timeout=True,
                )
            except (ModbusIOException, ConnectionException, OSError) as exc:
                last_error = exc
                if attempt >= self.retry:
                    raise
                reconnect_error = await self._disconnect_and_reconnect_for_retry(
                    register_type=register_type,
                    start_address=start_address,
                    attempt=attempt,
                )
                if reconnect_error is not None:
                    last_error = reconnect_error
                    continue
                self._log_read_retry(
                    register_type=register_type,
                    start_address=start_address,
                    attempt=attempt,
                    exc=exc,
                )
            except ModbusException as exc:
                last_error = exc
                if attempt >= self.retry:
                    raise
                self._log_read_retry(
                    register_type=register_type,
                    start_address=start_address,
                    attempt=attempt,
                    exc=exc,
                )
                continue
        if last_error is not None:  # pragma: no cover
            raise last_error  # pragma: no cover
        raise ModbusException(
            f"Failed to read {register_type} registers at {start_address}"
        )  # pragma: no cover

    async def _read_input_registers_optimized(self) -> dict[str, Any]:
        """Read input registers using optimized batch reading."""
        data: dict[str, Any] = {}

        if "input_registers" not in self._register_groups:
            return data

        transport = self._transport
        client = self.client
        if transport is not None and transport.is_connected():
            read_method = transport.read_input_registers
        elif client is not None and getattr(client, "connected", True):

            async def read_method(
                slave_id: int, address: int, *, count: int, attempt: int = 1
            ) -> Any:
                return await self._call_modbus(
                    client.read_input_registers,
                    address,
                    count=count,
                    attempt=attempt,
                )
        else:
            raise ConnectionException("Modbus client is not connected")

        failed: set[str] = getattr(self, "_failed_registers", set())

        for start_addr, count in self._register_groups["input_registers"]:
            for chunk_start, chunk_count in chunk_register_range(
                start_addr, count, self.effective_batch
            ):
                register_names = [
                    self._find_register_name("input_registers", chunk_start + i)
                    for i in range(chunk_count)
                ]
                if all(name in failed for name in register_names if name):
                    continue
                try:
                    response = await self._read_with_retry(
                        read_method,
                        chunk_start,
                        chunk_count,
                        register_type="input",
                    )

                    for i, value in enumerate(response.registers):
                        addr = chunk_start + i
                        register_name = self._find_register_name("input_registers", addr)
                        if (
                            register_name
                            and register_name in self.available_registers["input_registers"]
                        ):
                            processed_value = self._process_register_value(register_name, value)
                            if processed_value is not None:
                                data[register_name] = processed_value
                                self.statistics["total_registers_read"] += 1
                                self._clear_register_failure(register_name)
                                _LOGGER.debug(
                                    "Read input %d (%s) = %s",
                                    addr,
                                    register_name,
                                    processed_value,
                                )

                    if len(response.registers) < chunk_count:
                        if len(response.registers) == 0:
                            # Batch returned nothing — fall back to individual reads
                            for idx, reg_name in enumerate(register_names):
                                if not reg_name:
                                    continue
                                addr = chunk_start + idx
                                try:
                                    single = await self._read_with_retry(
                                        read_method, addr, 1, register_type="input"
                                    )
                                    if single.registers:
                                        pv = self._process_register_value(
                                            reg_name, single.registers[0]
                                        )
                                        if pv is not None:
                                            data[reg_name] = pv
                                            self.statistics["total_registers_read"] += 1
                                            self._clear_register_failure(reg_name)
                                            _LOGGER.debug(
                                                "Read input %d (%s) = %s (individual fallback)",
                                                addr,
                                                reg_name,
                                                pv,
                                            )
                                        else:
                                            self._mark_registers_failed([reg_name])
                                    else:
                                        self._mark_registers_failed([reg_name])
                                except _PermanentModbusError:
                                    self._mark_registers_failed([reg_name])
                                except (
                                    ModbusException,
                                    ConnectionException,
                                    TimeoutError,
                                    OSError,
                                    ValueError,
                                ):
                                    self._mark_registers_failed([reg_name])
                        else:
                            missing = register_names[len(response.registers) :]
                            self._mark_registers_failed(missing)
                except _PermanentModbusError:
                    self._mark_registers_failed(register_names)
                    continue
                except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError):
                    self._mark_registers_failed(register_names)
                    continue

        return data

    async def _read_holding_individually(
        self,
        read_method: Any,
        chunk_start: int,
        register_names: list[str | None],
        data: dict[str, Any],
    ) -> None:
        """Read holding registers one-by-one as fallback when a batch read fails.

        Called both when the device returns an empty batch (len == 0) and when
        the batch raises a Modbus exception (e.g. AirPack4 FW 3.11 bug on
        schedule_summer addr 15-30 which returns corrupt bytes instead of data).
        """
        for idx, reg_name in enumerate(register_names):
            if not reg_name:
                continue
            addr = chunk_start + idx
            try:
                single = await self._read_with_retry(read_method, addr, 1, register_type="holding")
                if single.registers:
                    pv = self._process_register_value(reg_name, single.registers[0])
                    if pv is not None:
                        data[reg_name] = pv
                        self.statistics["total_registers_read"] += 1
                        self._clear_register_failure(reg_name)
                        _LOGGER.debug(
                            "Read holding %d (%s) = %s (individual fallback)",
                            addr,
                            reg_name,
                            pv,
                        )
                    else:
                        self._mark_registers_failed([reg_name])
                else:
                    self._mark_registers_failed([reg_name])
            except _PermanentModbusError:
                self._mark_registers_failed([reg_name])
            except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError):
                self._mark_registers_failed([reg_name])

    async def _read_holding_registers_optimized(self) -> dict[str, Any]:
        """Read holding registers using optimized batch reading."""
        data: dict[str, Any] = {}

        if "holding_registers" not in self._register_groups:
            return data

        transport = self._transport
        client = self.client
        if transport is not None and transport.is_connected():
            read_method = transport.read_holding_registers
        elif client is not None and getattr(client, "connected", True):

            async def read_method(
                slave_id: int, address: int, *, count: int, attempt: int = 1
            ) -> Any:
                return await self._call_modbus(
                    client.read_holding_registers,
                    address,
                    count=count,
                    attempt=attempt,
                )
        else:
            _LOGGER.warning("Modbus client is not connected")
            return data

        failed: set[str] = getattr(self, "_failed_registers", set())

        for start_addr, count in self._register_groups["holding_registers"]:
            for chunk_start, chunk_count in chunk_register_range(
                start_addr, count, self.effective_batch
            ):
                register_names = [
                    self._find_register_name("holding_registers", chunk_start + i)
                    for i in range(chunk_count)
                ]
                if all(name in failed for name in register_names if name):
                    continue
                try:
                    response = await self._read_with_retry(
                        read_method,
                        chunk_start,
                        chunk_count,
                        register_type="holding",
                    )

                    for i, value in enumerate(response.registers):
                        addr = chunk_start + i
                        register_name = self._find_register_name("holding_registers", addr)
                        if (
                            register_name
                            and register_name in self.available_registers["holding_registers"]
                        ):
                            processed_value = self._process_register_value(register_name, value)
                            if processed_value is not None:
                                data[register_name] = processed_value
                                self.statistics["total_registers_read"] += 1
                                self._clear_register_failure(register_name)
                                _LOGGER.debug(
                                    "Read holding %d (%s) = %s",
                                    addr,
                                    register_name,
                                    processed_value,
                                )

                    if len(response.registers) < chunk_count:
                        if len(response.registers) == 0:
                            # Batch returned nothing — fall back to individual reads
                            await self._read_holding_individually(
                                read_method, chunk_start, register_names, data
                            )
                        else:
                            # Partial response (e.g. AirPack4 FW 3.11 returns
                            # fewer registers than requested on schedule_summer
                            # batches). Retry the missing tail with single-
                            # register reads instead of marking it failed —
                            # otherwise post-write refresh skips the chunk and
                            # the UI reverts to the stale value.
                            tail_offset = len(response.registers)
                            tail_names = register_names[tail_offset:]
                            tail_start = chunk_start + tail_offset
                            await self._read_holding_individually(
                                read_method, tail_start, tail_names, data
                            )
                except _PermanentModbusError:
                    self._mark_registers_failed(register_names)
                except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError):
                    # Batch raised an exception (e.g. firmware bug returning corrupt bytes).
                    # Attempt individual reads so writes remain visible on the next poll.
                    await self._read_holding_individually(
                        read_method, chunk_start, register_names, data
                    )

        return data

    async def _read_coil_registers_optimized(self) -> dict[str, Any]:
        """Read coil registers using optimized batch reading."""
        data: dict[str, Any] = {}

        if "coil_registers" not in self._register_groups:
            return data

        client = self.client
        if client is None or not getattr(client, "connected", True):
            raise ConnectionException("Modbus client is not connected")

        failed: set[str] = getattr(self, "_failed_registers", set())

        for start_addr, count in self._register_groups["coil_registers"]:
            for chunk_start, chunk_count in chunk_register_range(
                start_addr, count, self.effective_batch
            ):
                register_names = [
                    self._find_register_name("coil_registers", chunk_start + i)
                    for i in range(chunk_count)
                ]
                if all(name in failed for name in register_names if name):
                    continue
                try:
                    response = await self._read_with_retry(
                        self._read_coils_transport,
                        chunk_start,
                        chunk_count,
                        register_type="coil",
                    )

                    if not response.bits:
                        self._mark_registers_failed(register_names)
                        raise ModbusException(f"No bits returned at {chunk_start}")

                    for i in range(min(chunk_count, len(response.bits))):
                        addr = chunk_start + i
                        register_name = self._find_register_name("coil_registers", addr)
                        if (
                            register_name
                            and register_name in self.available_registers["coil_registers"]
                        ):
                            bit = response.bits[i]
                            data[register_name] = bit
                            self.statistics["total_registers_read"] += 1
                            self._clear_register_failure(register_name)
                            _LOGGER.debug(
                                "Read coil %d (%s) = %s",
                                addr,
                                register_name,
                                bit,
                            )

                    if len(response.bits) < chunk_count:
                        missing = register_names[len(response.bits) :]
                        self._mark_registers_failed(missing)
                except _PermanentModbusError:
                    self._mark_registers_failed(register_names)
                    continue
                except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError):
                    self._mark_registers_failed(register_names)
                    raise

        return data

    async def _read_discrete_inputs_optimized(self) -> dict[str, Any]:  # pragma: no cover
        """Read discrete input registers using optimized batch reading."""
        data: dict[str, Any] = {}

        if "discrete_inputs" not in self._register_groups:
            return data

        client = self.client
        if client is None or not getattr(client, "connected", True):
            raise ConnectionException("Modbus client is not connected")

        failed: set[str] = getattr(self, "_failed_registers", set())

        for start_addr, count in self._register_groups["discrete_inputs"]:
            for chunk_start, chunk_count in chunk_register_range(
                start_addr, count, self.effective_batch
            ):
                register_names = [
                    self._find_register_name("discrete_inputs", chunk_start + i)
                    for i in range(chunk_count)
                ]
                if all(name in failed for name in register_names if name):
                    continue
                try:
                    response = await self._read_with_retry(
                        self._read_discrete_inputs_transport,
                        chunk_start,
                        chunk_count,
                        register_type="discrete",
                    )

                    if not response.bits:
                        self._mark_registers_failed(register_names)
                        raise ModbusException(f"No bits returned at {chunk_start}")

                    for i in range(min(chunk_count, len(response.bits))):
                        addr = chunk_start + i
                        register_name = self._find_register_name("discrete_inputs", addr)
                        if (
                            register_name
                            and register_name in self.available_registers["discrete_inputs"]
                        ):
                            bit = response.bits[i]
                            data[register_name] = bit
                            self.statistics["total_registers_read"] += 1
                            self._clear_register_failure(register_name)
                            _LOGGER.debug(
                                "Read discrete %d (%s) = %s",
                                addr,
                                register_name,
                                bit,
                            )

                    if len(response.bits) < chunk_count:
                        missing = register_names[len(response.bits) :]
                        self._mark_registers_failed(missing)
                except _PermanentModbusError:
                    self._mark_registers_failed(register_names)
                    continue
                except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError):
                    self._mark_registers_failed(register_names)
                    raise

        return data
