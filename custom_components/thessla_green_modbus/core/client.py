"""Device-domain client for ThesslaGreen Modbus integration.

ThesslaGreenDeviceClient owns all device-domain state and operations,
keeping the coordinator as a thin Home Assistant adapter.

Responsibilities are split across focused sub-modules:
- client_connection.py  – connection lifecycle and transport construction
- client_scanner.py     – scanner orchestration and capability discovery
- client_registers.py   – register groups, IO helpers, and write support
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Any, cast

from ..const import (
    coil_registers,
    discrete_input_registers,
    holding_registers,
    input_registers,
)
from ..coordinator.models import CoordinatorConfig
from ..scanner import DeviceCapabilities
from ..transport.base import BaseModbusTransport
from ..utils import utcnow as _utcnow
from .capabilities_mixin import _CoordinatorCapabilitiesMixin
from .client_connection import _DeviceClientConnectionMixin
from .client_registers import _DeviceClientRegistersMixin
from .client_scanner import _DeviceClientScannerMixin
from .io_mixin import _ModbusIOMixin

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenDeviceClient(
    _DeviceClientConnectionMixin,
    _DeviceClientScannerMixin,
    _DeviceClientRegistersMixin,
    _ModbusIOMixin,
    _CoordinatorCapabilitiesMixin,
):
    """Device-domain operations client for ThesslaGreen Modbus integration.

    Owns all device-domain mutable state and provides device operations.
    The coordinator acts as a thin HA adapter that delegates to this client.

    Method groups are implemented in focused mixins:
    - Connection lifecycle / transport: _DeviceClientConnectionMixin
    - Scanner orchestration: _DeviceClientScannerMixin
    - Register groups / IO helpers / writes: _DeviceClientRegistersMixin
    - Modbus read protocol: _ModbusIOMixin (core/io_mixin.py)
    - Derived capability metrics: _CoordinatorCapabilitiesMixin (core/capabilities_mixin.py)
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
