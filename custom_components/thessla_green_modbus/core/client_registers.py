"""Register operations and IO helpers mixin for DeviceClient."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any, cast

from ..const import HOLDING_BATCH_BOUNDARIES
from ..register_defs_cache import get_register_definitions
from ..registers.read_planner import group_reads
from ..registers.register_def import RegisterDef
from .register_groups import (
    compute_register_groups as _compute_register_groups_impl,
)
from .register_processing import (
    find_register_name as _find_register_name_impl,
)
from .register_processing import (
    process_register_value as _process_register_value_impl,
)
from .runtime_state import (
    clear_register_failure as _clear_register_failure_impl,
)
from .runtime_state import (
    mark_registers_failed as _mark_registers_failed_impl,
)

_LOGGER = logging.getLogger(__name__)


def _get_register_definition(name: str) -> RegisterDef:
    return get_register_definitions()[name]


class _DeviceClientRegistersMixin:
    """Register operations and IO helpers for ThesslaGreenDeviceClient.

    Extracted from core/client.py to keep client.py focused on composition and
    public API. All methods require the standard DeviceClient attributes
    (_register_maps, _reverse_maps, _failed_registers, _register_groups, etc.).
    """

    _register_maps: dict[str, Any]
    _reverse_maps: dict[str, Any]
    _failed_registers: set[str]
    _register_groups: dict[str, Any]
    client: Any
    _transport: Any

    # ------------------------------------------------------------------
    # Register groups
    # ------------------------------------------------------------------

    def compute_register_groups(self) -> None:
        """Pre-compute register groups for optimized batch reading."""
        _compute_register_groups_impl(
            self,
            get_register_definition=_get_register_definition,
            group_reads=group_reads,
            holding_batch_boundaries=HOLDING_BATCH_BOUNDARIES,
        )

    # ------------------------------------------------------------------
    # IO mixin required helpers (satisfy _ModbusIOMixin protocol)
    # ------------------------------------------------------------------

    def _find_register_name(self, register_type: str, address: int) -> str | None:
        """Find register name by address using pre-built reverse maps."""
        return _find_register_name_impl(self._reverse_maps, register_type, address)

    def _process_register_value(self, register_name: str, value: int) -> Any:
        """Decode a raw register value via register-processing helpers."""
        return _process_register_value_impl(register_name, value)

    def _mark_registers_failed(self, names: Iterable[str | None]) -> None:
        """Record registers that failed to read."""
        _mark_registers_failed_impl(self, names)

    def _clear_register_failure(self, name: str) -> None:
        """Remove register from failed list on successful read."""
        _clear_register_failure_impl(self, name)

    def _get_client_method(self, name: str) -> Callable[..., Any]:
        """Return a Modbus method from transport/client or a no-op placeholder."""
        for obj in (self._transport, self.client):
            if obj is None:
                continue
            method = getattr(obj, name, None)
            if callable(method):
                return cast(Callable[..., Any], method)

        async def _missing_method(*_args: Any, **_kwargs: Any) -> Any:
            return None

        _missing_method.__name__ = name
        return _missing_method

    # ------------------------------------------------------------------
    # Write support
    # ------------------------------------------------------------------

    def _resolve_write_address(self, register_name: str, definition: Any) -> int | None:
        if definition.function == 3:
            address = self._register_maps.get("holding_registers", {}).get(register_name)
        elif definition.function == 1:
            address = self._register_maps.get("coil_registers", {}).get(register_name)
        else:
            _LOGGER.error(
                "Register %s is not writable (function=%s)", register_name, definition.function
            )
            return None
        if address is None:
            _LOGGER.error("Register %s not found in register maps", register_name)
        return address

    async def _execute_modbus_write(self, plan: Any, function: int) -> Any:

        if function == 3:
            if plan.encoded_values is not None:
                if self._transport is not None:
                    return await self._transport.write_registers(
                        self.slave_id, plan.address, values=plan.encoded_values, attempt=1
                    )
                return await self._call_modbus(
                    self._get_client_method("write_registers"),
                    plan.address,
                    values=plan.encoded_values,
                    attempt=1,
                )
            if self._transport is not None:
                return await self._transport.write_register(
                    self.slave_id, plan.address, value=int(plan.scalar_value), attempt=1
                )
            return await self._call_modbus(
                self._get_client_method("write_register"),
                plan.address,
                value=int(plan.scalar_value),
                attempt=1,
            )
        # function == 1, coil
        return await self._call_modbus(
            self._get_client_method("write_coil"),
            plan.address,
            value=bool(plan.scalar_value),
            attempt=1,
        )

    def _build_write_plan(
        self,
        register_name: str,
        value: Any,
        offset: int,
    ) -> Any | None:
        from .write_path import SingleWritePlan, encode_write_value

        definition = _get_register_definition(register_name)
        address = self._resolve_write_address(register_name, definition)
        if address is None:
            return None
        encoded_values, scalar_value = encode_write_value(register_name, definition, value, offset)
        if encoded_values is None and scalar_value is None:
            return None
        return SingleWritePlan(
            register_name=register_name,
            address=address + offset,
            encoded_values=encoded_values,
            scalar_value=scalar_value,
            original_value=value,
        )

    async def _perform_write_and_verify(
        self,
        register_name: str,
        value: Any,
        plan: Any,
        function: int,
    ) -> bool:
        from pymodbus.exceptions import ConnectionException, ModbusException

        await self._ensure_connection()
        try:
            response = await self._execute_modbus_write(plan, function)
            if response is None or response.isError():
                _LOGGER.error("Failed to write register %s", register_name)
                return False
            self._clear_register_failure(register_name)
            _LOGGER.info("Successfully wrote %s to register %s", value, register_name)
            return True
        except (ModbusException, ConnectionException, TimeoutError, OSError) as exc:
            _LOGGER.exception("Error writing register %s: %s", register_name, exc)
            return False

    async def async_write_register(
        self,
        register_name: str,
        value: Any,
        *,
        entity_id: str = "",
        call_description: str = "",
        offset: int = 0,
    ) -> bool:
        """Write a single register by name."""
        plan = self._build_write_plan(register_name, value, offset)
        if plan is None:
            return False
        definition = _get_register_definition(register_name)
        return await self._perform_write_and_verify(register_name, value, plan, definition.function)
