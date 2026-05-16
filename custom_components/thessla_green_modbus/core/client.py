"""Device-domain client for ThesslaGreen Modbus integration.

ThesslaGreenDeviceClient owns all device-domain state and operations,
keeping the coordinator as a thin Home Assistant adapter.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from contextlib import suppress
from typing import TYPE_CHECKING, Any, cast

from pymodbus.client import AsyncModbusTcpClient

from ..const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_PARITY,
    DEFAULT_STOP_BITS,
    HOLDING_BATCH_BOUNDARIES,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
    coil_registers,
    discrete_input_registers,
    holding_registers,
    input_registers,
)
from ..coordinator.capabilities import _CoordinatorCapabilitiesMixin
from ..coordinator.connection import (
    build_rtu_transport as _build_rtu_transport_impl,
)
from ..coordinator.connection import (
    build_tcp_transport as _build_tcp_transport_impl,
)
from ..coordinator.connection import (
    connect_direct_tcp_client as _connect_direct_tcp_client_impl,
)
from ..coordinator.connection import (
    connect_transport_or_client as _connect_transport_or_client_impl,
)
from ..coordinator.connection import (
    ensure_connected_runtime as _ensure_connected_runtime_impl,
)
from ..coordinator.connection import (
    ensure_transport_selected as _ensure_transport_selected_impl,
)
from ..coordinator.connection import (
    reconnect_client_if_needed as _reconnect_client_if_needed_impl,
)
from ..coordinator.connection_lifecycle import (
    ensure_connected_lifecycle as _ensure_connected_lifecycle_impl,
)
from ..coordinator.connection_state import (
    mark_connection_disconnected as _mark_connection_disconnected_impl,
)
from ..coordinator.connection_state import (
    mark_connection_established as _mark_connection_established_impl,
)
from ..coordinator.connection_state import (
    mark_connection_failure as _mark_connection_failure_impl,
)
from ..coordinator.connection_test import run_connection_test as _run_connection_test_impl
from ..coordinator.disconnect import (
    close_client_connection as _close_client_connection_impl,
)
from ..coordinator.disconnect import (
    disconnect_locked as _disconnect_locked_impl,
)
from ..coordinator.io import _ModbusIOMixin
from ..coordinator.models import CoordinatorConfig
from ..coordinator.register_groups import (
    compute_register_groups as _compute_register_groups_impl,
)
from ..coordinator.register_processing import (
    find_register_name as _find_register_name_impl,
)
from ..coordinator.register_processing import (
    process_register_value as _process_register_value_impl,
)
from ..coordinator.runtime_state import (
    clear_register_failure as _clear_register_failure_impl,
)
from ..coordinator.runtime_state import (
    mark_registers_failed as _mark_registers_failed_impl,
)
from ..coordinator.scan import (
    normalise_available_registers as _normalise_available_registers_impl,
)
from ..coordinator.scanner_kwargs import build_scanner_kwargs as _build_scanner_kwargs_impl
from ..coordinator.transport_select import (
    select_auto_transport as _select_auto_transport_impl,
)
from ..register_defs_cache import get_register_definitions
from ..registers.read_planner import group_reads
from ..registers.register_def import RegisterDef
from ..scanner import (
    DeviceCapabilities,
    ThesslaGreenDeviceScanner,
    is_request_cancelled_error,
)
from ..transport.base import BaseModbusTransport
from ..utils import utcnow as _utcnow

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_ORIGINAL_ASYNC_MODBUS_TCP_CLIENT = AsyncModbusTcpClient


def _get_register_definition(name: str) -> RegisterDef:
    return get_register_definitions()[name]


class ThesslaGreenDeviceClient(_ModbusIOMixin, _CoordinatorCapabilitiesMixin):
    """Device-domain operations client for ThesslaGreen Modbus integration.

    Owns all device-domain mutable state and provides device operations.
    The coordinator acts as a thin HA adapter that delegates to this client.
    """

    #: Asyncio locks owned by this client (coordinator proxies access these).
    _client_lock: asyncio.Lock
    _write_lock: asyncio.Lock

    def __init__(
        self,
        config: CoordinatorConfig,
        *,
        hass: HomeAssistant,
        effective_batch: int,
        resolved_connection_mode: str | None,
        backoff: float,
        backoff_jitter: float | tuple[float, float] | None,
        entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize device client from coordinator config."""
        self.config = config
        self.hass = hass

        # Convenience aliases for frequently-accessed config fields.
        self.slave_id = config.slave_id
        self.timeout = config.timeout
        self.retry = config.retry
        self.backoff = backoff
        self.backoff_jitter = backoff_jitter
        self.force_full_register_list = config.force_full_register_list
        self.scan_uart_settings = config.scan_uart_settings
        self.deep_scan = config.deep_scan
        self.safe_scan = config.safe_scan
        self.skip_missing_registers = config.skip_missing_registers
        self.effective_batch = effective_batch
        self.max_registers_per_request = effective_batch
        self._resolved_connection_mode = resolved_connection_mode
        self._device_name: str = config.name

        # Connection state.
        self.client: Any | None = None
        self._transport: BaseModbusTransport | None = None
        self._client_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._update_in_progress: bool = False
        self.offline_state: bool = False

        # Device state.
        self.capabilities = DeviceCapabilities()
        if entry is not None and isinstance(entry.data.get("capabilities"), dict):
            with suppress(TypeError, ValueError):
                self.capabilities = DeviceCapabilities(**entry.data["capabilities"])
        self.device_info: dict[str, Any] = {}

        # Register availability and mappings.
        self.available_registers: dict[str, set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
            "calculated": {"estimated_power", "total_energy"},
        }
        self._register_maps: dict[str, dict[str, int]] = {
            "input_registers": input_registers().copy(),
            "holding_registers": holding_registers().copy(),
            "coil_registers": coil_registers().copy(),
            "discrete_inputs": discrete_input_registers().copy(),
        }
        self._reverse_maps: dict[str, dict[int, str]] = {
            key: {addr: name for name, addr in mapping.items()}
            for key, mapping in self._register_maps.items()
        }
        self._input_registers_rev = self._reverse_maps["input_registers"]
        self._holding_registers_rev = self._reverse_maps["holding_registers"]
        self._coil_registers_rev = self._reverse_maps["coil_registers"]
        self._discrete_inputs_rev = self._reverse_maps["discrete_inputs"]
        self._register_groups: dict[str, list[tuple[int, int]]] = {}
        self._failed_registers: set[str] = set()

        # Scan state.
        self.device_scan_result: dict[str, Any] | None = None
        self.unknown_registers: dict[str, Any] = {}
        self.scanned_registers: dict[str, Any] = {}
        self.last_scan: Any = None

        # Statistics.
        self.statistics: dict[str, Any] = {
            "successful_reads": 0,
            "failed_reads": 0,
            "connection_errors": 0,
            "timeout_errors": 0,
            "last_error": None,
            "last_successful_update": None,
            "average_response_time": 0.0,
            "total_registers_read": 0,
        }
        self._consecutive_failures: int = 0
        self._max_failures: int = 5

        # Post-processing state (used by _CoordinatorCapabilitiesMixin).
        self._last_power_timestamp = _utcnow()
        self._total_energy: float = 0.0

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def async_ensure_connected(self) -> None:
        """Ensure Modbus connection is established."""
        await _ensure_connected_lifecycle_impl(
            self,
            ensure_connected_runtime_fn=_ensure_connected_runtime_impl,
            reconnect_client_if_needed_fn=_reconnect_client_if_needed_impl,
            ensure_transport_selected_fn_factory=self._build_transport_selector_fn,
            connect_transport_or_client_fn=_connect_transport_or_client_impl,
            mark_connection_established_fn=lambda: _mark_connection_established_impl(
                offline_state_setter=lambda value: setattr(self, "offline_state", value)
            ),
            mark_connection_failure_fn=lambda: _mark_connection_failure_impl(
                statistics=self.statistics,
                offline_state_setter=lambda value: setattr(self, "offline_state", value),
            ),
            logger=_LOGGER,
        )

    async def async_disconnect(self) -> None:
        """Disconnect from Modbus device."""
        async with self._client_lock:
            await self._disconnect_locked()

    async def async_close(self) -> None:
        """Close all resources (alias for async_disconnect)."""
        await self.async_disconnect()

    async def async_test_connection(self) -> None:
        """Test initial connection to the device."""
        async with self._write_lock:
            await _run_connection_test_impl(
                ensure_connection=self.async_ensure_connected,
                get_transport=lambda: self._transport,
                slave_id=self.config.slave_id,
                test_addresses=list(input_registers().values())[:3],
                is_cancelled_error=is_request_cancelled_error,
                logger=_LOGGER,
            )

    async def _disconnect_locked(self) -> None:
        """Disconnect without acquiring the client lock."""
        await _disconnect_locked_impl(
            transport=self._transport,
            client=self.client,
            close_client_connection_fn=_close_client_connection_impl,
            mark_connection_disconnected_fn=lambda: _mark_connection_disconnected_impl(
                offline_state_setter=lambda value: setattr(self, "offline_state", value)
            ),
            logger=_LOGGER,
        )
        self.client = None

    async def _ensure_connection(self) -> None:
        """Internal alias used by coordinator submodule duck-typing."""
        await self.async_ensure_connected()

    async def _disconnect(self) -> None:
        """Internal alias used by coordinator submodule duck-typing."""
        await self.async_disconnect()

    async def _close_client_connection(self) -> None:
        """Close client object safely for sync or async close implementations."""
        await _close_client_connection_impl(client=self.client, logger=_LOGGER)

    # ------------------------------------------------------------------
    # Transport construction
    # ------------------------------------------------------------------

    def _build_tcp_transport(self, mode: str) -> BaseModbusTransport:
        """Build a TCP (or RTU-over-TCP) transport for the given mode."""
        return _build_tcp_transport_impl(
            mode=mode,
            host=self.config.host,
            port=self.config.port,
            retry=self.retry,
            backoff=self.backoff,
            max_backoff=DEFAULT_MAX_BACKOFF,
            timeout=self.timeout,
            offline_state=self.offline_state,
            connection_type_tcp=CONNECTION_TYPE_TCP,
            connection_mode_tcp_rtu=CONNECTION_MODE_TCP_RTU,
        )

    async def _try_direct_client_connect(self, *, allow_parameterless_ctor: bool) -> bool:
        """Try connecting via AsyncModbusTcpClient and store the connected client.

        Looks up AsyncModbusTcpClient through the coordinator module so that
        tests can patch ``coordinator.coordinator.AsyncModbusTcpClient`` and
        have it take effect here.
        """
        from custom_components.thessla_green_modbus import coordinator as coordinator_pkg

        # Access the coordinator.py module via the package to pick up any
        # test patches on coordinator.coordinator.AsyncModbusTcpClient.
        coord_module = getattr(coordinator_pkg, "coordinator", None)
        tcp_client_cls = (
            getattr(coord_module, "AsyncModbusTcpClient", None)
            if coord_module is not None
            else None
        ) or _ORIGINAL_ASYNC_MODBUS_TCP_CLIENT

        direct_client = await _connect_direct_tcp_client_impl(
            host=self.config.host,
            port=self.config.port,
            timeout=self.timeout,
            tcp_client_cls=tcp_client_cls,
            allow_parameterless_ctor=allow_parameterless_ctor,
        )
        if direct_client is not None:
            self.client = direct_client
            self._transport = None
            return True
        return False

    def _build_transport_selector_fn(self) -> Any:
        """Return the transport selector callable for the connection lifecycle."""
        parity = SERIAL_PARITY_MAP.get(self.config.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])
        stop_bits = SERIAL_STOP_BITS_MAP.get(
            self.config.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]
        )

        async def _ensure_transport_selected() -> Any:
            return await _ensure_transport_selected_impl(
                current_transport=self._transport,
                connection_type=self.config.connection_type,
                connection_mode=self.config.connection_mode,
                host=self.config.host,
                port=self.config.port,
                serial_port=self.config.serial_port,
                baudrate=self.config.baud_rate,
                parity=parity,
                stopbits=stop_bits,
                retry=self.retry,
                backoff=self.backoff,
                max_backoff=DEFAULT_MAX_BACKOFF,
                timeout=self.timeout,
                offline_state=self.offline_state,
                connection_type_rtu=CONNECTION_TYPE_RTU,
                connection_mode_auto=CONNECTION_MODE_AUTO,
                connection_mode_tcp=CONNECTION_MODE_TCP,
                build_rtu_transport_fn=_build_rtu_transport_impl,
                build_tcp_transport_fn=self._build_tcp_transport,
                select_auto_transport_fn=lambda: _select_auto_transport_impl(
                    resolved_connection_mode=self._resolved_connection_mode,
                    build_tcp_transport=self._build_tcp_transport,
                    try_direct_client_connect=lambda allow_pc: self._try_direct_client_connect(
                        allow_parameterless_ctor=allow_pc
                    ),
                    port=self.config.port,
                    timeout=self.timeout,
                    slave_id=self.config.slave_id,
                    host=self.config.host,
                    logger=_LOGGER,
                ),
            )

        return _ensure_transport_selected

    # ------------------------------------------------------------------
    # Scanner / device scan
    # ------------------------------------------------------------------

    def _build_scanner_kwargs(self) -> dict[str, Any]:
        """Return constructor kwargs for scanner creation."""
        return _build_scanner_kwargs_impl(
            self,
            resolved_connection_mode=self._resolved_connection_mode,
        )

    async def async_create_scanner(self) -> ThesslaGreenDeviceScanner:
        """Instantiate a ThesslaGreenDeviceScanner using its create() factory."""
        return await ThesslaGreenDeviceScanner.create(**self._build_scanner_kwargs())

    async def async_scan_device(self) -> dict[str, Any]:
        """Run a full device scan and return the raw scan result.

        The caller (coordinator) is responsible for applying the result via
        ``apply_scan_result`` / ``_apply_scan_result_impl``.
        """
        scanner = await self.async_create_scanner()
        return await scanner.scan_device()

    def _normalise_available_registers(
        self, available: dict[str, list[str] | set[str]]
    ) -> dict[str, set[str]]:
        """Return available register names in canonical form."""
        return _normalise_available_registers_impl(self, available)

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
    # Write support (minimal, mirrors coordinator write helpers)
    # ------------------------------------------------------------------

    async def async_write_register(
        self,
        register_name: str,
        value: Any,
        *,
        entity_id: str = "",
        call_description: str = "",
        offset: int = 0,
    ) -> bool:
        """Write a single register by name.

        Delegates to the coordinator's write helpers. Intended for use
        by external callers (services, tests) once the DeviceClient is
        the canonical write path.
        """
        from ..coordinator.write_path import (
            SingleWritePlan,
            encode_write_value,
            run_single_write_attempts,
        )

        definition = _get_register_definition(register_name)
        address = self._register_maps.get("holding_registers", {}).get(register_name)
        if address is None:
            _LOGGER.error("Register %s not found in holding registers map", register_name)
            return False

        encoded_values, scalar_value = encode_write_value(register_name, definition, value, offset)
        if encoded_values is None and scalar_value is None:
            return False

        plan = SingleWritePlan(
            register_name=register_name,
            address=address,
            definition=definition,
            encoded_values=encoded_values,
            scalar_value=scalar_value,
            offset=offset,
            entity_id=entity_id,
            call_description=call_description,
        )
        return await run_single_write_attempts(self, plan)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_device_info(self) -> dict[str, Any]:
        """Return device info mapping for the connected unit."""
        return dict(self.device_info)

    def get_capabilities(self) -> DeviceCapabilities:
        """Return current device capabilities."""
        return self.capabilities

    def get_register_map(self, register_type: str) -> dict[str, int]:
        """Return the register map for the given register type."""
        return cast(dict[str, int], self._register_maps.get(register_type, {}))

    @property
    def is_connected(self) -> bool:
        """Return True if the device connection is currently active."""
        transport = self._transport
        if transport is not None:
            return transport.is_connected()
        return self.client is not None

    @property
    def selected_transport(self) -> str | None:
        """Return the currently selected transport/connection mode."""
        return self._resolved_connection_mode
