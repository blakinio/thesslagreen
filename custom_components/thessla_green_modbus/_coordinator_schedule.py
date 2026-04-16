"""Write/control helpers mixin for coordinator."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from .const import MAX_REGS_PER_REQUEST
from .modbus_exceptions import ConnectionException, ModbusException
from .modbus_helpers import chunk_register_values
from .register_addresses import REG_TEMPORARY_FLOW_START, REG_TEMPORARY_TEMP_START

if TYPE_CHECKING:
    from .modbus_transport import BaseModbusTransport

_LOGGER = logging.getLogger(__name__)


def _get_register_definition(register_name: str) -> Any:
    """Resolve register definitions via coordinator module for test compatibility."""

    from . import coordinator as coordinator_module

    return coordinator_module.get_register_definition(register_name)


class _CoordinatorScheduleMixin:
    """Write-path and schedule helpers for the coordinator."""

    _transport: BaseModbusTransport | None
    client: Any | None
    slave_id: int
    retry: int
    effective_batch: int
    _write_lock: asyncio.Lock

    async def _call_modbus(
        self, func: Any, *args: Any, attempt: int = 1, **kwargs: Any
    ) -> Any: ...
    def _get_client_method(self, name: str) -> Any: ...
    async def _ensure_connection(self) -> None: ...
    async def _disconnect(self) -> None: ...
    def _clear_register_failure(self, name: str) -> None: ...

    def _encode_write_value(
        self,
        register_name: str,
        definition: Any,
        value: float | str | list[int] | tuple[int, ...],
        offset: int,
    ) -> tuple[list[int] | None, Any]:
        """Encode *value* for writing. Returns (encoded_values, scalar_value).

        For multi-register definitions, returns (list[int], original_value).
        For single-register definitions, returns (None, int_value).
        Logs an error and returns (None, None) on validation failure.
        """
        if definition.length > 1:
            if isinstance(value, list | tuple) and not isinstance(value, bytes | bytearray | str):
                if len(value) + offset > definition.length:
                    _LOGGER.error(
                        "Register %s expects at most %d values starting at offset %d",
                        register_name,
                        definition.length - offset,
                        offset,
                    )
                    return None, None
                if offset == 0 and len(value) != definition.length:
                    _LOGGER.error(
                        "Register %s requires exactly %d values",
                        register_name,
                        definition.length,
                    )
                    return None, None
                try:
                    return [int(v) for v in value], value
                except (TypeError, ValueError):
                    _LOGGER.error("Register %s expects integer values", register_name)
                    return None, None
            else:
                encoded = definition.encode(value)
                if isinstance(encoded, list):
                    encoded_values: list[int] = [int(v) for v in encoded]
                else:
                    encoded_values = [int(encoded)]
                if offset >= definition.length:
                    _LOGGER.error(
                        "Register %s expects at most %d values starting at offset %d",
                        register_name,
                        definition.length - offset,
                        offset,
                    )
                    return None, None
                return encoded_values[offset:], value
        else:
            if isinstance(value, list | tuple) and not isinstance(value, bytes | bytearray | str):
                _LOGGER.error("Register %s expects a single value", register_name)
                return None, None
            return None, int(definition.encode(value))

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
            if self._transport is None and self.client is not None:
                response = await self.client.write_registers(
                    address=chunk_start,
                    values=[int(v) for v in chunk],
                )
            elif self._transport is not None:
                response = await self._transport.write_registers(
                    self.slave_id,
                    chunk_start,
                    values=[int(v) for v in chunk],
                    attempt=attempt,
                )
            else:
                response = await self._call_modbus(
                    self._get_client_method("write_registers"),
                    chunk_start,
                    values=[int(v) for v in chunk],
                    attempt=attempt,
                )
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
                await self._ensure_connection()
                transport = self._transport
                if transport is not None and not transport.is_connected():
                    raise ConnectionException("Modbus transport is not connected")
                if transport is None and self.client is None:
                    raise ConnectionException("Modbus client is not connected")

                original_value = value
                try:
                    definition = _get_register_definition(register_name)
                except KeyError:
                    _LOGGER.error("Unknown register name: %s", register_name)
                    return False

                encoded_values, scalar_value = self._encode_write_value(
                    register_name, definition, value, offset
                )
                if encoded_values is None and scalar_value is None:
                    return False

                address = definition.address + offset

                for attempt in range(1, self.retry + 1):
                    try:
                        if definition.function == 3:
                            if encoded_values is not None:
                                response, success = await self._write_holding_multi(
                                    address, encoded_values, attempt
                                )
                                if not success:
                                    if attempt == self.retry:
                                        _LOGGER.error(
                                            "Error writing to register %s: %s",
                                            register_name,
                                            response,
                                        )
                                        return False
                                    _LOGGER.info("Retrying write to register %s", register_name)
                                    continue
                            else:
                                response = await self._write_holding_single(
                                    address, scalar_value, attempt
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
                            return False

                        if response is None or response.isError():
                            if attempt == self.retry:
                                _LOGGER.error(
                                    "Error writing to register %s: %s",
                                    register_name,
                                    response,
                                )
                                return False
                            _LOGGER.info("Retrying write to register %s", register_name)
                            continue

                        refresh_after_write = refresh
                        # Successful write: remove from failed set so the next
                        # poll doesn't skip this register's chunk entirely.
                        self._clear_register_failure(register_name)
                        _LOGGER.info(
                            "Successfully wrote %s to register %s",
                            original_value,
                            register_name,
                        )
                        break
                    except (ModbusException, ConnectionException) as exc:
                        await self._disconnect()
                        if attempt == self.retry:
                            _LOGGER.error(
                                "Failed to write register %s",
                                register_name,
                                exc_info=True,
                            )
                            return False
                        _LOGGER.info(
                            "Retrying write to register %s after error: %s",
                            register_name,
                            exc,
                        )
                        continue
                    except TimeoutError:
                        if self._transport is not None:
                            await self._disconnect()
                        _LOGGER.warning(
                            "Writing register %s timed out (attempt %d/%d)",
                            register_name,
                            attempt,
                            self.retry,
                            exc_info=True,
                        )
                        if attempt == self.retry:
                            _LOGGER.error(
                                "Persistent timeout writing register %s",
                                register_name,
                            )
                            return False
                        continue
                    except OSError:
                        await self._disconnect()
                        _LOGGER.exception("Unexpected error writing register %s", register_name)
                        return False

            except (ModbusException, ConnectionException):  # pragma: no cover - safety
                _LOGGER.exception("Failed to write register %s", register_name)
                return False

        if refresh_after_write:
            refresh_cb = getattr(self, "async_request_refresh", None)
            if callable(refresh_cb):
                try:
                    await refresh_cb()
                except TypeError:
                    _LOGGER.debug("Skipping refresh for mock Home Assistant context")
        return True

    async def async_write_registers(
        self,
        start_address: int,
        values: list[int],
        refresh: bool = True,
        *,
        require_single_request: bool = False,
    ) -> bool:
        """Write multiple holding registers in one Modbus request."""

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
        refresh_after_write = False
        async with self._write_lock:
            try:
                await self._ensure_connection()
                transport = self._transport
                if transport is not None and not transport.is_connected():
                    raise ConnectionException("Modbus transport is not connected")
                if transport is None and self.client is None:
                    raise ConnectionException("Modbus client is not connected")

                for attempt in range(1, self.retry + 1):
                    try:
                        success = True
                        if require_single_request:
                            if self._transport is None and self.client is not None:
                                response = await self.client.write_registers(
                                    address=start_address,
                                    values=[int(v) for v in values],
                                )
                            elif self._transport is not None:
                                response = await self._transport.write_registers(
                                    self.slave_id,
                                    start_address,
                                    values=[int(v) for v in values],
                                    attempt=attempt,
                                )
                            else:
                                response = await self._call_modbus(
                                    self._get_client_method("write_registers"),
                                    start_address,
                                    values=[int(v) for v in values],
                                    attempt=attempt,
                                )
                            if response is None or response.isError():
                                success = False
                        else:
                            for _index, (chunk_start, chunk) in enumerate(
                                chunk_register_values(start_address, values, self.effective_batch)
                            ):
                                if self._transport is None and self.client is not None:
                                    response = await self.client.write_registers(
                                        address=chunk_start,
                                        values=[int(v) for v in chunk],
                                    )
                                elif self._transport is not None:
                                    response = await self._transport.write_registers(
                                        self.slave_id,
                                        chunk_start,
                                        values=[int(v) for v in chunk],
                                        attempt=attempt,
                                    )
                                else:
                                    response = await self._call_modbus(
                                        self._get_client_method("write_registers"),
                                        chunk_start,
                                        values=[int(v) for v in chunk],
                                        attempt=attempt,
                                    )
                                if response is None or response.isError():
                                    success = False
                                    break
                        if not success:
                            if attempt == self.retry:
                                _LOGGER.error(
                                    "Error writing registers at %s: %s",
                                    start_address,
                                    response,
                                )
                                return False
                            _LOGGER.info("Retrying multi-register write at %s", start_address)
                            await self._disconnect()
                            continue

                        refresh_after_write = refresh
                        _LOGGER.info(
                            "Successfully wrote %s to registers starting at %s",
                            values,
                            start_address,
                        )
                        break
                    except (ModbusException, ConnectionException) as exc:
                        await self._disconnect()
                        if attempt == self.retry:
                            _LOGGER.error(
                                "Failed to write registers at %s",
                                start_address,
                                exc_info=True,
                            )
                            return False
                        _LOGGER.info(
                            "Retrying multi-register write at %s after error: %s",
                            start_address,
                            exc,
                        )
                        continue
                    except TimeoutError:
                        if self._transport is not None:
                            await self._disconnect()
                        _LOGGER.warning(
                            "Writing registers at %s timed out (attempt %d/%d)",
                            start_address,
                            attempt,
                            self.retry,
                            exc_info=True,
                        )
                        if attempt == self.retry:
                            _LOGGER.error(
                                "Persistent timeout writing registers at %s",
                                start_address,
                            )
                            return False
                        continue
                    except OSError:
                        await self._disconnect()
                        _LOGGER.exception("Unexpected error writing registers at %s", start_address)
                        return False

            except (ModbusException, ConnectionException):  # pragma: no cover - safety
                _LOGGER.exception("Failed to write registers at %s", start_address)
                return False

        if refresh_after_write:
            refresh_cb = getattr(self, "async_request_refresh", None)
            if callable(refresh_cb):
                try:
                    await refresh_cb()
                except TypeError:
                    _LOGGER.debug("Skipping refresh for mock Home Assistant context")
        return True

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
