"""Write/control helpers mixin for coordinator."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from pymodbus.exceptions import ConnectionException, ModbusException

from ..const import MAX_REGS_PER_REQUEST
from ..core.write_path import SingleWritePlan, encode_write_value
from ..registers import REG_TEMPORARY_FLOW_START, REG_TEMPORARY_TEMP_START
from ..registers.read_planner import chunk_register_values
from .write_path import (
    finalize_write_result,
    run_multi_register_write_attempts,
    run_single_write_attempts,
)

if TYPE_CHECKING:
    from ..transport.base import BaseModbusTransport

_LOGGER = logging.getLogger(__name__)

# Explicit allow-list of registers eligible for targeted read-back after a write.
#
# Targeted read-back is restricted to writable holding registers that are 1:1 with a
# single displayed entity state — setpoints and operational mode controls exposed via
# the number/select/switch platforms — where reading the just-written register straight
# back is both safe and useful.  Everything else defaults to a full refresh, including:
#   * communication config (uart_*),
#   * security (lock_*, access_level),
#   * configuration mode (configuration_mode, cfg_mode_*),
#   * reset/trigger/self-clearing registers (hard_reset_*, filter_change, *_change_flag,
#     pres_check_*_2),
#   * schedule/setting BCD-AATT slots (schedule_*, setting_*),
#   * device identity/clock/calibration (language, rtc_cal, device_name, date_time*),
#   * and any multi-word block.
#
# This replaces the previous permissive deny-list (any single-word holding register was
# eligible unless enumerated), which left dangerous config entities read-back-eligible.
# See docs/architecture/write_path.md and docs/audits/targeted_readback_write_path_audit.md.
_READBACK_ALLOW_LIST: frozenset[str] = frozenset(
    {
        # Airflow / fan-speed setpoints (%)
        "air_flow_rate_manual",
        "air_flow_rate_temporary",
        "air_flow_rate_temporary_4401",
        "fan_speed_1_coef",
        "fan_speed_2_coef",
        "fan_speed_3_coef",
        "max_supply_air_flow_rate",
        "max_exhaust_air_flow_rate",
        "max_supply_air_flow_rate_gwc",
        "max_exhaust_air_flow_rate_gwc",
        "nominal_supply_air_flow",
        "nominal_exhaust_air_flow",
        "nominal_supply_air_flow_gwc",
        "nominal_exhaust_air_flow_gwc",
        # Special-function intensity setpoints (%)
        "airing_bathroom_coef",
        "airing_coef",
        "airing_switch_coef",
        "bypass_coef_1",
        "bypass_coef_2",
        "contamination_coef",
        "empty_house_coef",
        "fireplace_supply_coef",
        "hood_supply_coef",
        "hood_exhaust_coef",
        "open_window_coef",
        # Special-function / GWC timings
        "airing_panel_mode_time",
        "airing_switch_mode_time",
        "airing_switch_mode_on_delay",
        "airing_switch_mode_off_delay",
        "fireplace_mode_time",
        "gwc_regen_period",
        # Temperature setpoints (°C)
        "supply_air_temperature_manual",
        "supply_air_temperature_temporary",
        "supply_air_temperature_temporary_4404",
        "min_bypass_temperature",
        "min_gwc_air_temperature",
        "max_gwc_air_temperature",
        "delta_t_gwc",
        "air_temperature_summer_free_heating",
        "air_temperature_summer_free_cooling",
        # Filter wear thresholds
        "cfgszf_fn_new",
        "cfgszf_fw_new",
        # Operational mode controls (enum select/switch, 1:1 with displayed state)
        "mode",
        "season_mode",
        "special_mode",
        "on_off_panel_mode",
        "comfort_mode_panel",
        "bypass_user_mode",
        "bypass_off",
        "gwc_off",
        "gwc_regen",
        "cfg_post_heater_mode",
        "pres_check_day",
        "pres_check_day_4432",
    }
)


def _targeted_readback_safe(register_name: str, definition: Any) -> bool:
    """Return True only for registers on the explicit safe read-back allow-list.

    A register is eligible for targeted read-back after a write iff it is on
    ``_READBACK_ALLOW_LIST`` (a curated set of 1:1 writable holding registers) and is
    still a function-3 single-word register.  The function/length checks are
    defence-in-depth: only holding single-word registers can ever read back, even if
    the allow-list were to drift from the register definitions.  Everything not on the
    allow-list — comms/security/config-mode registers, reset/trigger/self-clearing
    registers, schedule/setting BCD-AATT slots, device identity/clock, and multi-word
    blocks — falls back to a full refresh.
    """
    return (
        register_name in _READBACK_ALLOW_LIST
        and definition.function == 3
        and definition.length == 1
    )


def _get_register_definition(register_name: str) -> Any:
    """Resolve register definitions via coordinator module (allows test monkeypatching)."""
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

    async def _ensure_connection(self) -> None: ...
    async def _disconnect(self) -> None: ...
    async def _safe_request_refresh(self) -> None:
        """Request refresh and ignore mock-context TypeError in tests."""
        await _safe_request_refresh(self)

    def _assert_write_connection_ready(self) -> None:
        """Ensure transport/client is present and connected for writes."""
        transport = self._device_client._transport
        if transport is not None and not transport.is_connected():
            raise ConnectionException("Modbus transport is not connected")
        if transport is None and self._device_client.client is None:
            raise ConnectionException("Modbus client is not connected")

    async def _write_registers_payload(self, address: int, values: list[int], attempt: int) -> Any:
        """Write a holding-register payload via transport or call_modbus (injects slave_id)."""
        payload = [int(v) for v in values]
        if self._device_client._transport is not None:
            return await self._device_client._transport.write_registers(
                self._device_client.slave_id,
                address,
                values=payload,
                attempt=attempt,
            )
        return await self._device_client._call_modbus(
            self._device_client._get_client_method("write_registers"),
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
            address, encoded_values, self._device_client.effective_batch
        ):
            response = await self._write_registers_payload(chunk_start, chunk, attempt)
            if response is None or response.isError():
                return response, False
        return response, True

    async def _write_holding_single(self, address: int, value: Any, attempt: int) -> Any:
        """Write a single holding register via transport or call_modbus (injects slave_id)."""
        if self._device_client._transport is not None:
            return await self._device_client._transport.write_register(
                self._device_client.slave_id, address, value=int(value)
            )
        return await self._device_client._call_modbus(
            self._device_client._get_client_method("write_register"),
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
        return list(
            chunk_register_values(start_address, values, self._device_client.effective_batch)
        )

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
            if attempt == self._device_client.retry:
                _LOGGER.error(failed_message, register_name, exc_info=True)
                return False
            _LOGGER.info(retry_message, register_name, exc)
            return True

        if isinstance(exc, TimeoutError):
            if self._device_client._transport is not None:
                await self._disconnect()
            _LOGGER.warning(
                timed_out_message,
                register_name,
                attempt,
                self._device_client.retry,
                exc_info=True,
            )
            if attempt == self._device_client.retry:
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
        self._device_client._clear_register_failure(register_name)
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
            response = await self._device_client._call_modbus(
                self._device_client._get_client_method("write_coil"),
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
        targeted_readback: bool = True,
    ) -> bool:
        """Write to a holding or coil register.

        ``value`` should be supplied in user-friendly units. The register
        definition's :meth:`encode` method is used to convert it to the raw
        Modbus representation before sending to the device.

        After a successful write to a safe single holding register a targeted
        read-back is performed under the same lock, provided ``targeted_readback``
        is True (the default).  When read-back succeeds ``coordinator.data`` is
        updated with the decoded confirmed value and Home Assistant listeners
        are notified without triggering a full scan.  If read-back fails the
        coordinator falls back to a full refresh when ``refresh=True``.

        Callers that already perform their own full refresh after a sequence
        of writes (e.g. fan/climate entities, service dispatch) should pass
        ``targeted_readback=False`` to avoid a redundant or misleading
        intermediate read-back of a register that isn't 1:1 with displayed
        state.
        """
        refresh_after_write = False
        _raw_readback: list[int] | None = None
        _readback_definition: Any = None

        async with self._device_client._write_lock:
            try:
                success, refresh_after_write = await self._locked_single_register_write(
                    register_name=register_name,
                    value=value,
                    offset=offset,
                    refresh=refresh,
                )
                if not success:
                    return False

                # Targeted read-back while still holding the write lock so no
                # concurrent Modbus operation can interleave between write and
                # read-back, preventing transaction-ID mismatches.
                _definition = self._resolve_write_definition(register_name)
                if (
                    targeted_readback
                    and _definition is not None
                    and _targeted_readback_safe(register_name, _definition)
                ):
                    _raw_readback = await self._locked_read_holding_registers(
                        _definition.address + offset,
                        count=_definition.length,
                    )
                    if _raw_readback is not None:
                        _readback_definition = _definition
                        refresh_after_write = False
                    else:
                        _LOGGER.debug(
                            "Targeted read-back failed for %s; falling back to full refresh",
                            register_name,
                        )

            except (ModbusException, ConnectionException):  # pragma: no cover - safety
                _LOGGER.exception("Failed to write register %s", register_name)
                return False

        # Apply read-back result outside the lock so listener notifications cannot
        # re-enter the Modbus transport lock.
        if _raw_readback is not None and _readback_definition is not None:
            try:
                _decoded = _readback_definition.decode(_raw_readback)
                if (
                    getattr(_readback_definition, "enum", None) is not None
                    and isinstance(_decoded, str)
                    and isinstance(_raw_readback[0], int)
                ):
                    # The polling pipeline (process_register_value) stores raw
                    # ints for enum registers, not labels; keep the same
                    # representation so switch.is_on / select.current_option
                    # don't break until the next full poll.
                    _decoded = _raw_readback[0]
            except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
                # The write itself already succeeded; a bad read-back decode
                # must not turn a successful write into a failure.
                _LOGGER.debug("Targeted read-back decode failed for %s: %s", register_name, exc)
                if refresh:
                    refresh_after_write = True
            else:
                _updated_data = dict(self.data) if self.data else {}
                _updated_data[register_name] = _decoded
                try:
                    self.async_set_updated_data(_updated_data)
                except (TypeError, AttributeError):
                    _LOGGER.debug(
                        "Skipping listener notification after read-back for %s", register_name
                    )
                _LOGGER.debug("Targeted read-back for %s decoded to %r", register_name, _decoded)

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
        async with self._device_client._write_lock:
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

    async def _locked_read_holding_registers(
        self,
        start_address: int,
        count: int,
    ) -> list[int] | None:
        """Read holding registers without acquiring _write_lock.

        Caller MUST already hold _write_lock. Returns None on any failure.
        """
        try:
            if self._device_client._transport is not None:
                response = await self._device_client._transport.read_holding_registers(
                    self._device_client.slave_id,
                    start_address,
                    count=count,
                    attempt=1,
                )
            elif self._device_client.client is not None:
                response = await self._device_client._call_modbus(
                    self._device_client.client.read_holding_registers,
                    start_address,
                    count=count,
                    attempt=1,
                )
            else:
                return None
            if hasattr(response, "isError") and response.isError():
                return None
            regs = getattr(response, "registers", None)
            return list(regs) if regs is not None else None
        except (
            ModbusException,
            ConnectionException,
            TimeoutError,
            OSError,
            AttributeError,
            TypeError,
        ):
            _LOGGER.debug("Read-back at address %s failed", start_address)
            return None

    async def async_write_and_read_holding_registers(
        self,
        start_address: int,
        values: list[int],
        readback_count: int,
        *,
        require_single_request: bool = False,
    ) -> tuple[bool, list[int] | None]:
        """Write holding registers and immediately read them back under one lock.

        Holds _write_lock for the entire write + read-back sequence so that no
        concurrent Modbus operation (scan, update, or other write) can interleave
        between the write and the read-back.  This prevents transaction-ID
        mismatches that occur when a pymodbus TCP client is shared across
        concurrent coroutines.

        Returns (write_success, readback_registers_or_None).
        """
        if not self._validate_multi_register_write_request(
            start_address, values, require_single_request
        ):
            return False, None

        async with self._device_client._write_lock:
            try:
                await self._ensure_connection()
                self._assert_write_connection_ready()

                success, _ = await run_multi_register_write_attempts(
                    self, start_address, values, require_single_request, False
                )
                if not success:
                    return False, None

                readback = await self._locked_read_holding_registers(start_address, readback_count)
                return True, readback

            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug("Write+readback at address %s failed: %s", start_address, exc)
                return False, None

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
