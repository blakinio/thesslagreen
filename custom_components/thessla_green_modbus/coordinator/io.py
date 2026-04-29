"""Read-path coordinator mixin kept as thin delegating facade."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from .._coordinator_read_batches import (
    read_holding_individually as _read_holding_individually_impl,
)
from .._coordinator_read_batches import (
    read_holding_registers_optimized as _read_holding_registers_optimized_impl,
)
from .._coordinator_read_batches import (
    read_input_registers_optimized as _read_input_registers_optimized_impl,
)
from .._coordinator_read_bits import (
    read_coil_registers_optimized as _read_coil_registers_optimized_impl,
)
from .._coordinator_read_bits import (
    read_discrete_inputs_optimized as _read_discrete_inputs_optimized_impl,
)
from .._coordinator_read_common import (
    execute_read_call as _execute_read_call_impl,
)
from .._coordinator_read_common import (
    is_illegal_data_address_response as _is_illegal_data_address_response_impl,
)
from .._coordinator_read_common import (
    is_transient_error_response as _is_transient_error_response_impl,
)
from .._coordinator_read_common import (
    log_read_retry as _log_read_retry_impl,
)
from .._coordinator_read_common import (
    raise_for_error_response as _raise_for_error_response_impl,
)
from .._coordinator_runtime_io import (
    call_modbus as _call_modbus_impl,
)
from .._coordinator_runtime_io import (
    read_all_register_data as _read_all_register_data_impl,
)
from .retry import (
    disconnect_and_reconnect_for_retry as _disconnect_and_reconnect_for_retry_impl,
)
from .retry import (
    read_with_retry as _read_with_retry_impl,
)

if TYPE_CHECKING:
    from ..modbus_transport import BaseModbusTransport


class _ModbusIOMixin:
    """Read-path Modbus methods used by the coordinator."""

    _transport: BaseModbusTransport | None
    client: Any | None
    slave_id: int
    timeout: float
    retry: int
    backoff: float
    backoff_jitter: float | tuple[float, float] | None

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
        return await _call_modbus_impl(self, func, *args, attempt=attempt, **kwargs)

    async def _read_all_register_data(self) -> dict[str, Any]:
        return await _read_all_register_data_impl(self)

    @staticmethod
    def _is_illegal_data_address_response(response: Any) -> bool:
        return bool(_is_illegal_data_address_response_impl(response))

    @staticmethod
    def _is_transient_error_response(response: Any) -> bool:
        return bool(_is_transient_error_response_impl(response))

    async def _execute_read_call(
        self,
        read_method: Callable[..., Any],
        start_address: int,
        count: int,
        attempt: int,
    ) -> Any:
        return await _execute_read_call_impl(self, read_method, start_address, count, attempt)

    async def _disconnect_and_reconnect_for_retry(
        self,
        *,
        register_type: str,
        start_address: int,
        attempt: int,
    ) -> Exception | None:
        return await _disconnect_and_reconnect_for_retry_impl(
            self,
            register_type=register_type,
            start_address=start_address,
            attempt=attempt,
        )

    def _log_read_retry(
        self,
        *,
        register_type: str,
        start_address: int,
        attempt: int,
        exc: Exception,
        timeout: bool = False,
    ) -> None:
        _log_read_retry_impl(
            self,
            register_type=register_type,
            start_address=start_address,
            attempt=attempt,
            exc=exc,
            timeout=timeout,
        )

    def _raise_for_error_response(
        self,
        response: Any,
        *,
        register_type: str,
        start_address: int,
    ) -> None:
        _raise_for_error_response_impl(
            self,
            response,
            register_type=register_type,
            start_address=start_address,
        )

    async def _read_with_retry(
        self,
        read_method: Callable[..., Any],
        start_address: int,
        count: int,
        *,
        register_type: str,
    ) -> Any:
        return await _read_with_retry_impl(
            self,
            read_method,
            start_address,
            count,
            register_type=register_type,
        )

    async def _read_input_registers_optimized(self) -> dict[str, Any]:
        return await _read_input_registers_optimized_impl(self)

    async def _read_holding_individually(
        self,
        read_method: Any,
        chunk_start: int,
        register_names: list[str | None],
        data: dict[str, Any],
    ) -> None:
        await _read_holding_individually_impl(
            self,
            read_method,
            chunk_start,
            register_names,
            data,
        )

    async def _read_holding_registers_optimized(self) -> dict[str, Any]:
        return await _read_holding_registers_optimized_impl(self)

    async def _read_coil_registers_optimized(self) -> dict[str, Any]:
        return await _read_coil_registers_optimized_impl(self)

    async def _read_discrete_inputs_optimized(self) -> dict[str, Any]:  # pragma: no cover
        return await _read_discrete_inputs_optimized_impl(self)
