"""Data coordinator for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from homeassistant.util import dt as dt_util

try:  # pragma: no cover - handle missing pymodbus during tests
    from pymodbus.exceptions import ConnectionException, ModbusException
except (ModuleNotFoundError, ImportError):  # pragma: no cover

    class ConnectionException(Exception):
        """Fallback exception when pymodbus is not available."""

        pass

    class ModbusException(Exception):
        """Fallback Modbus exception when pymodbus is not available."""

        pass


if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from pymodbus.client import AsyncModbusTcpClient

from homeassistant.core import HomeAssistant

try:  # pragma: no cover
    from homeassistant.helpers.device_registry import DeviceInfo
except (ModuleNotFoundError, ImportError):  # pragma: no cover

    class DeviceInfo(dict):
        """Minimal fallback DeviceInfo for tests."""

        pass


from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    DOMAIN,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    MANUFACTURER,
    MODEL,
    REGISTER_MULTIPLIERS,
)
from .device_scanner import DeviceCapabilities, ThesslaGreenDeviceScanner
from .modbus_helpers import _call_modbus as call_modbus

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenModbusCoordinator(DataUpdateCoordinator):
    """Optimized data coordinator for ThesslaGreen Modbus device."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        name: str,
        scan_interval: timedelta,
        timeout: int = 10,
        retry: int = 3,
        force_full_register_list: bool = False,
        entry: Optional[Any] = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=scan_interval,
        )

        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.device_name = name
        self.timeout = timeout
        self.retry = retry
        self.force_full_register_list = force_full_register_list
        self.entry = entry

        # Connection management
        self.client: Optional["AsyncModbusTcpClient"] = None
        self._connection_lock = asyncio.Lock()
        self._last_successful_read = dt_util.utcnow()

        # Device info and capabilities
        self.device_info: Dict[str, Any] = {}
        self.capabilities: DeviceCapabilities = DeviceCapabilities()
        self.available_registers: Dict[str, Set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }
        # Pre-computed reverse register maps for fast lookups
        self._input_registers_rev = {addr: name for name, addr in INPUT_REGISTERS.items()}
        self._holding_registers_rev = {addr: name for name, addr in HOLDING_REGISTERS.items()}
        self._coil_registers_rev = {addr: name for name, addr in COIL_REGISTERS.items()}
        self._discrete_inputs_rev = {addr: name for name, addr in DISCRETE_INPUT_REGISTERS.items()}

        # Optimization: Pre-computed register groups for batch reading
        self._register_groups: Dict[str, List[Tuple[int, int]]] = {}
        self._failed_registers: Set[str] = set()
        self._consecutive_failures = 0
        self._max_failures = 5

        # Device scan result
        self.device_scan_result: Optional[Dict[str, Any]] = None

        # Statistics and diagnostics
        self.statistics = {
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
        return await call_modbus(func, self.slave_id, *args, **kwargs)

    async def async_setup(self) -> bool:
        """Set up the coordinator by scanning the device."""
        _LOGGER.info("Setting up ThesslaGreen coordinator for %s:%s", self.host, self.port)

        # Scan device to discover available registers and capabilities
        if not self.force_full_register_list:
            _LOGGER.info("Scanning device for available registers...")
            scanner = ThesslaGreenDeviceScanner(
                host=self.host,
                port=self.port,
                slave_id=self.slave_id,
                timeout=self.timeout,
                retry=self.retry,
            )

            try:
                self.device_scan_result = await scanner.scan_device()
                self.available_registers = self.device_scan_result.get("available_registers", {})
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
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.exception("Device scan failed: %s", exc)
                raise
            except (OSError, asyncio.TimeoutError, ValueError) as exc:
                _LOGGER.exception("Unexpected error during device scan: %s", exc)
                raise
            finally:
                await scanner.close()
        else:
            _LOGGER.info("Using full register list (skipping scan)")
            # Load all registers if forced
            self._load_full_register_list()

        # Pre-compute register groups for batch reading
        self._compute_register_groups()

        # Test initial connection
        await self._test_connection()

        return True

    def _load_full_register_list(self) -> None:
        """Load full register list when forced."""
        self.available_registers = {
            "input_registers": set(INPUT_REGISTERS.keys()),
            "holding_registers": set(HOLDING_REGISTERS.keys()),
            "coil_registers": set(COIL_REGISTERS.keys()),
            "discrete_inputs": set(DISCRETE_INPUT_REGISTERS.keys()),
        }

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
            holding_addrs = [
                HOLDING_REGISTERS[reg] for reg in self.available_registers["holding_registers"]
            ]
            self._register_groups["holding_registers"] = self._group_registers_for_batch_read(
                sorted(holding_addrs)
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
        self, addresses: List[int], max_gap: int = 10, max_batch: int = 16
    ) -> List[Tuple[int, int]]:
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

    async def _test_connection(self) -> None:
        """Test initial connection to the device."""
        async with self._connection_lock:
            try:
                await self._ensure_connection()
                # Try to read a basic register to verify communication
 codex/refactor-coordinator.py-for-modbus-calls
                response = await self._call_modbus(
                    self.client.read_input_registers, 0x0000, 1
=======
                response = await _call_modbus(
                    self.client.read_input_registers,
                    self.slave_id,
                    0x0000,
                    1,
 main
                )
                if response.isError():
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

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the device with optimized batch reading."""
        start_time = dt_util.utcnow()

        async with self._connection_lock:
            try:
                await self._ensure_connection()

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

    async def _read_input_registers_optimized(self) -> Dict[str, Any]:
        """Read input registers using optimized batch reading."""
        data = {}

        if "input_registers" not in self._register_groups:
            return data

        for start_addr, count in self._register_groups["input_registers"]:
            try:
                response = await self._call_modbus(
                    self.client.read_input_registers, start_addr, count
                )
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

        return data

    async def _read_holding_registers_optimized(self) -> Dict[str, Any]:
        """Read holding registers using optimized batch reading."""
        data = {}

        if "holding_registers" not in self._register_groups:
            return data

        for start_addr, count in self._register_groups["holding_registers"]:
            try:
                response = await self._call_modbus(
                    self.client.read_holding_registers, start_addr, count
                )
                if response.isError():
                    _LOGGER.debug(
                        "Failed to read holding registers at 0x%04X: %s", start_addr, response
                    )
                    continue

                # Process each register in the batch
                for i, value in enumerate(response.registers):
                    addr = start_addr + i
                    register_name = self._find_register_name(HOLDING_REGISTERS, addr)
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

        return data

    async def _read_coil_registers_optimized(self) -> Dict[str, Any]:
        """Read coil registers using optimized batch reading."""
        data = {}

        if "coil_registers" not in self._register_groups:
            return data

        for start_addr, count in self._register_groups["coil_registers"]:
            try:
 codex/refactor-coordinator.py-for-modbus-calls
                response = await self._call_modbus(
                    self.client.read_coils, start_addr, count
=======
                response = await _call_modbus(
                    self.client.read_coils,
                    self.slave_id,
                    start_addr,
                    count,
 main
                )
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

        return data

    async def _read_discrete_inputs_optimized(self) -> Dict[str, Any]:
        """Read discrete input registers using optimized batch reading."""
        data = {}

        if "discrete_inputs" not in self._register_groups:
            return data

        for start_addr, count in self._register_groups["discrete_inputs"]:
            try:
                response = await self._call_modbus(
                    self.client.read_discrete_inputs, start_addr, count
                )
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

        return data

    def _find_register_name(self, register_map: Dict[str, int], address: int) -> Optional[str]:
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
        if value == 0x8000 and "temperature" in register_name.lower():
            return None  # No sensor
        if value == 0x8000 and "flow" in register_name.lower():
            return None  # No sensor

        # Apply multiplier
        if register_name in REGISTER_MULTIPLIERS:
            value = value * REGISTER_MULTIPLIERS[register_name]

        return value

    def _post_process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
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
        if "supply_flowrate" in data and "exhaust_flowrate" in data:
            data["flow_balance"] = data["supply_flowrate"] - data["exhaust_flowrate"]
            data["flow_balance_status"] = (
                "balanced"
                if abs(data["flow_balance"]) < 10
                else "supply_dominant" if data["flow_balance"] > 0 else "exhaust_dominant"
            )

        return data

    async def async_write_register(
        self, register_name: str, value: float, refresh: bool = True
    ) -> bool:
        """Write to a holding or coil register.

        Values should be provided in user units (°C, minutes, etc.). The value
        will be scaled according to ``REGISTER_MULTIPLIERS`` before being
        written to the device.

        If ``refresh`` is ``True`` (default), the coordinator will request a data
        refresh after the write. Set to ``False`` when performing multiple writes
        in sequence and manually refresh at the end.
        """
        async with self._connection_lock:
            try:
                await self._ensure_connection()

                original_value = value

                # Apply multiplier if defined and convert to integer for Modbus
                if register_name in REGISTER_MULTIPLIERS:
                    multiplier = REGISTER_MULTIPLIERS[register_name]
                    value = int(round(value / multiplier))
                else:
                    value = int(round(value))

                # Determine register type and address
                if register_name in HOLDING_REGISTERS:
                    address = HOLDING_REGISTERS[register_name]
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

                if response.isError():
                    _LOGGER.error("Error writing to register %s: %s", register_name, response)
                    return False

                _LOGGER.info("Successfully wrote %s to register %s", original_value, register_name)

                if refresh:
                    await self.async_request_refresh()
                return True

            except (ModbusException, ConnectionException):
                _LOGGER.exception("Failed to write register %s", register_name)
                return False
            except (OSError, asyncio.TimeoutError, ValueError):
                _LOGGER.exception("Unexpected error writing register %s", register_name)
                return False

    async def _disconnect(self) -> None:
        """Disconnect from Modbus device."""
        if self.client is not None:
            try:
                result = self.client.close()
                if inspect.isawaitable(result):
                    await result
            except (ModbusException, ConnectionException):
                _LOGGER.debug("Error disconnecting", exc_info=True)
            except OSError:
                _LOGGER.exception("Unexpected error disconnecting")

        self.client = None
        _LOGGER.debug("Disconnected from Modbus device")

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
        await self._disconnect()

    @property
    def performance_stats(self) -> Dict[str, Any]:
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

    def get_diagnostic_data(self) -> Dict[str, Any]:
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

        diagnostics: Dict[str, Any] = {
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
    def device_info_dict(self) -> Dict[str, Any]:
        """Return device information as a plain dictionary for legacy use."""
        return self.get_device_info().as_dict()
