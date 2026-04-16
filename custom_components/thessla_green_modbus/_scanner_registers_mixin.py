"""Raw Modbus read operations mixin for ThesslaGreenDeviceScanner."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, cast

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import chunk_register_range
from .scanner_helpers import _format_register_value

if TYPE_CHECKING:  # pragma: no cover
    from pymodbus.client import AsyncModbusTcpClient

    from .modbus_transport import BaseModbusTransport

    class _ScannerRegistersProto:
        slave_id: int
        timeout: int | float
        retry: int
        backoff: float
        backoff_jitter: float | tuple[float, float] | None
        verbose_invalid_values: bool
        effective_batch: int
        _client: AsyncModbusTcpClient | None
        _transport: BaseModbusTransport | None
        _failed_input: set[int]
        _failed_holding: set[int]
        _input_failures: dict[int, int]
        _holding_failures: dict[int, int]
        _input_skip_log_ranges: set[tuple[int, int]]
        _unsupported_input_ranges: dict[tuple[int, int], int]
        _unsupported_holding_ranges: dict[tuple[int, int], int]
        _reported_invalid: set[str]
        failed_addresses: dict[str, dict[str, set[int]]]


_LOGGER = logging.getLogger(__name__)


class _ScannerRegistersMixin:
    """Raw Modbus read operations for the device scanner."""

    _client: AsyncModbusTcpClient | None

    def _filter_unsupported_addresses(self, reg_type: str, addrs: set[int]) -> set[int]:
        """Return failed addresses that are not already covered by unsupported spans."""

        if reg_type == "input_registers":
            ranges = self._unsupported_input_ranges  # type: ignore[attr-defined]
        elif reg_type == "holding_registers":
            ranges = self._unsupported_holding_ranges  # type: ignore[attr-defined]
        else:
            return set(addrs)

        if not ranges:
            return set(addrs)

        return {addr for addr in addrs if not any(start <= addr <= end for start, end in ranges)}

    def _log_invalid_value(self, name: str, raw: int) -> None:
        """Log a register value that failed validation."""
        if name in self._reported_invalid:  # type: ignore[attr-defined]
            if not self.verbose_invalid_values:  # type: ignore[attr-defined]
                return
            level = logging.DEBUG
        else:
            level = logging.INFO if self.verbose_invalid_values else logging.DEBUG  # type: ignore[attr-defined]
            self._reported_invalid.add(name)  # type: ignore[attr-defined]
        decoded = _format_register_value(name, raw)
        _LOGGER.log(level, "Invalid value for %s: raw=%d decoded=%s", name, raw, decoded)

    def _mark_input_supported(self, address: int) -> None:
        """Remove address from cached unsupported input ranges after success."""
        self._failed_input.discard(address)  # type: ignore[attr-defined]
        for (start, end), code in list(self._unsupported_input_ranges.items()):  # type: ignore[attr-defined]
            if start <= address <= end:
                del self._unsupported_input_ranges[(start, end)]  # type: ignore[attr-defined]
                if start <= address - 1:
                    self._unsupported_input_ranges[(start, address - 1)] = code  # type: ignore[attr-defined]
                if address + 1 <= end:
                    self._unsupported_input_ranges[(address + 1, end)] = code  # type: ignore[attr-defined]

    def _mark_holding_supported(self, address: int) -> None:
        """Remove address from cached unsupported holding ranges after success."""
        self._failed_holding.discard(address)  # type: ignore[attr-defined]
        for (start, end), code in list(self._unsupported_holding_ranges.items()):  # type: ignore[attr-defined]
            if start <= address <= end:
                del self._unsupported_holding_ranges[(start, end)]  # type: ignore[attr-defined]
                if start <= address - 1:
                    self._unsupported_holding_ranges[(start, address - 1)] = code  # type: ignore[attr-defined]
                if address + 1 <= end:
                    self._unsupported_holding_ranges[(address + 1, end)] = code  # type: ignore[attr-defined]

    def _mark_holding_unsupported(self, start: int, end: int, code: int) -> None:
        """Track unsupported holding register range without overlaps."""
        for (exist_start, exist_end), exist_code in list(self._unsupported_holding_ranges.items()):  # type: ignore[attr-defined]
            if exist_end < start or exist_start > end:
                continue
            del self._unsupported_holding_ranges[(exist_start, exist_end)]  # type: ignore[attr-defined]
            if exist_start < start:
                self._unsupported_holding_ranges[(exist_start, start - 1)] = exist_code  # type: ignore[attr-defined]
            if end < exist_end:
                self._unsupported_holding_ranges[(end + 1, exist_end)] = exist_code  # type: ignore[attr-defined]
        self._unsupported_holding_ranges[(start, end)] = code  # type: ignore[attr-defined]

    def _mark_input_unsupported(self, start: int, end: int, code: int | None) -> None:
        """Cache unsupported input register range, merging overlaps."""

        for (old_start, old_end), _ in list(self._unsupported_input_ranges.items()):  # type: ignore[attr-defined]
            if end < old_start or start > old_end:
                continue
            del self._unsupported_input_ranges[(old_start, old_end)]  # type: ignore[attr-defined]
            start = min(start, old_start)
            end = max(end, old_end)

        self._unsupported_input_ranges[(start, end)] = code or 0  # type: ignore[attr-defined]

    def _track_input_failure(self, count: int, address: int) -> None:
        """Increment the failure counter for an input register (only for single-reg reads)."""
        if count != 1:
            return
        failures = self._input_failures.get(address, 0) + 1  # type: ignore[attr-defined]
        self._input_failures[address] = failures  # type: ignore[attr-defined]
        if failures >= self.retry and address not in self._failed_input:  # type: ignore[attr-defined]
            self._failed_input.add(address)  # type: ignore[attr-defined]
            self.failed_addresses["modbus_exceptions"]["input_registers"].add(address)  # type: ignore[attr-defined]
            _LOGGER.warning("Device does not expose register %d", address)

    def _track_holding_failure(self, count: int, address: int) -> None:
        """Increment the failure counter for a holding register (only for single-reg reads)."""
        if count != 1:
            return
        failures = self._holding_failures.get(address, 0) + 1  # type: ignore[attr-defined]
        self._holding_failures[address] = failures  # type: ignore[attr-defined]
        if failures >= self.retry and address not in self._failed_holding:  # type: ignore[attr-defined]
            self._failed_holding.add(address)  # type: ignore[attr-defined]
            self.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)  # type: ignore[attr-defined]
            _LOGGER.warning("Device does not expose register %d", address)

    async def _read_input(
        self,
        client_or_address: Any,
        address_or_count: int,
        count: int | None = None,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        """Read input registers with retry and backoff.

        ``skip_cache`` is used when probing individual registers after a block
        read failed. When ``True`` the cached set of failed registers is not
        checked, allowing each register to be queried once before being cached
        as missing.
        """
        from . import scanner_io as _scanner_io
        from .modbus_helpers import _call_modbus

        client, address, count = self._unpack_read_args(client_or_address, address_or_count, count)  # type: ignore[attr-defined]
        start = address
        end = address + count - 1

        if not skip_cache:
            for skip_start, skip_end in self._unsupported_input_ranges:  # type: ignore[attr-defined]
                if skip_start <= start and end <= skip_end:
                    self.failed_addresses["modbus_exceptions"]["input_registers"].update(  # type: ignore[attr-defined]
                        range(start, end + 1)
                    )
                    return None
        if not skip_cache and any(reg in self._failed_input for reg in range(start, end + 1)):  # type: ignore[attr-defined]
            first = next(reg for reg in range(start, end + 1) if reg in self._failed_input)  # type: ignore[attr-defined]
            skip_start = skip_end = first
            while skip_start - 1 in self._failed_input:  # type: ignore[attr-defined]
                skip_start -= 1
            while skip_end + 1 in self._failed_input:  # type: ignore[attr-defined]
                skip_end += 1
            if (skip_start, skip_end) not in self._input_skip_log_ranges:  # type: ignore[attr-defined]
                _LOGGER.debug(
                    "Skipping cached failed input registers %d-%d",
                    skip_start,
                    skip_end,
                )
                self._input_skip_log_ranges.add((skip_start, skip_end))  # type: ignore[attr-defined]
            self.failed_addresses["modbus_exceptions"]["input_registers"].update(  # type: ignore[attr-defined]
                range(skip_start, skip_end + 1)
            )
            return None

        transport, client = self._resolve_transport_and_client(client)  # type: ignore[attr-defined]

        attempted_reads = 0
        aborted_transiently = False
        for attempt in range(1, self.retry + 1):  # type: ignore[attr-defined]
            attempted_reads = attempt
            try:
                if transport is not None:
                    response = await transport.read_input_registers(
                        self.slave_id,  # type: ignore[attr-defined]
                        address,
                        count=count,
                    )
                else:
                    response = await _scanner_io.call_modbus_compat(
                        _call_modbus,
                        client.read_input_registers,
                        self.slave_id,  # type: ignore[attr-defined]
                        address,
                        count=count,
                        attempt=attempt,
                        retry=self.retry,  # type: ignore[attr-defined]
                        timeout=self.timeout,  # type: ignore[attr-defined]
                        backoff=self.backoff,  # type: ignore[attr-defined]
                        backoff_jitter=self.backoff_jitter,  # type: ignore[attr-defined]
                    )
                if response is not None:
                    if response.isError():
                        code = getattr(response, "exception_code", None)
                        _LOGGER.warning(
                            "Exception code %s while reading holding registers %d-%d",
                            code,
                            start,
                            end,
                        )
                        self._failed_input.update(range(start, end + 1))  # type: ignore[attr-defined]
                        self._mark_input_unsupported(start, end, code)
                        self.failed_addresses["modbus_exceptions"]["input_registers"].update(  # type: ignore[attr-defined]
                            range(start, end + 1)
                        )
                        return None
                    if skip_cache and count == 1:
                        self._mark_input_supported(address)
                    registers = cast(list[int], response.registers)
                    _LOGGER.debug(
                        "Read input registers %d-%d: %s",
                        start,
                        end,
                        registers,
                    )
                    return registers
                _LOGGER.debug(
                    "Attempt %d failed to read input %d: %s",
                    attempt,
                    address,
                    response,
                )
            except ModbusIOException as exc:
                _LOGGER.debug(
                    "Modbus IO error reading input registers %d-%d on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
                if _scanner_io.is_request_cancelled_error(exc):
                    aborted_transiently = True
                    break  # Treat cancellation like a timeout — stop retrying
                self._track_input_failure(count, address)
            except TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading input registers %d-%d on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
                aborted_transiently = True
                break
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading input %d on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Failed to read input registers %d-%d on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
                self._track_input_failure(count, address)

            await _scanner_io.sleep_retry_backoff(
                calculate_backoff_delay=lambda base, at, jitter: __import__(
                    "custom_components.thessla_green_modbus.modbus_helpers",
                    fromlist=["_calculate_backoff_delay"],
                )._calculate_backoff_delay(base=base, attempt=at, jitter=jitter),
                backoff=self.backoff,  # type: ignore[attr-defined]
                backoff_jitter=self.backoff_jitter,  # type: ignore[attr-defined]
                attempt=attempt,
                retry=self.retry,  # type: ignore[attr-defined]
            )

        if aborted_transiently:
            _LOGGER.warning(
                (
                    "Aborted reading input registers %d-%d after %d/%d attempts "
                    "due to timeout/cancellation"
                ),
                start,
                end,
                attempted_reads,
                self.retry,  # type: ignore[attr-defined]
            )
            return None

        self.failed_addresses["modbus_exceptions"]["input_registers"].update(range(start, end + 1))  # type: ignore[attr-defined]
        _LOGGER.error(
            "Failed to read input registers %d-%d after %d retries",
            start,
            end,
            self.retry,  # type: ignore[attr-defined]
        )
        return None

    async def _read_register_block(
        self,
        read_fn: Any,
        client_or_start: Any,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        """Read a contiguous register block in MAX-sized chunks using read_fn."""
        if count is None:
            start = int(client_or_start)
            count = start_or_count
            client: Any = None
        elif isinstance(client_or_start, int):
            start = client_or_start
            count = start_or_count
            client = None
        else:
            client = client_or_start
            start = start_or_count

        results: list[int] = []
        active_client = client or self._client
        for chunk_start, chunk_count in chunk_register_range(start, count, self.effective_batch):  # type: ignore[attr-defined]
            block = await (
                read_fn(chunk_start, chunk_count)
                if active_client is None
                else read_fn(active_client, chunk_start, chunk_count)
            )
            if block is None:
                return None
            results.extend(block)
        return results

    async def _read_input_block(
        self,
        client_or_start: Any,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        """Read a contiguous input register block in MAX-sized chunks."""
        return await self._read_register_block(
            self._read_input, client_or_start, start_or_count, count
        )

    async def _read_holding_block(
        self,
        client_or_start: Any,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        """Read a contiguous holding register block in MAX-sized chunks."""
        return await self._read_register_block(
            self._read_holding, client_or_start, start_or_count, count
        )

    async def _read_holding(
        self,
        client_or_address: Any,
        address_or_count: int,
        count: int | None = None,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        """Read holding registers with retry, backoff and failure tracking.

        ``skip_cache`` is used when probing individual registers after a block
        read failed. When ``True`` the cached sets of unsupported ranges and
        failed registers are ignored, allowing each register to be queried
        once before being cached again.
        """
        from . import scanner_io as _scanner_io
        from .modbus_helpers import _call_modbus

        client, address, count = self._unpack_read_args(client_or_address, address_or_count, count)  # type: ignore[attr-defined]
        start = address
        end = address + count - 1

        if not skip_cache:
            for skip_start, skip_end in self._unsupported_holding_ranges:  # type: ignore[attr-defined]
                if skip_start <= start and end <= skip_end:
                    self.failed_addresses["modbus_exceptions"]["holding_registers"].update(  # type: ignore[attr-defined]
                        range(start, end + 1)
                    )
                    return None

            if address in self._failed_holding:  # type: ignore[attr-defined]
                _LOGGER.debug("Skipping cached failed holding register %d", address)
                self.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)  # type: ignore[attr-defined]
                return None

        failures = self._holding_failures.get(address, 0)  # type: ignore[attr-defined]
        if failures >= self.retry:  # type: ignore[attr-defined]
            _LOGGER.warning("Skipping unsupported holding register %d", address)
            self.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)  # type: ignore[attr-defined]
            return None

        transport, client = self._resolve_transport_and_client(client)  # type: ignore[attr-defined]

        attempted_reads = 0
        aborted_transiently = False
        for attempt in range(1, self.retry + 1):  # type: ignore[attr-defined]
            attempted_reads = attempt
            try:
                if transport is not None:
                    response = await transport.read_holding_registers(
                        self.slave_id,  # type: ignore[attr-defined]
                        address,
                        count=count,
                    )
                else:
                    response = await _scanner_io.call_modbus_compat(
                        _call_modbus,
                        client.read_holding_registers,
                        self.slave_id,  # type: ignore[attr-defined]
                        address,
                        count=count,
                        attempt=attempt,
                        retry=self.retry,  # type: ignore[attr-defined]
                        timeout=self.timeout,  # type: ignore[attr-defined]
                        backoff=self.backoff,  # type: ignore[attr-defined]
                        backoff_jitter=self.backoff_jitter,  # type: ignore[attr-defined]
                    )
                if response is not None:
                    if response.isError():
                        code = getattr(response, "exception_code", None)
                        _LOGGER.warning(
                            "Exception code %s while reading holding registers %d-%d",
                            code,
                            start,
                            end,
                        )
                        if code == 2:
                            self._failed_holding.update(range(start, end + 1))  # type: ignore[attr-defined]
                            self._mark_holding_unsupported(start, end, code)
                            self.failed_addresses["modbus_exceptions"]["holding_registers"].update(  # type: ignore[attr-defined]
                                range(start, end + 1)
                            )
                            return None
                        if count == 1:
                            failures = self._holding_failures.get(address, 0) + 1  # type: ignore[attr-defined]
                            self._holding_failures[address] = failures  # type: ignore[attr-defined]
                            if failures >= self.retry:  # type: ignore[attr-defined]
                                self._failed_holding.update(range(start, end + 1))  # type: ignore[attr-defined]
                                self._mark_holding_unsupported(start, end, code or 0)
                                self.failed_addresses["modbus_exceptions"][  # type: ignore[attr-defined]
                                    "holding_registers"
                                ].update(range(start, end + 1))
                                return None
                        continue
                    if skip_cache and count == 1:
                        self._mark_holding_supported(address)
                    if address in self._holding_failures:  # type: ignore[attr-defined]
                        del self._holding_failures[address]  # type: ignore[attr-defined]
                    registers = cast(list[int], response.registers)
                    _LOGGER.debug(
                        "Read holding registers %d-%d: %s",
                        start,
                        end,
                        registers,
                    )
                    return registers
            except TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading holding %d (attempt %d/%d): %s",
                    address,
                    attempt,
                    self.retry,  # type: ignore[attr-defined]
                    exc,
                    exc_info=True,
                )
                self._track_holding_failure(count, address)
                aborted_transiently = True
            except ModbusIOException as exc:
                if _scanner_io.is_request_cancelled_error(exc):
                    _LOGGER.debug(
                        "Cancelled reading holding registers %d-%d on attempt %d/%d: %s",
                        start,
                        end,
                        attempt,
                        self.retry,  # type: ignore[attr-defined]
                        exc,
                    )
                    aborted_transiently = True
                    break
                _LOGGER.debug(
                    "Failed to read holding %d (attempt %d/%d): %s",
                    address,
                    attempt,
                    self.retry,  # type: ignore[attr-defined]
                    exc,
                    exc_info=True,
                )
                self._track_holding_failure(count, address)
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Failed to read holding %d (attempt %d/%d): %s",
                    address,
                    attempt,
                    self.retry,  # type: ignore[attr-defined]
                    exc,
                    exc_info=True,
                )
                self._track_holding_failure(count, address)
            except asyncio.CancelledError:
                _LOGGER.debug(
                    "Cancelled reading holding %d on attempt %d/%d",
                    address,
                    attempt,
                    self.retry,  # type: ignore[attr-defined]
                )
                raise
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading holding %d on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            await _scanner_io.sleep_retry_backoff(
                calculate_backoff_delay=lambda base, at, jitter: __import__(
                    "custom_components.thessla_green_modbus.modbus_helpers",
                    fromlist=["_calculate_backoff_delay"],
                )._calculate_backoff_delay(base=base, attempt=at, jitter=jitter),
                backoff=self.backoff,  # type: ignore[attr-defined]
                backoff_jitter=self.backoff_jitter,  # type: ignore[attr-defined]
                attempt=attempt,
                retry=self.retry,  # type: ignore[attr-defined]
            )

        if aborted_transiently:
            _LOGGER.warning(
                (
                    "Aborted reading holding registers %d-%d after %d/%d attempts "
                    "due to timeout/cancellation"
                ),
                start,
                end,
                attempted_reads,
                self.retry,  # type: ignore[attr-defined]
            )
            _LOGGER.error(
                "Failed to read holding registers %d-%d after %d retries",
                start,
                end,
                self.retry,  # type: ignore[attr-defined]
            )
            return None

        _LOGGER.error(
            "Failed to read holding registers %d-%d after %d retries",
            start,
            end,
            self.retry,  # type: ignore[attr-defined]
        )
        self.failed_addresses["modbus_exceptions"]["holding_registers"].update(  # type: ignore[attr-defined]
            range(start, end + 1)
        )
        return None

    async def _read_bit_registers(
        self,
        method_name: str,
        failed_key: str,
        type_name: str,
        client_or_address: Any,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        """Shared implementation for coil and discrete input reads with retry and backoff."""
        from . import scanner_io as _scanner_io
        from .modbus_helpers import _call_modbus

        if count is None:
            address = int(client_or_address)
            count = address_or_count
            client = self._client
        elif isinstance(client_or_address, int):
            address = client_or_address
            count = address_or_count
            client = self._client
        else:
            client = client_or_address
            address = address_or_count

        if client is None:
            raise ConnectionException("Modbus client is not connected")
        # Refresh client from transport in case transport reconnected since scan start
        if client is self._client and self._transport is not None:  # type: ignore[attr-defined]
            fresh = getattr(self._transport, "client", None)  # type: ignore[attr-defined]
            if fresh is not None:
                client = fresh
        for attempt in range(1, self.retry + 1):  # type: ignore[attr-defined]
            try:
                response: Any = await _scanner_io.call_modbus_compat(
                    _call_modbus,
                    getattr(client, method_name),
                    self.slave_id,  # type: ignore[attr-defined]
                    address,
                    count=count,
                    attempt=attempt,
                    retry=self.retry,  # type: ignore[attr-defined]
                    timeout=self.timeout,  # type: ignore[attr-defined]
                    backoff=self.backoff,  # type: ignore[attr-defined]
                    backoff_jitter=self.backoff_jitter,  # type: ignore[attr-defined]
                )
                if response is not None and not response.isError():
                    bits = cast(list[bool], response.bits[:count])
                    _LOGGER.debug(
                        "Read %s registers %d-%d: %s",
                        type_name,
                        address,
                        address + count - 1,
                        bits,
                    )
                    return bits
            except TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading %s %d on attempt %d: %s",
                    type_name,
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Failed to read %s %d on attempt %d: %s",
                    type_name,
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                if self._transport is not None:  # type: ignore[attr-defined]
                    try:
                        await self._transport.ensure_connected()  # type: ignore[attr-defined]
                        transport_client = getattr(self._transport, "client", None)  # type: ignore[attr-defined]
                        if transport_client is not None:
                            client = transport_client
                            self._client = transport_client
                    except (
                        ModbusException,
                        ConnectionException,
                        ModbusIOException,
                        TimeoutError,
                        OSError,
                        AttributeError,
                    ) as exc:
                        _LOGGER.debug(
                            "Transport client refresh failed during %s read: %s", type_name, exc
                        )
            except asyncio.CancelledError:
                _LOGGER.debug(
                    "Cancelled reading %s %d on attempt %d",
                    type_name,
                    address,
                    attempt,
                )
                raise
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading %s %d on attempt %d: %s",
                    type_name,
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            await _scanner_io.sleep_retry_backoff(
                calculate_backoff_delay=lambda base, at, jitter: __import__(
                    "custom_components.thessla_green_modbus.modbus_helpers",
                    fromlist=["_calculate_backoff_delay"],
                )._calculate_backoff_delay(base=base, attempt=at, jitter=jitter),
                backoff=self.backoff,  # type: ignore[attr-defined]
                backoff_jitter=self.backoff_jitter,  # type: ignore[attr-defined]
                attempt=attempt,
                retry=self.retry,  # type: ignore[attr-defined]
            )

        self.failed_addresses["modbus_exceptions"][failed_key].update(  # type: ignore[attr-defined]
            range(address, address + count)
        )
        _LOGGER.error(
            "Failed to read %s registers %d-%d after %d retries",
            type_name,
            address,
            address + count - 1,
            self.retry,  # type: ignore[attr-defined]
        )
        return None

    async def _read_coil(
        self,
        client_or_address: Any,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        """Read coil registers with retry and backoff."""
        return await self._read_bit_registers(
            "read_coils",
            "coil_registers",
            "coil",
            client_or_address,
            address_or_count,
            count,
        )

    async def _read_discrete(
        self,
        client_or_address: Any,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        """Read discrete input registers with retry and backoff."""
        return await self._read_bit_registers(
            "read_discrete_inputs",
            "discrete_inputs",
            "discrete",
            client_or_address,
            address_or_count,
            count,
        )
