"""Device-domain Modbus client for ThesslaGreen units.

This module owns all device/protocol concerns.  It deliberately contains no
Home Assistant imports so that it can be tested and reused independently.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from ..const import (
    CONNECTION_MODE_AUTO,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
)
from ..registers.maps import (
    coil_registers,
    discrete_input_registers,
    holding_registers,
    input_registers,
)
from ..scanner import DeviceCapabilities
from ..utils import utcnow as _utcnow
from .capabilities_mixin import _CoordinatorCapabilitiesMixin
from .client_connection import _DeviceClientConnectionMixin
from .client_registers import _DeviceClientRegistersMixin
from .client_scanner import _DeviceClientScannerMixin
from .models import CoordinatorConfig

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenDeviceClient(
    _CoordinatorCapabilitiesMixin,
    _DeviceClientConnectionMixin,
    _DeviceClientRegistersMixin,
    _DeviceClientScannerMixin,
):
    """Device-domain client owning connection, scanner and register state."""

    def __init__(
        self,
        config: CoordinatorConfig,
        *,
        hass: Any = None,
        effective_batch: int = DEFAULT_MAX_REGISTERS_PER_REQUEST,
        resolved_connection_mode: str | None = None,
        backoff: float = 1.0,
        backoff_jitter: float | tuple[float, float] | None = None,
        entry: Any = None,
    ) -> None:
        """Initialize device client state."""
        self.config = config
        self.hass = hass
        self.entry = entry

        # Connection/config state.
        self.host = config.host
        self.port = config.port
        self.slave_id = config.slave_id
        self._device_name = config.name
        self.timeout = config.timeout
        self.retry = config.retry
        self.backoff = backoff
        self.backoff_jitter = backoff_jitter
        self.connection_type = config.connection_type
        self.connection_mode = config.connection_mode
        self._resolved_connection_mode = resolved_connection_mode
        self.serial_port = config.serial_port
        self.baud_rate = config.baud_rate
        self.parity = config.parity
        self.stop_bits = config.stop_bits
        self.effective_batch = effective_batch
        self.force_full_register_list = config.force_full_register_list
        self.scan_uart_settings = config.scan_uart_settings
        self.deep_scan = config.deep_scan
        self.safe_scan = config.safe_scan
        self.skip_missing_registers = config.skip_missing_registers

        # Client/transport lifecycle.
        self.client: Any = None
        self._transport: Any = None
        self._client_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._update_in_progress = False
        self.offline_state = False

        # Device and register state.
        self.device_info: dict[str, Any] = {}
        self.capabilities = DeviceCapabilities()
        self.available_registers: dict[str, set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
            "calculated": set(),
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
    def device_name(self) -> str:
        """Return the configured or detected device name."""
        return str(self.device_info.get("device_name") or self._device_name)

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

    async def async_close(self) -> None:
        """Close the active connection."""
        await self.async_disconnect()

    async def async_test_connection(self) -> bool:
        """Test whether the configured device can be reached."""
        try:
            await self.async_ensure_connected()
        except Exception:  # noqa: BLE001 - device boundary converts failures to bool
            return False
        return self.is_connected

    async def async_scan_device(self) -> dict[str, Any]:
        """Run a device scan and return its result."""
        scanner = await self.async_create_scanner()
        try:
            scan_result = await scanner.scan_device()
            if isinstance(scan_result, dict):
                return scan_result
            return dict(scan_result or {})
        finally:
            await scanner.close()

    @property
    def selected_connection_mode(self) -> str:
        """Return resolved connection mode or configured mode."""
        return self._resolved_connection_mode or self.connection_mode or CONNECTION_MODE_AUTO

    def mark_update_success(self) -> None:
        """Record a successful update timestamp."""
        self.statistics["last_successful_update"] = _utcnow()
