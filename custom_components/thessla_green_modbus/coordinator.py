"""Data coordinator for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

from homeassistant.util import dt as dt_util

try:  # pragma: no cover - used in runtime environments only
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP
except (ModuleNotFoundError, ImportError):  # pragma: no cover - test fallback
    EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"

from homeassistant.core import HomeAssistant

from .modbus_exceptions import ConnectionException, ModbusException

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo
else:  # pragma: no cover
    try:
        from homeassistant.helpers.device_registry import DeviceInfo
    except (ModuleNotFoundError, ImportError):  # pragma: no cover

        class DeviceInfo:
            """Minimal fallback DeviceInfo for tests.

            Stores provided keyword arguments and exposes an ``as_dict`` method
            similar to Home Assistant's ``DeviceInfo`` dataclass.
            """

            def __init__(self, **kwargs: Any) -> None:
                self._data: dict[str, Any] = dict(kwargs)

            def as_dict(self) -> dict[str, Any]:
                """Return stored fields as a dictionary."""
                return dict(self._data)

            # Provide dictionary-style and attribute-style access for convenience in tests
            def __getitem__(self, key: str) -> Any:  # pragma: no cover - simple mapping
                return self._data[key]

            def __getattr__(self, item: str) -> Any:
                try:
                    return self._data[item]
                except KeyError as exc:  # pragma: no cover - mirror dict behaviour
                    raise AttributeError(item) from exc


from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    COIL_REGISTERS,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DISCRETE_INPUT_REGISTERS,
    DOMAIN,
    KNOWN_MISSING_REGISTERS,
    MANUFACTURER,
    SENSOR_UNAVAILABLE,
    UNKNOWN_MODEL,
)
from .scanner_core import DeviceCapabilities, ThesslaGreenDeviceScanner
from .modbus_client import ThesslaGreenModbusClient
from .modbus_helpers import _call_modbus
from .multipliers import REGISTER_MULTIPLIERS
from .registers import HOLDING_REGISTERS, INPUT_REGISTERS, MULTI_REGISTER_SIZES
from .utils import TIME_REGISTER_PREFIXES, _decode_bcd_time

_LOGGER = logging.getLogger(__name__)

# Map each register belonging to a multi-register block to its starting register
MULTI_REGISTER_STARTS: dict[str, str] = {}
for start, size in MULTI_REGISTER_SIZES.items():
    MULTI_REGISTER_STARTS[start] = start
    base = HOLDING_REGISTERS[start]
    for offset in range(1, size):
        addr = base + offset
        for name, reg_addr in HOLDING_REGISTERS.items():
            if reg_addr == addr:
                MULTI_REGISTER_STARTS[name] = start
                break


class ThesslaGreenModbusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Optimized data coordinator for ThesslaGreen Modbus device."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        name: str,
        scan_interval: timedelta | int = DEFAULT_SCAN_INTERVAL,
        timeout: int = 10,
        retry: int = 3,
        force_full_register_list: bool = False,
        scan_uart_settings: bool = False,
        deep_scan: bool = False,
        entry: ConfigEntry | None = None,
        skip_missing_registers: bool = False,
    ) -> None:
        """Initialize the coordinator."""
        if isinstance(scan_interval, timedelta):
            update_interval = scan_interval
            self.scan_interval = int(scan_interval.total_seconds())
        else:
            update_interval = timedelta(seconds=scan_interval)
            self.scan_interval = int(scan_interval)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id if entry else name}",
            update_interval=update_interval,
        )

        self.host = host
        self.port = port
        self.slave_id = slave_id
        self._device_name = name
        self.timeout = timeout
        self.retry = retry
        self.force_full_register_list = force_full_register_list
        self.scan_uart_settings = scan_uart_settings
        self.deep_scan = deep_scan
        self.entry = entry
        self.skip_missing_registers = skip_missing_registers

        # Connection management
        self.client: ThesslaGreenModbusClient | None = None
        self._connection_lock = asyncio.Lock()
        self._last_successful_read = dt_util.utcnow()

        # Stop listener for Home Assistant shutdown
        self._stop_listener: Callable[[], None] | None = None

        # Device info and capabilities
        self.device_info: dict[str, Any] = {}
        self.capabilities: DeviceCapabilities = DeviceCapabilities()
        self.available_registers: dict[str, set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
            "calculated": {"estimated_power", "total_energy"},
        }
        # Pre-computed reverse register maps for fast lookups
        self._input_registers_rev = {addr: name for name, addr in INPUT_REGISTERS.items()}
        self._holding_registers_rev = {addr: name for name, addr in HOLDING_REGISTERS.items()}
        self._coil_registers_rev = {addr: name for name, addr in COIL_REGISTERS.items()}
        self._discrete_inputs_rev = {addr: name for name, addr in DISCRETE_INPUT_REGISTERS.items()}

        # Optimization: Pre-computed register groups for batch reading
        self._register_groups: dict[str, list[tuple[int, int]]] = {}
        self._consecutive_failures = 0
        self._max_failures = 5

        # Device scan result
        self.device_scan_result: dict[str, Any] | None = None
        self.unknown_registers: dict[str, dict[int, Any]] = {}
        self.scanned_registers: dict[str, int] = {}

        # Statistics and diagnostics
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

        self._last_power_timestamp = dt_util.utcnow()
        self._total_energy = 0.0

    async def _call_modbus(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Wrapper around Modbus calls injecting the slave ID."""
        if not self.client:
            raise ConnectionException("Modbus client is not connected")
        return await _call_modbus(func, self.slave_id, *args, **kwargs)

    async def async_setup(self) -> bool:
        """Set up the coordinator by scanning the device."""
        _LOGGER.info("Setting up ThesslaGreen coordinator for %s:%s", self.host, self.port)

        # Scan device to discover available registers and capabilities
        if not self.force_full_register_list:
            _LOGGER.info("Scanning device for available registers...")
            scanner = None
            try:
                scanner = await ThesslaGreenDeviceScanner.create(
                    host=self.host,
                    port=self.port,
                    slave_id=self.slave_id,
                    timeout=self.timeout,
                    retry=self.retry,
                    scan_uart_settings=self.scan_uart_settings,
                    skip_known_missing=self.skip_missing_registers,
                    deep_scan=self.deep_scan,
                )

                self.device_scan_result = await scanner.scan_device()
                scan_registers = self.device_scan_result.get("available_registers", {})
                self.available_registers = {
                    "input_registers": set(scan_registers.get("input_registers", [])),
                    "holding_registers": set(scan_registers.get("holding_registers", [])),
                    "coil_registers": set(scan_registers.get("coil_registers", [])),
                    "discrete_inputs": set(scan_registers.get("discrete_inputs", [])),
                }
                if self.skip_missing_registers:
                    for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                        self.available_registers[reg_type].difference_update(names)

                self.device_info = self.device_scan_result.get("device_info", {})
                self.device_info.setdefault("device_name", self._device_name)
                self.capabilities = DeviceCapabilities(
                    **self.device_scan_result.get("capabilities", {})
                )
                self.unknown_registers = self.device_scan_result.get("unknown_registers", {})
                self.scanned_registers = self.device_scan_result.get("scanned_registers", {})

                _LOGGER.info(
                    "Device scan completed: %d registers found, model: %s, firmware: %s",
                    self.device_scan_result.get("register_count", 0),
                    self.device_info.get("model", UNKNOWN_MODEL),
                    self.device_info.get("firmware", "Unknown"),
                )
            except asyncio.CancelledError:
                _LOGGER.debug("Device scan cancelled")
                if scanner is not None:
                    await scanner.close()
                    scanner = None
                raise
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.exception("Device scan failed: %s", exc)
                raise
            except (OSError, asyncio.TimeoutError, ValueError) as exc:
                _LOGGER.exception("Unexpected error during device scan: %s", exc)
                raise
            finally:
                if scanner is not None:
                    await scanner.close()
        else:
            _LOGGER.info("Using full register list (skipping scan)")
            # Load all registers if forced
            self._load_full_register_list()

        model = self.device_info.get("model", UNKNOWN_MODEL)
        firmware = self.device_info.get("firmware", "Unknown")
        # Warn when any key identification fields are missing
        if model == UNKNOWN_MODEL or firmware == "Unknown":
            missing: list[str] = []
            if model == "Unknown":
                missing.append("model")
                _LOGGER.debug(
                    "Device model missing for %s:%s%s",
                    self.host,
                    self.port,
                    f" (slave {self.slave_id})" if self.slave_id is not None else "",
                )
            if firmware == "Unknown":
                missing.append("firmware")
                _LOGGER.debug(
                    "Device firmware missing for %s:%s%s",
                    self.host,
                    self.port,
                    f" (slave {self.slave_id})" if self.slave_id is not None else "",
                )
            if missing:
                device_details = f"{self.host}:{self.port}"
                if self.slave_id is not None:
                    device_details += f", slave {self.slave_id}"
                missing_str = " and ".join(missing)
                _LOGGER.warning(
                    "Device %s missing %s (%s). "
                    "Verify Modbus connectivity or ensure your firmware is supported.",
                    self._device_name,
                    missing_str,
                    device_details,
                )

        # Pre-compute register groups for batch reading
        self._compute_register_groups()

        # Test initial connection
        await self._test_connection()

        # Ensure we clean up tasks when Home Assistant stops
        if self._stop_listener is None:
            self._stop_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._async_handle_stop
            )

        return True

    def _load_full_register_list(self) -> None:
        """Load full register list when forced."""
        for reg_type in self.available_registers:
            self.available_registers[reg_type].clear()
        self.available_registers["input_registers"].update(INPUT_REGISTERS.keys())
        self.available_registers["holding_registers"].update(HOLDING_REGISTERS.keys())
        self.available_registers["coil_registers"].update(COIL_REGISTERS.keys())
        self.available_registers["discrete_inputs"].update(DISCRETE_INPUT_REGISTERS.keys())

        if self.skip_missing_registers:
            for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                self.available_registers[reg_type].difference_update(names)

        self.device_info.clear()
        self.device_info.update(
            {
                "device_name": f"{DEFAULT_NAME} {UNKNOWN_MODEL}",
                "model": UNKNOWN_MODEL,
                "firmware": "Unknown",
                "serial_number": "Unknown",
            }
        )

        _LOGGER.info(
            "Loaded full register list: %d total registers",
            sum(len(regs) for regs in self.available_registers.values()),
        )

    def _compute_register_groups(self) -> None:
        """Pre-compute register groups for optimized batch reading."""
        # Group Input Registers
        if self.available_registers["input_registers"]:
            input_addrs = [
                INPUT_REGISTERS[reg] for reg in self.available_registers["input_registers"]
            ]
            self._register_groups["input_registers"] = self._group_registers_for_batch_read(
                sorted(input_addrs)
            )

        # Group Holding Registers
        if self.available_registers["holding_registers"]:
            holding_addrs: list[int] = []
            for reg in self.available_registers["holding_registers"]:
                start = HOLDING_REGISTERS[reg]
                size = MULTI_REGISTER_SIZES.get(reg, 1)
                holding_addrs.extend(range(start, start + size))
            self._register_groups["holding_registers"] = self._group_registers_for_batch_read(
                sorted(set(holding_addrs))
            )

        # Group Coil Registers
        if self.available_registers["coil_registers"]:
            coil_addrs = [COIL_REGISTERS[reg] for reg in self.available_registers["coil_registers"]]
            self._register_groups["coil_registers"] = self._group_registers_for_batch_read(
                sorted(coil_addrs)
            )

        # Group Discrete Input Registers
        if self.available_registers["discrete_inputs"]:
            discrete_addrs = [
                DISCRETE_INPUT_REGISTERS[reg] for reg in self.available_registers["discrete_inputs"]
            ]
            self._register_groups["discrete_inputs"] = self._group_registers_for_batch_read(
                sorted(discrete_addrs)
            )

        _LOGGER.debug(
            "Pre-computed register groups: %s",
            {k: len(v) for k, v in self._register_groups.items()},
        )

    def _group_registers_for_batch_read(
        self, addresses: list[int], max_gap: int = 10, max_batch: int = 16
    ) -> list[tuple[int, int]]:
        """Group consecutive registers for efficient batch reading."""
        if not addresses:
            return []

        groups = []
        current_start = addresses[0]
        current_end = addresses[0]

        for addr in addresses[1:]:
            # If gap is too large or batch too big, start new group
            if (addr - current_end > max_gap) or (current_end - current_start + 1 >= max_batch):
                groups.append((current_start, current_end - current_start + 1))
                current_start = addr
                current_end = addr
            else:
                current_end = addr

        # Add last group
        groups.append((current_start, current_end - current_start + 1))
        return groups

    def _mark_registers_failed(self, names: Iterable[str | None]) -> None:
        """Record registers that failed to read."""
        failed: set[str] = getattr(self, "_failed_registers", set())
        failed.update(name for name in names if name)
        self._failed_registers = failed

    def _clear_register_failure(self, name: str) -> None:
        """Remove register from failed list on successful read."""
        if hasattr(self, "_failed_registers"):
            self._failed_registers.discard(name)

    async def _test_connection(self) -> None:
        """Test initial connection to the device."""
        async with self._connection_lock:
            try:
                await self._ensure_connection()
                client = self.client
                if client is None or not client.connected:
                    raise ConnectionException("Modbus client is not connected")
                # Try to read a basic register to verify communication. "count" must
                # always be passed as a keyword argument to ``_call_modbus`` to avoid
                # issues with keyword-only parameters in pymodbus.
                count = 1
                response = await self._call_modbus(client.read_input_registers, 0x0000, count=count)
                if response is None or response.isError():
                    raise ConnectionException("Cannot read basic register")
                _LOGGER.debug("Connection test successful")
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.exception("Connection test failed: %s", exc)
                raise
            except (OSError, asyncio.TimeoutError) as exc:
                _LOGGER.exception("Unexpected error during connection test: %s", exc)
                raise

    async def _async_setup_client(self) -> bool:
        """Set up the Modbus client if needed.

        Returns True on success, False otherwise.
        """
        try:
            async with self._connection_lock:
                await self._ensure_connection()
            return True
        except (ModbusException, ConnectionException) as exc:
            _LOGGER.exception("Failed to set up Modbus client: %s", exc)
            return False
        except (OSError, asyncio.TimeoutError) as exc:
            _LOGGER.exception("Unexpected error setting up Modbus client: %s", exc)
            return False

    async def _ensure_connection(self) -> None:
        """Ensure Modbus connection is established."""
        if self.client and self.client.connected:
            return
        if self.client is not None:
            await self._disconnect()
        try:
            self.client = ThesslaGreenModbusClient(self.host, self.port, timeout=self.timeout)
            if not await self.client.connect():
                raise ConnectionException(f"Could not connect to {self.host}:{self.port}")
            _LOGGER.debug("Modbus connection established")
        except (ModbusException, ConnectionException) as exc:
            self.statistics["connection_errors"] += 1
            _LOGGER.exception("Failed to establish connection: %s", exc)
            raise
        except (OSError, asyncio.TimeoutError) as exc:
            self.statistics["connection_errors"] += 1
            _LOGGER.exception("Unexpected error establishing connection: %s", exc)
            raise

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device with optimized batch reading."""
        start_time = dt_util.utcnow()

        async with self._connection_lock:
            try:
                await self._ensure_connection()
                client = self.client
                if client is None or not client.connected:
                    raise ConnectionException("Modbus client is not connected")

                # Read all register types
                data = {}

                # Read Input Registers
                input_data = await self._read_input_registers_optimized()
                data.update(input_data)

                # Read Holding Registers
                holding_data = await self._read_holding_registers_optimized()
                data.update(holding_data)

                # Read Coil Registers
                coil_data = await self._read_coil_registers_optimized()
                data.update(coil_data)

                # Read Discrete Inputs
                discrete_data = await self._read_discrete_inputs_optimized()
                data.update(discrete_data)

                # Post-process data (calculate derived values)
                data = self._post_process_data(data)

                if not client.connected:
                    _LOGGER.debug(
                        "Modbus client disconnected during update; attempting reconnection"
                    )
                    await self._ensure_connection()
                    client = self.client
                    if client is None or not client.connected:
                        raise ConnectionException("Modbus client is not connected")

                # Update statistics
                self.statistics["successful_reads"] += 1
                self.statistics["last_successful_update"] = dt_util.utcnow()
                self._consecutive_failures = 0

                # Calculate response time
                response_time = (dt_util.utcnow() - start_time).total_seconds()
                self.statistics["average_response_time"] = (
                    self.statistics["average_response_time"]
                    * (self.statistics["successful_reads"] - 1)
                    + response_time
                ) / self.statistics["successful_reads"]

                _LOGGER.debug(
                    "Data update successful: %d values read in %.2fs", len(data), response_time
                )
                return data

            except (ModbusException, ConnectionException) as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1

                # Disconnect if too many failures
                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    await self._disconnect()

                _LOGGER.error("Failed to update data: %s", exc)
                raise UpdateFailed(f"Error communicating with device: {exc}") from exc
            except (OSError, asyncio.TimeoutError, ValueError) as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    await self._disconnect()

                _LOGGER.error("Unexpected error during data update: %s", exc)
                raise UpdateFailed(f"Unexpected error: {exc}") from exc

    async def _read_input_registers_optimized(self) -> dict[str, Any]:
        """Read input registers using optimized batch reading."""
        data: dict[str, Any] = {}

        if "input_registers" not in self._register_groups:
            return data

        client = self.client
        if client is None or not client.connected:
            raise ConnectionException("Modbus client is not connected")

        failed: set[str] = getattr(self, "_failed_registers", set())

        for start_addr, count in self._register_groups["input_registers"]:
            register_names = [
                self._find_register_name(INPUT_REGISTERS, start_addr + i) for i in range(count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            try:
                # Pass "count" as a keyword argument to ensure compatibility with
                # Modbus helpers that expect keyword-only parameters.
                response = await self._call_modbus(
                    client.read_input_registers,
                    start_addr,
                    count=count,
                )
                if response is None or response.isError():
                    _LOGGER.debug(
                        "Failed to read input registers at 0x%04X", start_addr, exc_info=True
                    )
                    self._mark_registers_failed(register_names)
                    continue

                # Process each register in the batch
                for i, value in enumerate(response.registers):
                    addr = start_addr + i
                    register_name = self._find_register_name(INPUT_REGISTERS, addr)
                    if (
                        register_name
                        and register_name in self.available_registers["input_registers"]
                    ):
                        processed_value = self._process_register_value(register_name, value)
                        if processed_value is not None:
                            data[register_name] = processed_value
                            self.statistics["total_registers_read"] += 1
                            self._clear_register_failure(register_name)

                if len(response.registers) < count:
                    missing = register_names[len(response.registers) :]  # noqa: E203
                    self._mark_registers_failed(missing)

            except (ModbusException, ConnectionException):
                self._mark_registers_failed(register_names)
                _LOGGER.debug("Error reading input registers at 0x%04X", start_addr, exc_info=True)
                continue
            except (OSError, asyncio.TimeoutError, ValueError):
                self._mark_registers_failed(register_names)
                _LOGGER.error(
                    "Unexpected error reading input registers at 0x%04X",
                    start_addr,
                    exc_info=True,
                )
                continue

        return data

    async def _read_holding_registers_optimized(self) -> dict[str, Any]:
        """Read holding registers using optimized batch reading."""
        data: dict[str, Any] = {}

        if "holding_registers" not in self._register_groups:
            return data

        client = self.client
        if client is None or not client.connected:
            _LOGGER.debug("Modbus client not available; skipping holding register read")
            return data

        failed: set[str] = getattr(self, "_failed_registers", set())

        for start_addr, count in self._register_groups["holding_registers"]:
            register_names = [
                self._find_register_name(HOLDING_REGISTERS, start_addr + i) for i in range(count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            try:
                # Pass "count" as a keyword argument to ensure compatibility with
                # Modbus helpers that expect keyword-only parameters.
                response = await self._call_modbus(
                    client.read_holding_registers,
                    start_addr,
                    count=count,
                )
                if response is None or response.isError():
                    _LOGGER.debug(
                        "Failed to read holding registers at 0x%04X", start_addr, exc_info=True
                    )
                    self._mark_registers_failed(register_names)
                    continue

                # Process each register in the batch
                for i, value in enumerate(response.registers):
                    addr = start_addr + i
                    register_name = self._find_register_name(HOLDING_REGISTERS, addr)
                    if register_name in MULTI_REGISTER_SIZES:
                        size = MULTI_REGISTER_SIZES[register_name]
                        values = response.registers[i : i + size]  # noqa: E203
                        if (
                            len(values) == size
                            and register_name in self.available_registers["holding_registers"]
                        ):
                            data[register_name] = values
                            self.statistics["total_registers_read"] += size
                            self._clear_register_failure(register_name)
                        continue
                    if (
                        register_name
                        and register_name in self.available_registers["holding_registers"]
                    ):
                        processed_value = self._process_register_value(register_name, value)
                        if processed_value is not None:
                            data[register_name] = processed_value
                            self.statistics["total_registers_read"] += 1
                            self._clear_register_failure(register_name)

                if len(response.registers) < count:
                    missing = register_names[len(response.registers) :]  # noqa: E203
                    self._mark_registers_failed(missing)

            except (ModbusException, ConnectionException):
                self._mark_registers_failed(register_names)
                _LOGGER.debug(
                    "Error reading holding registers at 0x%04X", start_addr, exc_info=True
                )
                continue
            except (OSError, asyncio.TimeoutError, ValueError):
                self._mark_registers_failed(register_names)
                _LOGGER.error(
                    "Unexpected error reading holding registers at 0x%04X",
                    start_addr,
                    exc_info=True,
                )
                continue

        return data

    async def _read_coil_registers_optimized(self) -> dict[str, Any]:
        """Read coil registers using optimized batch reading."""
        data: dict[str, Any] = {}

        if "coil_registers" not in self._register_groups:
            return data

        client = self.client
        if client is None or not client.connected:
            raise ConnectionException("Modbus client is not connected")

        failed: set[str] = getattr(self, "_failed_registers", set())

        for start_addr, count in self._register_groups["coil_registers"]:
            register_names = [
                self._find_register_name(COIL_REGISTERS, start_addr + i) for i in range(count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            try:
                # Pass "count" as a keyword argument to ensure compatibility with
                # Modbus helpers that expect keyword-only parameters.
                response = await self._call_modbus(
                    client.read_coils,
                    start_addr,
                    count=count,
                )
                if response is None or response.isError():
                    _LOGGER.debug(
                        "Failed to read coil registers at 0x%04X", start_addr, exc_info=True
                    )
                    self._mark_registers_failed(register_names)
                    continue

                if not response.bits:
                    if response.bits is None:
                        _LOGGER.error(
                            "No bits returned reading coil registers at 0x%04X",
                            start_addr,
                        )
                    self._mark_registers_failed(register_names)
                    continue

                # Process each bit in the batch
                for i in range(min(count, len(response.bits))):
                    addr = start_addr + i
                    register_name = self._find_register_name(COIL_REGISTERS, addr)
                    if (
                        register_name
                        and register_name in self.available_registers["coil_registers"]
                    ):
                        data[register_name] = response.bits[i]
                        self.statistics["total_registers_read"] += 1
                        self._clear_register_failure(register_name)

                if len(response.bits) < count:
                    missing = register_names[len(response.bits) :]  # noqa: E203
                    self._mark_registers_failed(missing)

            except (ModbusException, ConnectionException):
                self._mark_registers_failed(register_names)
                _LOGGER.debug("Error reading coil registers at 0x%04X", start_addr, exc_info=True)
                continue
            except (OSError, asyncio.TimeoutError, ValueError):
                self._mark_registers_failed(register_names)
                _LOGGER.error(
                    "Unexpected error reading coil registers at 0x%04X",
                    start_addr,
                    exc_info=True,
                )
                continue

        return data

    async def _read_discrete_inputs_optimized(self) -> dict[str, Any]:
        """Read discrete input registers using optimized batch reading."""
        data: dict[str, Any] = {}

        if "discrete_inputs" not in self._register_groups:
            return data

        client = self.client
        if client is None or not client.connected:
            raise ConnectionException("Modbus client is not connected")

        failed: set[str] = getattr(self, "_failed_registers", set())

        for start_addr, count in self._register_groups["discrete_inputs"]:
            register_names = [
                self._find_register_name(DISCRETE_INPUT_REGISTERS, start_addr + i)
                for i in range(count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            try:
                # Pass "count" as a keyword argument to ensure compatibility with
                # Modbus helpers that expect keyword-only parameters.
                response = await self._call_modbus(
                    client.read_discrete_inputs,
                    start_addr,
                    count=count,
                )
                if response is None or response.isError():
                    _LOGGER.debug(
                        "Failed to read discrete inputs at 0x%04X", start_addr, exc_info=True
                    )
                    self._mark_registers_failed(register_names)
                    continue

                if not response.bits:
                    if response.bits is None:
                        _LOGGER.error(
                            "No bits returned reading discrete inputs at 0x%04X",
                            start_addr,
                        )
                    self._mark_registers_failed(register_names)
                    continue

                # Process each bit in the batch
                for i in range(min(count, len(response.bits))):
                    addr = start_addr + i
                    register_name = self._find_register_name(DISCRETE_INPUT_REGISTERS, addr)
                    if (
                        register_name
                        and register_name in self.available_registers["discrete_inputs"]
                    ):
                        data[register_name] = response.bits[i]
                        self.statistics["total_registers_read"] += 1
                        self._clear_register_failure(register_name)

                if len(response.bits) < count:
                    missing = register_names[len(response.bits) :]  # noqa: E203
                    self._mark_registers_failed(missing)

            except (ModbusException, ConnectionException):
                self._mark_registers_failed(register_names)
                _LOGGER.debug("Error reading discrete inputs at 0x%04X", start_addr, exc_info=True)
                continue
            except (OSError, asyncio.TimeoutError, ValueError):
                self._mark_registers_failed(register_names)
                _LOGGER.error(
                    "Unexpected error reading discrete inputs at 0x%04X",
                    start_addr,
                    exc_info=True,
                )
                continue

        return data

    def _find_register_name(self, register_map: dict[str, int], address: int) -> str | None:
        """Find register name by address using pre-built reverse maps."""
        if register_map is INPUT_REGISTERS:
            return self._input_registers_rev.get(address)
        if register_map is HOLDING_REGISTERS:
            return self._holding_registers_rev.get(address)
        if register_map is COIL_REGISTERS:
            return self._coil_registers_rev.get(address)
        if register_map is DISCRETE_INPUT_REGISTERS:
            return self._discrete_inputs_rev.get(address)
        return None

    def _process_register_value(self, register_name: str, value: int) -> Any:
        """Process register value according to its type and multiplier."""
        # Check for sensor error values
        if value == SENSOR_UNAVAILABLE and "temperature" in register_name.lower():
            return None  # No sensor
        if value == SENSOR_UNAVAILABLE and "flow" in register_name.lower():
            return None  # No sensor

        if register_name.startswith(TIME_REGISTER_PREFIXES):
            decoded = _decode_bcd_time(value)
            return decoded if decoded is not None else value

        # Apply multiplier
        if register_name in REGISTER_MULTIPLIERS:
            return value * REGISTER_MULTIPLIERS[register_name]

        return value

    def calculate_power_consumption(self, data: dict[str, Any]) -> float | None:
        """Estimate power usage from DAC output voltages."""
        try:
            supply = float(data["dac_supply"])
            exhaust = float(data["dac_exhaust"])
        except (KeyError, TypeError, ValueError):
            return None

        heater = float(data.get("dac_heater", 0) or 0)
        cooler = float(data.get("dac_cooler", 0) or 0)

        def _power(voltage: float, max_power: float) -> float:
            voltage = max(0.0, min(10.0, voltage))
            return (voltage / 10) ** 3 * max_power

        fan_max = 80.0
        heater_max = 2000.0
        cooler_max = 1000.0

        power = _power(supply, fan_max) + _power(exhaust, fan_max)
        if heater:
            power += _power(heater, heater_max)
        if cooler:
            power += _power(cooler, cooler_max)

        return power

    def _post_process_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Post-process data to calculate derived values."""
        # Calculate heat recovery efficiency if temperatures available
        if all(
            k in data for k in ["outside_temperature", "supply_temperature", "exhaust_temperature"]
        ):
            try:
                outside = data["outside_temperature"]
                supply = data["supply_temperature"]
                exhaust = data["exhaust_temperature"]

                if exhaust != outside:
                    efficiency = ((supply - outside) / (exhaust - outside)) * 100
                    data["calculated_efficiency"] = max(0, min(100, efficiency))
            except (ZeroDivisionError, TypeError) as exc:
                _LOGGER.debug("Could not calculate efficiency: %s", exc)

        # Calculate flow balance
        if "supply_flow_rate" in data and "exhaust_flow_rate" in data:
            data["flow_balance"] = data["supply_flow_rate"] - data["exhaust_flow_rate"]
            data["flow_balance_status"] = (
                "balanced"
                if abs(data["flow_balance"]) < 10
                else "supply_dominant" if data["flow_balance"] > 0 else "exhaust_dominant"
            )
        power = self.calculate_power_consumption(data)
        if power is not None:
            data["estimated_power"] = power
            now = dt_util.utcnow()
            elapsed = (now - self._last_power_timestamp).total_seconds()
            self._total_energy += power * elapsed / 3600000.0
            data["total_energy"] = self._total_energy
            self._last_power_timestamp = now

        return data

    async def async_write_register(
        self,
        register_name: str,
        value: float | list[int] | tuple[int, ...],
        refresh: bool = True,
    ) -> bool:
        """Write to a holding or coil register.

        Values should be provided in user units (°C, minutes, etc.). The value
        will be scaled according to ``REGISTER_MULTIPLIERS`` before being
        written to the device.

        If ``refresh`` is ``True`` (default), the coordinator will request a data
        refresh after the write. Set to ``False`` when performing multiple writes
        in sequence and manually refresh at the end.
        """
        refresh_after_write = False
        async with self._connection_lock:
            try:
                await self._ensure_connection()
                if not self.client:
                    raise ConnectionException("Modbus client is not connected")

                original_value = value
                start_register = MULTI_REGISTER_STARTS.get(register_name)

                if isinstance(value, (list, tuple)):
                    if start_register is None:
                        _LOGGER.error(
                            "Register %s does not support multi-register writes",
                            register_name,
                        )
                        return False
                    if start_register != register_name:
                        _LOGGER.error(
                            "Multi-register writes must start at %s",
                            start_register,
                        )
                        return False
                    assert start_register is not None
                    if len(value) != MULTI_REGISTER_SIZES[start_register]:
                        _LOGGER.error(
                            "Register %s expects %d values",
                            start_register,
                            MULTI_REGISTER_SIZES[register_name],
                        )
                        return False

                if register_name in MULTI_REGISTER_SIZES:
                    if (
                        not isinstance(value, (list, tuple))
                        or len(value) != MULTI_REGISTER_SIZES[register_name]
                    ):
                        _LOGGER.error(
                            "Register %s expects %d values",
                            register_name,
                            MULTI_REGISTER_SIZES[register_name],
                        )
                        return False
                    values = [int(v) for v in value]
                else:
                    if isinstance(value, (list, tuple)):
                        _LOGGER.error("Register %s expects a single numeric value", register_name)
                        return False
                    # Apply multiplier if defined and convert to integer for Modbus
                    if register_name in REGISTER_MULTIPLIERS:
                        multiplier = REGISTER_MULTIPLIERS[register_name]
                        value = int(round(float(value) / multiplier))
                    else:
                        value = int(round(float(value)))

                # Determine register type and address
                if register_name in HOLDING_REGISTERS:
                    address = HOLDING_REGISTERS[register_name]
                    if register_name in MULTI_REGISTER_SIZES:
                        response = await self._call_modbus(
                            self.client.write_registers,
                            address=address,
                            values=values,
                        )
                    else:
                        response = await self._call_modbus(
                            self.client.write_register,
                            address=address,
                            value=value,
                        )
                elif register_name in COIL_REGISTERS:
                    address = COIL_REGISTERS[register_name]
                    response = await self._call_modbus(
                        self.client.write_coil,
                        address=address,
                        value=bool(value),
                    )
                else:
                    _LOGGER.error("Unknown register for writing: %s", register_name)
                    return False

                if response is None or response.isError():
                    _LOGGER.error("Error writing to register %s: %s", register_name, response)
                    return False

                _LOGGER.info("Successfully wrote %s to register %s", original_value, register_name)

                refresh_after_write = refresh
            except (ModbusException, ConnectionException):
                _LOGGER.exception("Failed to write register %s", register_name)
                return False
            except (OSError, asyncio.TimeoutError, ValueError):
                _LOGGER.exception("Unexpected error writing register %s", register_name)
                return False

        if refresh_after_write:
            await self.async_request_refresh()
        return True

    async def _disconnect(self) -> None:
        """Disconnect from Modbus device."""
        if self.client is not None:
            try:
                close = self.client.close
                if inspect.iscoroutinefunction(close):
                    await close()
                else:
                    close()
            except (ModbusException, ConnectionException):
                _LOGGER.debug("Error disconnecting", exc_info=True)
            except OSError:
                _LOGGER.exception("Unexpected error disconnecting")

        self.client = None
        _LOGGER.debug("Disconnected from Modbus device")

    async def _async_handle_stop(self, _event: Any) -> None:
        """Handle Home Assistant stop to cancel tasks."""
        await self.async_shutdown()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
        if self._stop_listener is not None:
            self._stop_listener()
            self._stop_listener = None
        shutdown = getattr(super(), "async_shutdown", None)
        if shutdown is not None:
            await shutdown()
        await self._disconnect()

    @property
    def performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return {
            "total_reads": self.statistics["successful_reads"],
            "failed_reads": self.statistics["failed_reads"],
            "success_rate": (
                self.statistics["successful_reads"]
                / max(1, self.statistics["successful_reads"] + self.statistics["failed_reads"])
            )
            * 100,
            "avg_response_time": self.statistics["average_response_time"],
            "connection_errors": self.statistics["connection_errors"],
            "last_error": self.statistics["last_error"],
            "registers_available": sum(len(regs) for regs in self.available_registers.values()),
            "registers_read": self.statistics["total_registers_read"],
        }

    def get_diagnostic_data(self) -> dict[str, Any]:
        """Return diagnostic information for Home Assistant."""
        last_update = self.statistics.get("last_successful_update")
        connection = {
            "host": self.host,
            "port": self.port,
            "slave_id": self.slave_id,
            "connected": bool(self.client and getattr(self.client, "connected", False)),
            "last_successful_update": last_update.isoformat() if last_update else None,
        }

        statistics = self.statistics.copy()
        if statistics.get("last_successful_update"):
            statistics["last_successful_update"] = statistics["last_successful_update"].isoformat()

        diagnostics: dict[str, Any] = {
            "connection": connection,
            "statistics": statistics,
            "performance": self.performance_stats,
            "device_info": self.device_info,
            "available_registers": {
                key: sorted(list(value)) for key, value in self.available_registers.items()
            },
            "capabilities": (
                self.capabilities.as_dict() if hasattr(self.capabilities, "as_dict") else {}
            ),
            "scan_result": self.device_scan_result,
            "unknown_registers": self.unknown_registers,
            "scanned_registers": self.scanned_registers,
        }

        if self.device_scan_result and "raw_registers" in self.device_scan_result:
            diagnostics["raw_registers"] = self.device_scan_result["raw_registers"]
            if "total_addresses_scanned" in self.device_scan_result:
                statistics["total_addresses_scanned"] = self.device_scan_result[
                    "total_addresses_scanned"
                ]

        return diagnostics

    def get_device_info(self) -> DeviceInfo:
        """Return a ``DeviceInfo`` object for the connected unit.

        The data is used by Home Assistant to uniquely identify the device
        and to group all entities originating from it in the device registry.
        """

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.host}:{self.port}:{self.slave_id}")},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=self.device_info.get("model", UNKNOWN_MODEL),
            sw_version=self.device_info.get("firmware", "Unknown"),
            configuration_url=f"http://{self.host}",
        )

    @property
    def device_name(self) -> str:
        """Return the configured or detected device name."""
        return cast(str, self.device_info.get("device_name") or self._device_name)

    @property
    def device_info_dict(self) -> dict[str, Any]:
        """Return device information as a plain dictionary for legacy use."""
        return cast(dict[str, Any], self.get_device_info().as_dict())
