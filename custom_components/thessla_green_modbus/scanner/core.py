"""Device scanner for ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict as _dataclasses_asdict
from typing import TYPE_CHECKING, Any, cast

from .. import scanner_register_maps as _register_maps
from ..const import (
    CONNECTION_MODE_AUTO,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_PARITY,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOP_BITS,
    HOLDING_BATCH_BOUNDARIES,
    KNOWN_MISSING_REGISTERS,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
)
from ..modbus_helpers import async_maybe_await_close
from ..modbus_helpers import group_reads as _group_reads
from ..modbus_transport import (
    BaseModbusTransport,
    RtuModbusTransport,
)
from ..registers.loader import (
    async_get_all_registers,
)
from ..scanner_device_info import DeviceCapabilities, ScannerDeviceInfo
from ..scanner_helpers import (
    MAX_BATCH_REGISTERS,
)
from ..scanner_helpers import (
    SAFE_REGISTERS as _SAFE_REGISTERS,
)
from ..scanner_register_maps import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    MULTI_REGISTER_SIZES,
)
from ..utils import (
    resolve_connection_settings,
)
from . import capabilities_facade as scanner_capabilities_facade
from . import firmware as scanner_firmware
from . import orchestration as scanner_orchestration
from . import read_facade as scanner_read_facade
from . import register_map_runtime as scanner_register_map_runtime
from . import registers as scanner_registers
from . import selection as scanner_selection
from . import setup as scanner_setup

asdict = _dataclasses_asdict

_LOGGER = logging.getLogger(__name__)
REGISTER_DEFINITIONS = _register_maps.REGISTER_DEFINITIONS
SAFE_REGISTERS = _SAFE_REGISTERS
__all__ = [
    "DeviceCapabilities",
    "ThesslaGreenDeviceScanner",
]


if TYPE_CHECKING:  # pragma: no cover - typing helper only
    from pymodbus.client import AsyncModbusSerialClient as AsyncModbusSerialClientType
else:
    AsyncModbusSerialClientType = Any


class ThesslaGreenDeviceScanner(
    scanner_capabilities_facade.ScannerCapabilitiesFacadeMixin,
    scanner_read_facade.ScannerReadFacadeMixin,
):
    """Device scanner for ThesslaGreen AirPack Home - compatible with pymodbus 3.5.*+"""

    available_registers: dict[str, set[str]]
    failed_addresses: dict[str, dict[str, set[int]]]
    capabilities: DeviceCapabilities
    _registers: dict[int, dict[int, str]]
    _register_ranges: dict[str, tuple[int | None, int | None]]
    _names_by_address: dict[int, dict[int, set[str]]]
    _holding_failures: dict[int, int]
    _failed_holding: set[int]
    _input_failures: dict[int, int]
    _failed_input: set[int]
    _input_skip_log_ranges: set[tuple[int, int]]
    _unsupported_input_ranges: dict[tuple[int, int], int]
    _unsupported_holding_ranges: dict[tuple[int, int], int]
    _client: Any | None
    _transport: Any | None
    _reported_invalid: set[str]
    _sensor_unavailable_checks: dict[str, Any]

    def __init__(
        self,
        host: str,
        port: int,
        slave_id: int = DEFAULT_SLAVE_ID,
        timeout: int = 10,
        retry: int = 3,
        backoff: float = 0,
        backoff_jitter: float | tuple[float, float] | None = None,
        verbose_invalid_values: bool = False,
        scan_uart_settings: bool = DEFAULT_SCAN_UART_SETTINGS,
        skip_known_missing: bool = False,
        deep_scan: bool = False,
        full_register_scan: bool = False,
        safe_scan: bool = False,
        max_registers_per_request: int = MAX_BATCH_REGISTERS,
        connection_type: str = DEFAULT_CONNECTION_TYPE,
        connection_mode: str | None = None,
        serial_port: str = DEFAULT_SERIAL_PORT,
        baud_rate: int = DEFAULT_BAUD_RATE,
        parity: str = DEFAULT_PARITY,
        stop_bits: int = DEFAULT_STOP_BITS,
        *,
        hass: Any | None = None,
        registers_ready: bool = False,
    ) -> None:
        """Initialize device scanner with consistent parameter names.

        ``max_registers_per_request`` is clamped to the safe Modbus range of
        1-16 registers per request.
        """
        if not registers_ready:
            scanner_register_map_runtime.ensure_register_maps(
                scanner_register_map_runtime.initial_register_hash()
            )
        # Avoid sticky logger levels from previous tests/services.
        _LOGGER.setLevel(logging.DEBUG)
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        try:
            self.backoff = float(backoff)
        except (TypeError, ValueError):
            self.backoff = 0.0
        self.backoff_jitter = scanner_setup.normalize_backoff_jitter(backoff_jitter)
        self.verbose_invalid_values = verbose_invalid_values
        self.scan_uart_settings = scan_uart_settings
        self.skip_known_missing = skip_known_missing
        self.deep_scan = deep_scan
        self.full_register_scan = full_register_scan
        self.safe_scan = safe_scan
        try:
            self.effective_batch = min(int(max_registers_per_request), MAX_BATCH_REGISTERS)
        except (TypeError, ValueError):
            self.effective_batch = MAX_BATCH_REGISTERS
        if self.effective_batch < 1:
            self.effective_batch = 1
        self.max_registers_per_request = self.effective_batch

        (
            resolved_type,
            resolved_mode,
            resolved_fixed_mode,
        ) = self._resolve_connection_configuration(
            connection_type,
            connection_mode,
            port,
        )
        self.connection_type = resolved_type
        self.connection_mode = resolved_mode
        self._resolved_connection_mode: str | None = resolved_fixed_mode
        self.serial_port = serial_port or DEFAULT_SERIAL_PORT
        try:
            self.baud_rate = int(baud_rate)
        except (TypeError, ValueError):
            self.baud_rate = DEFAULT_BAUD_RATE
        parity_norm = str(parity or DEFAULT_PARITY).lower()
        if parity_norm not in SERIAL_PARITY_MAP:
            parity_norm = DEFAULT_PARITY
        self.parity = parity_norm
        self.stop_bits = SERIAL_STOP_BITS_MAP.get(
            stop_bits,
            SERIAL_STOP_BITS_MAP.get(str(stop_bits), DEFAULT_STOP_BITS),
        )
        if self.stop_bits not in (1, 2):
            self.stop_bits = DEFAULT_STOP_BITS
        self._hass = hass

        scanner_setup.initialize_runtime_collections(self, DeviceCapabilities)
        self._input_register_map = INPUT_REGISTERS
        self._holding_register_map = HOLDING_REGISTERS
        self._coil_register_map = COIL_REGISTERS
        self._discrete_input_register_map = DISCRETE_INPUT_REGISTERS
        self._known_missing_registers = KNOWN_MISSING_REGISTERS
        self._multi_register_sizes = MULTI_REGISTER_SIZES

        self._populate_known_missing_addresses()

    def _populate_known_missing_addresses(self) -> None:
        """Pre-compute addresses of known missing registers for batch grouping."""
        scanner_setup.populate_known_missing_addresses(self)
        self._update_known_missing_addresses()

    @staticmethod
    def _resolve_connection_configuration(
        connection_type: str,
        connection_mode: str | None,
        port: int,
    ) -> tuple[str, str, str | None]:
        """Resolve transport selection and cached fixed mode."""
        resolved_type, resolved_mode = resolve_connection_settings(
            connection_type, connection_mode, port
        )
        resolved_fixed_mode = resolved_mode if resolved_mode != CONNECTION_MODE_AUTO else None
        return resolved_type, resolved_mode, resolved_fixed_mode

    def _update_known_missing_addresses(self) -> None:
        """Populate cached missing register addresses from known missing list."""
        scanner_setup.update_known_missing_addresses(
            self,
            known_missing_registers=self._known_missing_registers,
            input_registers=self._input_register_map,
            holding_registers=self._holding_register_map,
            coil_registers=self._coil_register_map,
            discrete_input_registers=self._discrete_input_register_map,
            multi_register_sizes=self._multi_register_sizes,
        )

    async def _async_setup(self) -> None:
        """Asynchronously load register definitions."""
        await scanner_setup.async_setup_register_maps(self)
        self._names_by_address = {
            4: self._build_names_by_address(
                {name: addr for addr, name in self._registers.get(4, {}).items()}
                or self._input_register_map
            ),
            3: self._build_names_by_address(
                {name: addr for addr, name in self._registers.get(3, {}).items()}
                or self._holding_register_map
            ),
            1: self._build_names_by_address(
                {name: addr for addr, name in self._registers.get(1, {}).items()}
                or self._coil_register_map
            ),
            2: self._build_names_by_address(
                {name: addr for addr, name in self._registers.get(2, {}).items()}
                or self._discrete_input_register_map
            ),
        }
        self._update_known_missing_addresses()

    @staticmethod
    def _build_names_by_address(mapping: dict[str, int]) -> dict[int, set[str]]:
        """Create address->name aliases map from name->address mapping."""
        return scanner_selection.build_names_by_address(mapping)

    def _alias_names(self, function: int, address: int) -> set[str]:
        """Return all register names sharing the same function/address pair."""

        return self._names_by_address.get(function, {}).get(address, set())

    @classmethod
    async def create(
        cls,
        host: str,
        port: int,
        slave_id: int = DEFAULT_SLAVE_ID,
        timeout: int = 10,
        retry: int = 3,
        backoff: float = 0,
        backoff_jitter: float | tuple[float, float] | None = None,
        verbose_invalid_values: bool = False,
        scan_uart_settings: bool = DEFAULT_SCAN_UART_SETTINGS,
        skip_known_missing: bool = False,
        deep_scan: bool = False,
        full_register_scan: bool = False,
        max_registers_per_request: int = MAX_BATCH_REGISTERS,
        safe_scan: bool = False,
        connection_type: str = DEFAULT_CONNECTION_TYPE,
        connection_mode: str | None = None,
        serial_port: str = DEFAULT_SERIAL_PORT,
        baud_rate: int = DEFAULT_BAUD_RATE,
        parity: str = DEFAULT_PARITY,
        stop_bits: int = DEFAULT_STOP_BITS,
        hass: Any | None = None,
    ) -> ThesslaGreenDeviceScanner:
        """Factory to create an initialized scanner instance."""
        return cast(
            ThesslaGreenDeviceScanner,
            await scanner_setup.async_create_scanner_instance(
                cls,
                host=host,
                port=port,
                slave_id=slave_id,
                timeout=timeout,
                retry=retry,
                backoff=backoff,
                backoff_jitter=backoff_jitter,
                verbose_invalid_values=verbose_invalid_values,
                scan_uart_settings=scan_uart_settings,
                skip_known_missing=skip_known_missing,
                deep_scan=deep_scan,
                full_register_scan=full_register_scan,
                max_registers_per_request=max_registers_per_request,
                safe_scan=safe_scan,
                connection_type=connection_type,
                connection_mode=connection_mode,
                serial_port=serial_port,
                baud_rate=baud_rate,
                parity=parity,
                stop_bits=stop_bits,
                hass=hass,
            ),
        )

    async def close(self) -> None:
        """Close the underlying Modbus client connection."""
        await scanner_setup.async_close_connection(self, async_maybe_await_close)

    def _build_tcp_transport(
        self,
        mode: str,
        *,
        timeout_override: float | None = None,
    ) -> BaseModbusTransport:
        return scanner_setup.build_tcp_transport(
            self,
            mode,
            timeout_override=timeout_override,
        )

    def _build_auto_tcp_attempts(self) -> list[tuple[str, BaseModbusTransport, float]]:
        return scanner_setup.build_auto_tcp_attempts(self)

    async def verify_connection(self) -> None:
        """Verify basic Modbus connectivity by reading a few safe registers.

        A handful of well-known registers are read from the device to confirm
        that the TCP connection and Modbus protocol are functioning. Any
        failure will raise a ``ModbusException`` or ``ConnectionException`` so
        callers can surface an appropriate error to the user.
        """

        await scanner_setup.verify_connection(
            self,
            safe_registers=SAFE_REGISTERS,
            register_definitions=REGISTER_DEFINITIONS,
            holding_batch_boundaries=HOLDING_BATCH_BOUNDARIES,
            group_reads=_group_reads,
            rtu_transport_cls=RtuModbusTransport,
        )

    def _group_registers_for_batch_read(
        self,
        addresses: list[int],
        *,
        max_gap: int = 1,
        max_batch: int | None = None,
        boundaries: frozenset[int] | None = None,
    ) -> list[tuple[int, int]]:
        """Group consecutive register addresses for efficient batch reads.

        The grouping implementation delegates to the shared ``group_reads`` helper so that the
        scanner benefits from the same optimisation logic used elsewhere in the
        project.  Any registers that have previously been marked as missing are
        split into their own single-register groups to avoid unnecessary
        failures when reading surrounding ranges.
        """

        return scanner_selection.group_registers_for_batch_read(
            self,
            addresses,
            max_gap=max_gap,
            max_batch=max_batch,
            boundaries=boundaries,
        )

    async def _scan_firmware_info(self, info_regs: list[int], device: ScannerDeviceInfo) -> None:
        """Parse firmware version from info_regs and update device."""
        await scanner_firmware.scan_firmware_info(self, info_regs, device)

    async def _scan_device_identity(self, info_regs: list[int], device: ScannerDeviceInfo) -> None:
        """Parse serial number and device name from registers into device."""
        await scanner_firmware.scan_device_identity(self, info_regs, device)

    def _select_scan_registers(
        self,
    ) -> tuple[dict[int, str], dict[int, str], dict[int, str], dict[int, str], int, int, int, int]:
        """Select which registers to scan and compute address ranges."""
        return scanner_selection.select_scan_registers(self)

    async def _run_full_scan(
        self,
        input_max: int,
        holding_max: int,
        coil_max: int,
        discrete_max: int,
        unknown_registers: dict[str, dict[int, Any]],
        scanned_registers: dict[str, int],
    ) -> None:
        """Scan all registers up to max known address (full_register_scan mode)."""
        await scanner_orchestration.run_full_scan(
            self,
            input_max,
            holding_max,
            coil_max,
            discrete_max,
            unknown_registers,
            scanned_registers,
        )

    async def _scan_register_batch(
        self,
        reg_type: str,
        addr_to_names: dict[int, set[str]],
        addresses: list[int],
        read_fn: Callable[..., Awaitable[list[int] | None]],
        *,
        boundaries: frozenset[int] | None = None,
    ) -> None:
        """Read a batch of registers of one FC type, with per-address fallback."""
        await scanner_registers.scan_register_batch(
            self,
            reg_type,
            addr_to_names,
            addresses,
            read_fn,
            boundaries=boundaries,
        )

    async def _scan_named_input(self, input_registers: dict[int, str]) -> None:
        """Scan FC04 input registers in batches."""
        await scanner_registers.scan_named_input(self, input_registers)

    async def _scan_named_holding(self, holding_registers: dict[int, str]) -> None:
        """Scan FC03 holding registers in batches, handling multi-word registers."""
        await scanner_registers.scan_named_holding(self, holding_registers)

    async def _scan_named_coil(self, coil_registers: dict[int, str]) -> None:
        """Scan FC01 coil registers in batches."""
        await scanner_registers.scan_named_coil(self, coil_registers)

    async def _scan_named_discrete(self, discrete_registers: dict[int, str]) -> None:
        """Scan FC02 discrete input registers in batches."""
        await scanner_registers.scan_named_discrete(self, discrete_registers)

    async def _run_named_scan(
        self,
        input_registers: dict[int, str],
        holding_registers: dict[int, str],
        coil_registers: dict[int, str],
        discrete_registers: dict[int, str],
    ) -> None:
        """Scan only named/known registers (normal scan mode)."""
        await scanner_registers.run_named_scan(
            self,
            input_registers,
            holding_registers,
            coil_registers,
            discrete_registers,
        )

    def _compute_scan_blocks(
        self,
        input_registers: dict[int, str],
        holding_registers: dict[int, str],
        coil_registers: dict[int, str],
        discrete_registers: dict[int, str],
        input_max: int,
        holding_max: int,
        coil_max: int,
        discrete_max: int,
    ) -> dict[str, tuple[int | None, int | None]]:
        """Build scan_blocks dict describing the address range that was scanned."""
        return scanner_registers.compute_scan_blocks(
            self,
            input_registers,
            holding_registers,
            coil_registers,
            discrete_registers,
            input_max,
            holding_max,
            coil_max,
            discrete_max,
        )

    def _collect_missing_registers(
        self,
        input_registers: dict[int, str],
        holding_registers: dict[int, str],
        coil_registers: dict[int, str],
        discrete_registers: dict[int, str],
    ) -> dict[str, dict[str, int]]:
        """Return registers that were expected but not found during scan."""
        return scanner_registers.collect_missing_registers(
            self,
            input_registers,
            holding_registers,
            coil_registers,
            discrete_registers,
        )

    async def scan(self) -> dict[str, Any]:  # pragma: no cover - defensive
        """Perform the actual register scan using an established connection."""
        return await scanner_orchestration.scan(self)

    async def scan_device(self) -> dict[str, Any]:
        """Open the Modbus connection, perform a scan and close the client."""
        self._rtu_transport_cls = RtuModbusTransport
        return await scanner_orchestration.scan_device(self)

    async def _load_registers(
        self,
    ) -> tuple[
        dict[int, dict[int, str]],
        dict[str, tuple[float | None, float | None]],
    ]:
        """Load Modbus register definitions and value ranges."""
        return await scanner_registers.load_registers(self, async_get_all_registers)

    def _log_skipped_ranges(self) -> None:
        """Log summary of ranges skipped due to Modbus exceptions."""
        scanner_registers.log_skipped_ranges(self)
