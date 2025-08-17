"""Data update coordinator for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta

from typing import Any, Dict, List, Optional, Set, Tuple

from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

try:  # pragma: no cover - used in runtime environments only
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP
except (ModuleNotFoundError, ImportError):  # pragma: no cover - test fallback
    EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"  # type: ignore[assignment]

from .modbus_exceptions import ConnectionException, ModbusException

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from pymodbus.client import AsyncModbusTcpClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

try:  # pragma: no cover
    from homeassistant.helpers.device_registry import DeviceInfo
except (ModuleNotFoundError, ImportError):  # pragma: no cover

    class DeviceInfo:  # type: ignore[misc]
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


from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    COIL_REGISTERS,
    DEFAULT_SCAN_INTERVAL,
    DISCRETE_INPUT_REGISTERS,
    DOMAIN,
    KNOWN_MISSING_REGISTERS,
    MANUFACTURER,
    MODEL,
    SENSOR_UNAVAILABLE,
)
from .modbus_client import ThesslaGreenModbusClient
from .modbus_exceptions import ConnectionException, ModbusException
from .modbus_helpers import _call_modbus
from .multipliers import REGISTER_MULTIPLIERS
from .registers import HOLDING_REGISTERS, INPUT_REGISTERS

_LOGGER = logging.getLogger(__name__)

# Registers that should be interpreted as signed int16
SIGNED_REGISTERS: Set[str] = {
    "outside_temperature",
    "supply_temperature",
    "exhaust_temperature",
    "fpx_temperature",
    "duct_supply_temperature",
    "gwc_temperature",
    "ambient_temperature",
    "heating_temperature",
    "supply_flow_rate",
    "exhaust_flow_rate",
}


# DAC registers that output voltage (0-10V scaled from 0-4095)
DAC_REGISTERS: Set[str] = {
    "dac_supply",
    "dac_exhaust",
    "dac_heater",
    "dac_cooler",
}


def _to_signed_int16(value: int) -> int:
    """Convert unsigned int16 to signed int16."""
    if value > 0x7FFF:
        return value - 0x10000
    return value

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



class ThesslaGreenModbusCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator handling all communication with the ThesslaGreen device."""

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

        force_full_register_list: bool | None = False,
        entry: ConfigEntry | None = None,

        force_full_register_list: bool = False,
        scan_uart_settings: bool = False,
        entry: Any | None = None,
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

        self.hass = hass
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.name = name
        self.timeout = timeout
        self.retry = retry
        self.force_full_register_list = force_full_register_list
        self.scan_uart_settings = scan_uart_settings
        self.entry = entry
        self.skip_missing_registers = skip_missing_registers


        self.client: ThesslaGreenModbusClient | None = None
        self.available_registers: Dict[str, Set[str]] = {

        # Connection management
        self.client: "AsyncModbusTcpClient" | None = None
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
        }
        self._register_groups: Dict[str, List[Tuple[int, int]]] = {}
        self._connection_lock = asyncio.Lock()
        self.statistics: Dict[str, Any] = {"total_registers_read": 0}
        self._failed_registers: Set[Tuple[str, int]] = set()
        self._last_successful_read: Optional[str] = None
        self.device_info: Dict[str, Any] | None = None
        self.capabilities: Dict[str, Any] | None = None

        # Reverse lookup dictionaries for fast address -> name resolution
        self._input_registers_rev = {addr: name for name, addr in INPUT_REGISTERS.items()}
        self._holding_registers_rev = {addr: name for name, addr in HOLDING_REGISTERS.items()}
        self._coil_registers_rev = {addr: name for name, addr in COIL_REGISTERS.items()}
        self._discrete_inputs_rev = {addr: name for name, addr in DISCRETE_INPUT_REGISTERS.items()}

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------
    async def _ensure_connection(self) -> None:
        """Ensure the Modbus client is connected."""
        if self.client and getattr(self.client, "connected", False):
            return
        async with self._connection_lock:
            if self.client and getattr(self.client, "connected", False):
                return
            self.client = ThesslaGreenModbusClient(self.host, self.port, timeout=self.timeout)
            if not await self.client.connect():
                raise ConnectionException("Failed to connect to device")

        # Optimization: Pre-computed register groups for batch reading
        self._register_groups: dict[str, list[tuple[int, int]]] = {}
        self._failed_registers: set[str] = set()
        self._consecutive_failures = 0
        self._max_failures = 5

        # Device scan result
        self.device_scan_result: dict[str, Any] | None = None

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

    async def _call_modbus(self, func, *args, **kwargs):
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
                )

                self.device_scan_result = await scanner.scan_device()
                self.available_registers = self.device_scan_result.get("available_registers", {})
                if self.skip_missing_registers:
                    for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                        self.available_registers.get(reg_type, set()).difference_update(names)
                self.device_info = self.device_scan_result.get("device_info", {})
                self.capabilities = DeviceCapabilities(
                    **self.device_scan_result.get("capabilities", {})
                )

                _LOGGER.info(
                    "Device scan completed: %d registers found, model: %s, firmware: %s",
                    self.device_scan_result.get("register_count", 0),
                    self.device_info.get("model", "Unknown"),
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
        self.available_registers = {
            "input_registers": set(INPUT_REGISTERS.keys()),
            "holding_registers": set(HOLDING_REGISTERS.keys()),
            "coil_registers": set(COIL_REGISTERS.keys()),
            "discrete_inputs": set(DISCRETE_INPUT_REGISTERS.keys()),
        }

        if self.skip_missing_registers:
            for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                self.available_registers[reg_type].difference_update(names)

        self.device_info = {
            "device_name": f"ThesslaGreen {MODEL}",
            "model": MODEL,
            "firmware": "Unknown",
            "serial_number": "Unknown",
        }

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


    async def _disconnect(self) -> None:
        """Close the Modbus connection."""
        async with self._connection_lock:
            if self.client:
                await self.client.close()
                self.client = None

    async def async_shutdown(self) -> None:
        """Public method used by integration teardown."""
        await self._disconnect()

    # ------------------------------------------------------------------
    # Register grouping helpers
    # ------------------------------------------------------------------
    def _group_registers_for_batch_read(

        self, register_addresses: List[int], max_gap: int = 1
    ) -> List[Tuple[int, int]]:
        """Group addresses into batches allowing a gap up to ``max_gap``."""
        if not register_addresses:

        self, addresses: list[int], max_gap: int = 10, max_batch: int = 16
    ) -> list[tuple[int, int]]:
        """Group consecutive registers for efficient batch reading."""
        if not addresses:

            return []
        sorted_addrs = sorted(register_addresses)
        groups: List[Tuple[int, int]] = []
        start = last = sorted_addrs[0]
        for addr in sorted_addrs[1:]:
            if addr - last > max_gap:
                groups.append((start, last - start + 1))
                start = addr
            last = addr
        groups.append((start, last - start + 1))
        return groups

    def _create_consecutive_groups(
        self, registers: Dict[str, int]
    ) -> List[Tuple[int, int, Dict[int, str]]]:
        """Create groups of consecutive registers."""
        if not registers:
            return []
        items = sorted(registers.items(), key=lambda item: item[1])
        groups: List[Tuple[int, int, Dict[int, str]]] = []
        start_addr = items[0][1]
        current_map: Dict[int, str] = {items[0][1]: items[0][0]}
        last_addr = start_addr
        for name, addr in items[1:]:
            if addr != last_addr + 1:
                groups.append((start_addr, last_addr - start_addr + 1, current_map))
                start_addr = addr
                current_map = {addr: name}
            else:
                current_map[addr] = name
            last_addr = addr
        groups.append((start_addr, last_addr - start_addr + 1, current_map))
        return groups


    def _precompute_register_groups(self) -> None:
        """Pre-compute register groups for efficient batch reading."""
        if not self.available_registers:
            return
        self._register_groups = {}
        for reg_type, source_map in {
            "input_registers": INPUT_REGISTERS,
            "holding_registers": HOLDING_REGISTERS,
            "coil_registers": COIL_REGISTERS,
            "discrete_inputs": DISCRETE_INPUT_REGISTERS,
        }.items():
            allowed = self.available_registers.get(reg_type, set())
            selected = {name: addr for name, addr in source_map.items() if name in allowed}
            groups = [
                (start, count) for start, count, _ in self._create_consecutive_groups(selected)
            ]
            if groups:
                self._register_groups[reg_type] = groups

    # ------------------------------------------------------------------
    # Register helpers
    # ------------------------------------------------------------------
    def _find_register_name(self, register_map: Dict[str, int], addr: int) -> Optional[str]:
        """Return register name for ``addr`` using precomputed reverse maps."""
        if register_map is INPUT_REGISTERS:
            return self._input_registers_rev.get(addr)
        if register_map is HOLDING_REGISTERS:
            return self._holding_registers_rev.get(addr)
        if register_map is COIL_REGISTERS:
            return self._coil_registers_rev.get(addr)
        if register_map is DISCRETE_INPUT_REGISTERS:
            return self._discrete_inputs_rev.get(addr)
        for name, address in register_map.items():
            if address == addr:
                return name
        return None

    async def _test_connection(self) -> None:
        """Test initial connection to the device."""
        async with self._connection_lock:
            try:
                await self._ensure_connection()
                if self.client is None or not self.client.connected:
                    _LOGGER.debug("Modbus client missing; attempting reconnection")
                    await self._ensure_connection()
                if self.client is None or not self.client.connected:
                    raise ConnectionException("Modbus client is not connected")
                # Try to read a basic register to verify communication. "count" must
                # always be passed as a keyword argument to ``_call_modbus`` to avoid
                # issues with keyword-only parameters in pymodbus.
                count = 1
                response = await self._call_modbus(
                    self.client.read_input_registers,
                    0x0000,
                    count=count,
                )
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
            await self._ensure_connection()
            return True
        except (ModbusException, ConnectionException) as exc:
            _LOGGER.exception("Failed to set up Modbus client: %s", exc)
            return False
        except (OSError, asyncio.TimeoutError) as exc:
            _LOGGER.exception("Unexpected error setting up Modbus client: %s", exc)
            return False

    async def async_ensure_client(self) -> bool:
        """Public wrapper ensuring the Modbus client is connected."""
        return await self._async_setup_client()

    async def _ensure_connection(self) -> None:
        """Ensure Modbus connection is established."""
        if self.client is None or not self.client.connected:
            if self.client is not None:
                await self._disconnect()
            try:
                from pymodbus.client import AsyncModbusTcpClient

                self.client = AsyncModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout,
                )
                connected = await self.client.connect()
                if not connected:
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


    # ------------------------------------------------------------------
    # Reading helpers
    # ------------------------------------------------------------------
    async def _read_with_retry(
        self,
        func,
        start_addr: int,
        count: int,
        reg_type: str,
    ) -> Any:
        """Call a Modbus read function with retry logic."""
        for attempt in range(1, self.retry + 1):
            try:

                response = await _call_modbus(func, self.slave_id, address=start_addr, count=count)
                if response is None or getattr(response, "isError", lambda: True)():
                    raise ModbusException("Invalid response")
                return response
            except Exception as exc:  # pragma: no cover - debug log only

                await self._ensure_connection()
                if self.client is None or not self.client.connected:
                    _LOGGER.debug("Modbus client missing; attempting reconnection")
                    await self._ensure_connection()
                if self.client is None or not self.client.connected:
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

                if self.client is None or not self.client.connected:
                    _LOGGER.debug(
                        "Modbus client disconnected during update; attempting reconnection"
                    )
                    await self._ensure_connection()
                    if self.client is None or not self.client.connected:
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
                    "Attempt %d/%d failed for %s @0x%04X: %s",
                    attempt,
                    self.retry,
                    reg_type,
                    start_addr,
                    exc,
                )
                await asyncio.sleep(0)
        self._failed_registers.add((reg_type, start_addr))
        return None


    async def _read_input_registers_optimized(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if "input_registers" not in self._register_groups:
            return data
        if self.client is None:
            await self._ensure_connection()
        for start_addr, count in self._register_groups["input_registers"]:
            response = await self._read_with_retry(
                self.client.read_input_registers, start_addr, count, "input"
            )
            if response is None:

    async def _read_input_registers_optimized(self) -> dict[str, Any]:
        """Read input registers using optimized batch reading."""
        data = {}

        if "input_registers" not in self._register_groups:
            return data

        if not self.client:
            await self._ensure_connection()
        client = self.client
        if client is None or not client.connected:
            raise ConnectionException("Modbus client is not connected")

        for start_addr, count in self._register_groups["input_registers"]:
            try:
                # Pass "count" as a keyword argument to ensure compatibility with
                # Modbus helpers that expect keyword-only parameters.
                response = await self._call_modbus(
                    client.read_input_registers,
                    start_addr,
                    count=count,
                )
                if response is None:
                    _LOGGER.error(
                        "No response reading input registers at 0x%04X",
                        start_addr,
                    )
                    continue
                if response.isError():
                    _LOGGER.debug(
                        "Failed to read input registers at 0x%04X: %s", start_addr, response
                    )
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

            except (ModbusException, ConnectionException):
                _LOGGER.debug("Error reading input registers at 0x%04X", start_addr, exc_info=True)
                continue
            except (OSError, asyncio.TimeoutError, ValueError):
                _LOGGER.error(
                    "Unexpected error reading input registers at 0x%04X",
                    start_addr,
                    exc_info=True,
                )

                continue
            for i, value in enumerate(response.registers):
                addr = start_addr + i
                name = self._find_register_name(INPUT_REGISTERS, addr)
                if name and name in self.available_registers["input_registers"]:
                    processed = self._process_register_value(name, value)
                    if processed is not None:
                        data[name] = processed
                        self.statistics["total_registers_read"] += 1
        return data


    async def _read_holding_registers_optimized(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if "holding_registers" not in self._register_groups:
            return data
        if self.client is None:
            await self._ensure_connection()
        for start_addr, count in self._register_groups["holding_registers"]:
            response = await self._read_with_retry(
                self.client.read_holding_registers, start_addr, count, "holding"
            )
            if response is None:

    async def _read_holding_registers_optimized(self) -> dict[str, Any]:
        """Read holding registers using optimized batch reading."""
        data = {}

        if self.client is None:
            _LOGGER.debug("Modbus client not available; skipping holding register read")
            return {}

        if "holding_registers" not in self._register_groups:
            return data

        client = self.client
        if client is None or not client.connected:
            _LOGGER.debug("Modbus client is not connected")
            return data

        for start_addr, count in self._register_groups["holding_registers"]:
            try:
                # Pass "count" as a keyword argument to ensure compatibility with
                # Modbus helpers that expect keyword-only parameters.
                response = await self._call_modbus(
                    client.read_holding_registers,
                    start_addr,
                    count=count,
                )
                if response is None:
                    _LOGGER.error(
                        "No response reading holding registers at 0x%04X",
                        start_addr,
                    )
                    continue
                if response.isError():
                    _LOGGER.debug(
                        "Failed to read holding registers at 0x%04X: %s", start_addr, response
                    )
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
                        continue
                    if (
                        register_name
                        and register_name in self.available_registers["holding_registers"]
                    ):
                        processed_value = self._process_register_value(register_name, value)
                        if processed_value is not None:
                            data[register_name] = processed_value
                            self.statistics["total_registers_read"] += 1

            except (ModbusException, ConnectionException):
                _LOGGER.debug(
                    "Error reading holding registers at 0x%04X", start_addr, exc_info=True
                )
                continue
            except (OSError, asyncio.TimeoutError, ValueError):
                _LOGGER.error(
                    "Unexpected error reading holding registers at 0x%04X",
                    start_addr,
                    exc_info=True,
                )

                continue
            for i, value in enumerate(response.registers):
                addr = start_addr + i
                name = self._find_register_name(HOLDING_REGISTERS, addr)
                if name and name in self.available_registers["holding_registers"]:
                    processed = self._process_register_value(name, value)
                    if processed is not None:
                        data[name] = processed
                        self.statistics["total_registers_read"] += 1
        return data


    async def _read_coil_registers_optimized(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if "coil_registers" not in self._register_groups:
            return data
        if self.client is None:
            await self._ensure_connection()
        for start_addr, count in self._register_groups["coil_registers"]:
            response = await self._read_with_retry(
                self.client.read_coils, start_addr, count, "coil"
            )
            if response is None:

    async def _read_coil_registers_optimized(self) -> dict[str, Any]:
        """Read coil registers using optimized batch reading."""
        data = {}

        if "coil_registers" not in self._register_groups:
            return data

        if not self.client:
            await self._ensure_connection()
        client = self.client
        if client is None or not client.connected:
            raise ConnectionException("Modbus client is not connected")

        for start_addr, count in self._register_groups["coil_registers"]:
            try:
                # Pass "count" as a keyword argument to ensure compatibility with
                # Modbus helpers that expect keyword-only parameters.
                response = await self._call_modbus(
                    client.read_coils,
                    start_addr,
                    count=count,
                )
                if response is None:
                    _LOGGER.error(
                        "No response reading coil registers at 0x%04X",
                        start_addr,
                    )
                    continue
                if response.isError():
                    _LOGGER.debug(
                        "Failed to read coil registers at 0x%04X: %s", start_addr, response
                    )
                    continue

                if not response.bits:
                    if response.bits is None:
                        _LOGGER.error(
                            "No bits returned reading coil registers at 0x%04X",
                            start_addr,
                        )
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

            except (ModbusException, ConnectionException):
                _LOGGER.debug("Error reading coil registers at 0x%04X", start_addr, exc_info=True)
                continue
            except (OSError, asyncio.TimeoutError, ValueError):
                _LOGGER.error(
                    "Unexpected error reading coil registers at 0x%04X",
                    start_addr,
                    exc_info=True,
                )

                continue
            for i, bit in enumerate(response.bits):
                addr = start_addr + i
                name = self._find_register_name(COIL_REGISTERS, addr)
                if name and name in self.available_registers["coil_registers"]:
                    data[name] = bool(bit)
                    self.statistics["total_registers_read"] += 1
        return data


    async def _read_discrete_inputs_optimized(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if "discrete_inputs" not in self._register_groups:
            return data
        if self.client is None:
            await self._ensure_connection()
        for start_addr, count in self._register_groups["discrete_inputs"]:
            response = await self._read_with_retry(
                self.client.read_discrete_inputs, start_addr, count, "discrete"
            )
            if response is None:

    async def _read_discrete_inputs_optimized(self) -> dict[str, Any]:
        """Read discrete input registers using optimized batch reading."""
        data = {}

        if "discrete_inputs" not in self._register_groups:
            return data

        if not self.client:
            await self._ensure_connection()
        client = self.client
        if client is None or not client.connected:
            raise ConnectionException("Modbus client is not connected")

        for start_addr, count in self._register_groups["discrete_inputs"]:
            try:
                # Pass "count" as a keyword argument to ensure compatibility with
                # Modbus helpers that expect keyword-only parameters.
                response = await self._call_modbus(
                    client.read_discrete_inputs,
                    start_addr,
                    count=count,
                )
                if response is None:
                    _LOGGER.error(
                        "No response reading discrete inputs at 0x%04X",
                        start_addr,
                    )
                    continue
                if response.isError():
                    _LOGGER.debug(
                        "Failed to read discrete inputs at 0x%04X: %s", start_addr, response
                    )
                    continue

                if not response.bits:
                    if response.bits is None:
                        _LOGGER.error(
                            "No bits returned reading discrete inputs at 0x%04X",
                            start_addr,
                        )
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

            except (ModbusException, ConnectionException):
                _LOGGER.debug("Error reading discrete inputs at 0x%04X", start_addr, exc_info=True)
                continue
            except (OSError, asyncio.TimeoutError, ValueError):
                _LOGGER.error(
                    "Unexpected error reading discrete inputs at 0x%04X",
                    start_addr,
                    exc_info=True,
                )

                continue
            for i, bit in enumerate(response.bits):
                addr = start_addr + i
                name = self._find_register_name(DISCRETE_INPUT_REGISTERS, addr)
                if name and name in self.available_registers["discrete_inputs"]:
                    data[name] = bool(bit)
                    self.statistics["total_registers_read"] += 1
        return data


    # ------------------------------------------------------------------
    # Data processing
    # ------------------------------------------------------------------

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
        if register_name in SIGNED_REGISTERS:
            value = _to_signed_int16(value)
            if value == -32768:
                return None
        elif register_name in DAC_REGISTERS:
            if value < 0 or value > 4095:
                _LOGGER.warning("DAC register %s has invalid value: %s", register_name, value)
                return None
        elif value == SENSOR_UNAVAILABLE:
            if "flow" in register_name:
                return None
        if register_name in REGISTER_MULTIPLIERS:
            value = value * REGISTER_MULTIPLIERS[register_name]
        return value

    def _post_process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        processed = dict(data)
        out_t = processed.get("outside_temperature")
        sup_t = processed.get("supply_temperature")
        exh_t = processed.get("exhaust_temperature")
        if out_t is not None and sup_t is not None and exh_t is not None and exh_t != out_t:
            efficiency = (sup_t - out_t) / (exh_t - out_t) * 100
            processed["calculated_efficiency"] = max(0, min(100, efficiency))
        if "supply_flow_rate" in processed and "exhaust_flow_rate" in processed:
            balance = processed["supply_flow_rate"] - processed["exhaust_flow_rate"]
            processed["flow_balance"] = balance
            if balance > 0:
                processed["flow_balance_status"] = "supply_dominant"
            elif balance < 0:
                processed["flow_balance_status"] = "exhaust_dominant"
            else:
                processed["flow_balance_status"] = "balanced"
        return processed

    # ------------------------------------------------------------------
    # Update routines
    # ------------------------------------------------------------------
    def _update_data_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper executed in executor."""
        return asyncio.run(self._update_data_async())

    async def _update_data_async(self) -> Dict[str, Any]:
        if not self._register_groups:
            self._precompute_register_groups()
        input_data = await self._read_input_registers_optimized()
        holding_data = await self._read_holding_registers_optimized()
        coil_data = await self._read_coil_registers_optimized()
        discrete_data = await self._read_discrete_inputs_optimized()
        data = {**input_data, **holding_data, **coil_data, **discrete_data}
        data = self._post_process_data(data)
        self._last_successful_read = dt_util.utcnow().isoformat()
        self._failed_registers.clear()
        return data

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


    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the device."""
        try:
            data = await self.hass.async_add_executor_job(self._update_data_sync)
        except ConnectionException as exc:
            raise UpdateFailed(str(exc)) from exc
        except ModbusException as exc:
            raise UpdateFailed(str(exc)) from exc
        self.statistics.setdefault("total_reads", 0)
        self.statistics["total_reads"] += 1
        return data

    # ------------------------------------------------------------------
    # Write support
    # ------------------------------------------------------------------
    async def async_write_register(
        self, register: str, value: int | List[int], *, refresh: bool = True
    ) -> bool:
        """Write value to a holding register.

        Parameters:
            register: Name of the holding register.
            value: Single integer or list of integers to write.
            refresh: If ``True`` (default) the coordinator will schedule a
                data refresh after the write succeeds.
        """

        if register not in HOLDING_REGISTERS:
            return False
        await self._ensure_connection()
        address = HOLDING_REGISTERS[register]
        if isinstance(value, list):
            # Multi-register writes only allowed from the first register in the block
            base, _, idx = register.rpartition("_")
            if not idx.isdigit() or int(idx) != 1:

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
                    if len(value) != MULTI_REGISTER_SIZES[start_register]:
                        _LOGGER.error(
                            "Register %s expects %d values",
                            start_register,
                            MULTI_REGISTER_SIZES[start_register],
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
                            MULTI_REGISTER_SIZES[start_register],
                        )
                        return False
                    values = [int(v) for v in value]
                else:
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
            for offset, _ in enumerate(value):
                expected = HOLDING_REGISTERS.get(f"{base}_{offset + 1}")
                if expected != address + offset:
                    return False
            async with self._connection_lock:
                response = await _call_modbus(
                    self.client.write_registers,
                    self.slave_id,
                    address=address,
                    values=value,
                )
        else:
            async with self._connection_lock:
                response = await _call_modbus(
                    self.client.write_register,
                    self.slave_id,
                    address=address,
                    value=value,
                )
        if response is None or getattr(response, "isError", lambda: False)():
            return False
        if refresh:
            await self.async_request_refresh()
        return True

    # ------------------------------------------------------------------
    # Device information helpers
    # ------------------------------------------------------------------
    def get_device_info(self) -> Dict[str, Any]:
        info = self.device_info or {}
        device_name = info.get("device_name", self.name)
        return {
            "identifiers": {(DOMAIN, self.host)},
            "manufacturer": MANUFACTURER,
            "model": info.get("model", MODEL),
            "name": device_name,
            "sw_version": info.get("firmware"),
        }


    @property
    def device_info_dict(self) -> Dict[str, Any]:
        return self.get_device_info()

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


    # ------------------------------------------------------------------
    # Performance statistics
    # ------------------------------------------------------------------
    @property

    def performance_stats(self) -> Dict[str, Any]:

    def performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""

        return {
            "total_registers_read": self.statistics.get("total_registers_read", 0),
            "failed_batches": len(self._failed_registers),
            "last_successful_read": self._last_successful_read,
            "status": "ok" if not self._failed_registers else "degraded",
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
        }

        return diagnostics

    def get_device_info(self) -> DeviceInfo:
        """Get device information for Home Assistant."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.host}:{self.port}:{self.slave_id}")},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=self.device_info.get("model", MODEL),
            sw_version=self.device_info.get("firmware", "Unknown"),
            configuration_url=f"http://{self.host}",
        )

    @property
    def device_info_dict(self) -> dict[str, Any]:
        """Return device information as a plain dictionary for legacy use."""
        return self.get_device_info().as_dict()

