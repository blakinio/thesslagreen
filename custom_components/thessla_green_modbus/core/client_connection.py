"""Connection lifecycle and transport construction mixin for DeviceClient."""

from __future__ import annotations

import logging
from typing import Any

# Module-level name so tests can patch
# ``core.client_connection.AsyncModbusTcpClient`` without dynamic imports.
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
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
)
from ..registers.maps import input_registers
from ..scanner import is_request_cancelled_error
from ..transport.base import BaseModbusTransport
from .connection import (
    build_rtu_transport as _build_rtu_transport_impl,
)
from .connection import (
    build_tcp_transport as _build_tcp_transport_impl,
)
from .connection import (
    connect_direct_tcp_client as _connect_direct_tcp_client_impl,
)
from .connection import (
    connect_transport_or_client as _connect_transport_or_client_impl,
)
from .connection import (
    ensure_connected_runtime as _ensure_connected_runtime_impl,
)
from .connection import (
    ensure_transport_selected as _ensure_transport_selected_impl,
)
from .connection import (
    reconnect_client_if_needed as _reconnect_client_if_needed_impl,
)
from .connection_lifecycle import (
    ensure_connected_lifecycle as _ensure_connected_lifecycle_impl,
)
from .connection_state import (
    mark_connection_disconnected as _mark_connection_disconnected_impl,
)
from .connection_state import (
    mark_connection_established as _mark_connection_established_impl,
)
from .connection_state import (
    mark_connection_failure as _mark_connection_failure_impl,
)
from .connection_test import run_connection_test as _run_connection_test_impl
from .disconnect import (
    close_client_connection as _close_client_connection_impl,
)
from .disconnect import (
    disconnect_locked as _disconnect_locked_impl,
)
from .transport_select import (
    select_auto_transport as _select_auto_transport_impl,
)

_LOGGER = logging.getLogger(__name__)


class _DeviceClientConnectionMixin:
    """Connection lifecycle and transport construction for ThesslaGreenDeviceClient.

    Extracted from core/client.py to keep client.py focused on composition and
    public API. All methods require the standard DeviceClient attributes
    (config, hass, client, _transport, _client_lock, _write_lock, etc.).
    """

    # Declared here for type-checker; actual values set in ThesslaGreenDeviceClient.__init__.
    config: Any
    hass: Any
    client: Any
    _transport: Any
    _client_lock: Any
    _write_lock: Any
    offline_state: bool
    statistics: dict[str, Any]
    _resolved_connection_mode: str | None

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

        ``AsyncModbusTcpClient`` is a module-level name so tests can patch
        ``core.client_connection.AsyncModbusTcpClient`` without any dynamic
        import indirection.
        """
        direct_client = await _connect_direct_tcp_client_impl(
            host=self.config.host,
            port=self.config.port,
            timeout=self.timeout,
            tcp_client_cls=AsyncModbusTcpClient,
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
