"""Write/control helpers mixin for coordinator."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ..const import MAX_REGS_PER_REQUEST
from ..modbus_exceptions import ConnectionException, ModbusException
from ..modbus_helpers import chunk_register_values
from ..registers import REG_TEMPORARY_FLOW_START, REG_TEMPORARY_TEMP_START
from .write_path import (
    SingleWritePlan,
    encode_write_value,
    finalize_write_result,
    run_multi_register_write_attempts,
    run_single_write_attempts,
)

if TYPE_CHECKING:
    from ..modbus_transport import BaseModbusTransport

_LOGGER = logging.getLogger(__name__)


def _get_register_definition(register_name: str) -> Any:
    """Resolve register definitions via coordinator implementation module."""

    from custom_components.thessla_green_modbus.coordinator import coordinator as coordinator_module

    return coordinator_module.get_register_definition(register_name)


async def _safe_request_refresh(coordinator: Any) -> None:
    """Request refresh and ignore mock-context TypeError in tests."""
    try:
        await coordinator.async_request_refresh()
    except (TypeError, AttributeError):
        _LOGGER.debug("Skipping refresh for mock Home Assistant context")


class _CoordinatorScheduleMixin:
    """Write-path and schedule helpers for the coordinator."""

    _transport: BaseModbusTransport | None
    client: Any | None
    slave_id: int
    retry: int
    effective_batch: int
    _write_lock: asyncio.Lock

    async def _call_modbus(self, func: Any, *args: Any, attempt: int = 1, **kwargs: Any) -> Any: ...
    def _get_client_method(self, name: str) -> Any: ...
    async def _ensure_connection(self) -> None: ...
    async def _disconnect(self) -> None: ...
    def _clear_register_failure(self, name: str) -> None: ...
    async def _safe_request_refresh(self) -> None:
        """Request refresh and ignore mock-context TypeError in tests."""
        await _safe_request_refresh(self)

    def _assert_write_connection_ready(self) -> None:
        """Ensure transport/client is present and connected for writes."""
        transport = self._transport
        if transport is not None and not transport.is_connected():
            raise ConnectionException("Modbus transport is not connected")
        if transport is None and self.client is None:
            raise ConnectionException("Modbus client is not connected")

    async def _write_registers_payload(self, address: int, values: list[int], attempt: int) -> Any:
        """Write a holding-register payload via client, transport, or fallback call."""
        payload = [int(v) for v in values]
        if self._transport is None and self.client is not None:
            return await self.client.write_registers(address=address, values=payload)
        if self._transport is not None:
            return await self._transport.write_registers(
                self.slave_id,
                address,
                values=payload,
                attempt=attempt,
            )
        return await self._call_modbus(
            self._get_client_method("write_registers"),
            address,
            values=payload,
            attempt=attempt,
        )

    async def _execute_multi_register_chunks(
        self, chunks: list[tuple[int, list[int]]], attempt: int
    ) -> tuple[Any, bool]:
        """Execute a prepared list of multi-register write chunks."""
        response = None
        for chunk_start, chunk in chunks:
            response = await self._write_registers_payload(chunk_start, chunk, attempt)
            if not self._write_response_ok(response):
                return response, False
        return response, True

    async def _write_holding_multi(
        self,
        address: int,
        encoded_values: list[int],
        attempt: int,
    ) -> tuple[Any, bool]:
        """Write multiple holding registers in chunks. Returns (last_response, success)."""
        response = None
        for chunk_start, chunk in chunk_register_values(
            address, encoded_values, self.effective_batch
        ):
            response = await self._write_registers_payload(chunk_start, chunk, attempt)
            if response is None or response.isError():
                return response, False
        return response, True

    async def _write_holding_single(self, address: int, value: Any, attempt: int) -> Any:
        """Write a single holding register."""
        if self._transport is None and self.client is not None:
            return await self.client.write_register(address=address, value=int(value))
        if self._transport is not None:
            return await self._transport.write_register(self.slave_id, address, value=int(value))
        return await self._call_modbus(
            self._get_client_method("write_register"),
            address,
            value=int(value),
            attempt=attempt,
        )

    def _resolve_write_definition(self, register_name: str) -> Any | None:
        """Resolve writable register definition or log an error."""
        try:
            return _get_register_definition(register_name)
        except KeyError:
            _LOGGER.error("Unknown register name: %s", register_name)
            return None

    def _validate_multi_register_write_request(
        self, start_address: int, values: list[int], require_single_request: bool
    ) -> bool:
        """Validate a multi-register write request before connection work."""
        if not values:
            _LOGGER.error("No values provided for multi-register write at %s", start_address)
            return False
        if require_single_request and len(values) > MAX_REGS_PER_REQUEST:
            _LOGGER.error(
                "Requested %s registers at %s exceeds maximum %s per request",
                len(values),
                start_address,
                MAX_REGS_PER_REQUEST,
            )
            return False
        return True

    def _plan_multi_register_chunks(
        self, start_address: int, values: list[int], require_single_request: bool
    ) -> list[tuple[int, list[int]]]:
        """Build chunk plan for multi-register writes."""
        if require_single_request:
            return [(start_address, values)]
        return list(chunk_register_values(start_address, values, self.effective_batch))

    def _handle_write_response_failure(
        self,
        *,
        is_final_attempt: bool,
        final_error_message: str,
        retry_message: str,
        error_args: tuple[Any, ...],
    ) -> bool:
        """Handle write-response failure logging.

        Returns True when caller should retry, False when operation must stop.
        """
        if is_final_attempt:
            _LOGGER.error(final_error_message, *error_args)
            return False
        _LOGGER.info(retry_message)
        return True

    async def _handle_write_attempt_exception(
        self,
        *,
        register_name: str,
        attempt: int,
        exc: Exception,
        timed_out_message: str,
        persistent_timeout_message: str,
        failed_message: str,
        retry_message: str,
        unexpected_message: str,
    ) -> bool:
        """Handle write attempt exception paths.

        Returns True when caller should retry, False when operation must stop.
        """
        if isinstance(exc, (ModbusException, ConnectionException)):
            await self._disconnect()
            if attempt == self.retry:
                _LOGGER.error(failed_message, register_name, exc_info=True)
                return False
            _LOGGER.info(retry_message, register_name, exc)
            return True

        if isinstance(exc, TimeoutError):
            if self._transport is not None:
                await self._disconnect()
            _LOGGER.warning(
                timed_out_message,
                register_name,
                attempt,
                self.retry,
                exc_info=True,
            )
            if attempt == self.retry:
                _LOGGER.error(persistent_timeout_message, register_name)
                return False
            return True

        if isinstance(exc, OSError):
            await self._disconnect()
            _LOGGER.exception(unexpected_message, register_name)
            return False

        raise exc

    def _handle_successful_single_register_write(
        self,
        *,
        register_name: str,
        original_value: float | str | list[int] | tuple[int, ...],
        refresh: bool,
    ) -> bool:
        """Apply common success side effects for single-register write path."""
        # Successful write: remove from failed set so the next
        # poll doesn't skip this register's chunk entirely.
        self._clear_register_failure(register_name)
        _LOGGER.info(
            "Successfully wrote %s to register %s",
            original_value,
            register_name,
        )
        return refresh

    def _write_response_ok(self, response: Any) -> bool:
        """Return True when a Modbus write response indicates success."""
        return response is not None and not response.isError()

    async def _execute_single_register_write_attempt(
        self,
        *,
        definition: Any,
        register_name: str,
        address: int,
        encoded_values: list[int] | None,
        scalar_value: Any,
        attempt: int,
    ) -> tuple[Any, bool]:
        """Execute one write attempt and return (response, success)."""
        if definition.function == 3:
            response = await self._write_holding_attempt(
                address=address,
                encoded_values=encoded_values,
                scalar_value=scalar_value,
                attempt=attempt,
            )
        elif definition.function == 1:
            response = await self._call_modbus(
                self._get_client_method("write_coil"),
                address=address,
                value=bool(scalar_value),
                attempt=attempt,
            )
        else:
            _LOGGER.error("Register %s is not writable", register_name)
            return None, False
        return response, self._write_response_ok(response)

    async def _write_holding_attempt(
        self,
        *,
        address: int,
        encoded_values: list[int] | None,
        scalar_value: Any,
        attempt: int,
    ) -> Any:
        """Write holding register(s) for one attempt and return response."""
        if encoded_values is not None:
            response, _success = await self._write_holding_multi(address, encoded_values, attempt)
            return response
        return await self._write_holding_single(address, scalar_value, attempt)

    async def _locked_single_register_write(
        self,
        *,
        register_name: str,
        value: float | str | list[int] | tuple[int, ...],
        offset: int,
        refresh: bool,
    ) -> tuple[bool, bool]:
        """Execute single-register write within an already-acquired lock.

        Returns (success, refresh_after_write).
        """
        definition = self._resolve_write_definition(register_name)
        if definition is None:
            return False, False

        await self._ensure_connection()
        self._assert_write_connection_ready()

        encoded_values, scalar_value = encode_write_value(register_name, definition, value, offset)
        if encoded_values is None and scalar_value is None:
            return False, False

        plan = SingleWritePlan(
            register_name=register_name,
            address=definition.address + offset,
            encoded_values=encoded_values,
            scalar_value=scalar_value,
            original_value=value,
        )
        return await run_single_write_attempts(self, definition, plan, refresh)

    async def async_write_register(
        self,
        register_name: str,
        value: float | str | list[int] | tuple[int, ...],
        refresh: bool = True,
        *,
        offset: int = 0,
    ) -> bool:
        """Write to a holding or coil register.

        ``value`` should be supplied in user-friendly units. The register
        definition's :meth:`encode` method is used to convert it to the raw
        Modbus representation before sending to the device.
        """
        refresh_after_write = False
        async with self._write_lock:
            try:
                success, refresh_after_write = await self._locked_single_register_write(
                    register_name=register_name,
                    value=value,
                    offset=offset,
                    refresh=refresh,
                )
                if not success:
                    return False
            except (ModbusException, ConnectionException):  # pragma: no cover - safety
                _LOGGER.exception("Failed to write register %s", register_name)
                return False

        return await finalize_write_result(self, refresh_after_write)

    async def async_write_registers(
        self,
        start_address: int,
        values: list[int],
        refresh: bool = True,
        *,
        require_single_request: bool = False,
    ) -> bool:
        """Write multiple holding registers in one Modbus request."""

        if not self._validate_multi_register_write_request(
            start_address, values, require_single_request
        ):
            return False
        refresh_after_write = False
        async with self._write_lock:
            try:
                await self._ensure_connection()
                self._assert_write_connection_ready()

                success, refresh_after_write = await run_multi_register_write_attempts(
                    self, start_address, values, require_single_request, refresh
                )
                if not success:
                    return False

            except (ModbusException, ConnectionException):  # pragma: no cover - safety
                _LOGGER.exception("Failed to write registers at %s", start_address)
                return False

        return await finalize_write_result(self, refresh_after_write)

    async def async_write_temporary_airflow(self, airflow: float, refresh: bool = True) -> bool:
        """Write temporary airflow settings using the 3-register block."""

        try:
            mode_def = _get_register_definition("cfg_mode_1")
            value_def = _get_register_definition("air_flow_rate_temporary_4401")
            flag_def = _get_register_definition("airflow_rate_change_flag")
        except KeyError as exc:
            _LOGGER.error("Temporary airflow registers unavailable: %s", exc)
            return False

        values = [
            int(mode_def.encode(2)),
            int(value_def.encode(airflow)),
            int(flag_def.encode(1)),
        ]
        return await self.async_write_registers(
            REG_TEMPORARY_FLOW_START,
            values,
            refresh=refresh,
            require_single_request=True,
        )

    async def async_write_temporary_temperature(
        self, temperature: float, refresh: bool = True
    ) -> bool:
        """Write temporary temperature settings using the 3-register block."""

        try:
            mode_def = _get_register_definition("cfg_mode_2")
            value_def = _get_register_definition("supply_air_temperature_temporary_4404")
            flag_def = _get_register_definition("temperature_change_flag")
        except KeyError as exc:
            _LOGGER.error("Temporary temperature registers unavailable: %s", exc)
            return False

        values = [
            int(mode_def.encode(2)),
            value_def.encode(temperature),
            int(flag_def.encode(1)),
        ]
        return await self.async_write_registers(
            REG_TEMPORARY_TEMP_START,
            values,
            refresh=refresh,
            require_single_request=True,
        )
