"""Asynchronous data coordinator for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

try:  # pragma: no cover - handle missing Home Assistant util during tests
    from homeassistant.util import dt as dt_util
except (ModuleNotFoundError, ImportError):  # pragma: no cover

    class _DTUtil:
        """Fallback minimal dt util."""

        @staticmethod
        def now():
            from datetime import datetime, timezone

            return datetime.now(timezone.utc)

        @staticmethod
        def utcnow():
            from datetime import datetime, timezone

            return datetime.now(timezone.utc)

    dt_util = _DTUtil()  # type: ignore

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
from pymodbus.client import AsyncModbusTcpClient

from custom_components.thessla_green_modbus.registers.loader import (
    get_all_registers,
    get_registers_by_function,
)

from .config_flow import CannotConnect
from .const import (
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    CONF_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KNOWN_MISSING_REGISTERS,
    MANUFACTURER,
    MAX_BATCH_REGISTERS,
    SENSOR_UNAVAILABLE,
    UNKNOWN_MODEL,
)
from .modbus_helpers import _call_modbus, group_reads
from .scanner_core import DeviceCapabilities, ThesslaGreenDeviceScanner

REGISTER_DEFS = {r.name: r for r in get_all_registers()}


def get_register_definition(name: str):
    return REGISTER_DEFS[name]


_LOGGER = logging.getLogger(__name__)


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
        max_registers_per_request: int = DEFAULT_MAX_REGISTERS_PER_REQUEST,
        entry: ConfigEntry | None = None,
        skip_missing_registers: bool = False,
    ) -> None:
        """Initialize the coordinator.

        ``max_registers_per_request`` is clamped to the safe Modbus range of
        1–MAX_BATCH_REGISTERS registers per request.
        """
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

        if entry is not None:
            try:
                self.effective_batch = min(
                    int(
                        entry.options.get(
                            CONF_MAX_REGISTERS_PER_REQUEST, MAX_BATCH_REGISTERS
                        )
                    ),
                    MAX_BATCH_REGISTERS,
                )
            except (TypeError, ValueError):
                self.effective_batch = MAX_BATCH_REGISTERS
        else:
            self.effective_batch = min(
                int(max_registers_per_request), MAX_BATCH_REGISTERS
            )
        if self.effective_batch < 1:
            self.effective_batch = 1
        self.max_registers_per_request = self.effective_batch

        # Connection management
        self.client: AsyncModbusTcpClient | None = None
        self._connection_lock = asyncio.Lock()

        # Stop listener for Home Assistant shutdown
        self._stop_listener: Callable[[], None] | None = None

        # Device info and capabilities
        self.device_info: dict[str, Any] = {}
        self.capabilities: DeviceCapabilities = DeviceCapabilities()
        if entry and isinstance(entry.data.get("capabilities"), dict):
            try:
                self.capabilities = DeviceCapabilities(**entry.data["capabilities"])
            except (TypeError, ValueError):
                _LOGGER.debug("Invalid capabilities in config entry", exc_info=True)
        self.available_registers: dict[str, set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
            "calculated": {"estimated_power", "total_energy"},
        }
        # Register maps and reverse lookup maps
        self._register_maps = {
            "input_registers": {r.name: r.address for r in get_registers_by_function("04")},
            "holding_registers": {r.name: r.address for r in get_registers_by_function("03")},
            "coil_registers": {r.name: r.address for r in get_registers_by_function("01")},
            "discrete_inputs": {r.name: r.address for r in get_registers_by_function("02")},
        }
        self._reverse_maps = {
            key: {addr: name for name, addr in mapping.items()}
            for key, mapping in self._register_maps.items()
        }

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

        self.last_scan: datetime | None = None

        self._last_power_timestamp = dt_util.utcnow()
        self._total_energy = 0.0

    async def _call_modbus(
        self, func: Callable[..., Any], *args: Any, attempt: int = 1, **kwargs: Any
    ) -> Any:
        """Wrapper around Modbus calls injecting the slave ID."""
        if not self.client:
            raise ConnectionException("Modbus client is not connected")
        return await _call_modbus(
            func,
            self.slave_id,
            *args,
            attempt=attempt,
            max_attempts=self.retry,
            **kwargs,
        )

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
                    max_registers_per_request=self.effective_batch,
                )

                self.device_scan_result = await scanner.scan_device()
                self.last_scan = dt_util.utcnow()
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

                caps_obj = self.device_scan_result.get("capabilities")
                if isinstance(caps_obj, DeviceCapabilities):
                    self.capabilities = caps_obj
                elif isinstance(caps_obj, dict):
                    self.capabilities = DeviceCapabilities(**caps_obj)
                else:
                    _LOGGER.error(
                        "Invalid capabilities format: expected dict, got %s",
                        type(caps_obj).__name__,
                    )
                    raise CannotConnect("invalid_capabilities")

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
            except asyncio.TimeoutError as exc:
                _LOGGER.warning("Device scan timed out: %s", exc)
                raise
            except (OSError, ValueError) as exc:
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
        self.available_registers = {
            key: set(mapping.keys()) for key, mapping in self._register_maps.items()
        }

        self.device_info = {
            "device_name": f"{DEFAULT_NAME} {UNKNOWN_MODEL}",
            "model": UNKNOWN_MODEL,
            "firmware": "Unknown",
            "serial_number": "Unknown",
            "input_registers": set(self._register_maps["input_registers"].keys()),
            "holding_registers": set(self._register_maps["holding_registers"].keys()),
            "coil_registers": set(self._register_maps["coil_registers"].keys()),
            "discrete_inputs": set(self._register_maps["discrete_inputs"].keys()),
        }

        if self.skip_missing_registers:
            for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                self.available_registers[reg_type].difference_update(names)

        self.device_info = {
            "device_name": f"{DEFAULT_NAME} {UNKNOWN_MODEL}",
            "model": UNKNOWN_MODEL,
            "firmware": "Unknown",
            "serial_number": "Unknown",
        }

        _LOGGER.info(
            "Loaded full register list: %d total registers",
            sum(len(regs) for regs in self.available_registers.values()),
        )

    def _compute_register_groups(self) -> None:
        """Pre-compute register groups for optimized batch reading."""
        self._register_groups.clear()

        for key, names in self.available_registers.items():
            if not names:
                continue

            # Build list of raw addresses taking register length into account
            addresses: list[int] = []
            mapping = self._register_maps[key]
            for reg in names:
                addr = mapping.get(reg)
                if addr is None:
                    continue
                try:
                    definition = get_register_definition(reg)
                    length = max(1, definition.length)
                except (KeyError, AttributeError, TypeError) as err:
                    _LOGGER.debug("Missing definition for %s: %s", reg, err)
                    length = 1
                except Exception as err:  # pragma: no cover - unexpected
                    _LOGGER.exception("Unexpected error getting definition for %s: %s", reg, err)
                    length = 1
                addresses.extend(range(addr, addr + length))

            self._register_groups[key] = group_reads(addresses, max_block_size=self.effective_batch)

        _LOGGER.debug(
            "Pre-computed register groups: %s",
            {k: len(v) for k, v in self._register_groups.items()},
        )

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

                test_addresses = [reg.address for reg in get_registers_by_function("04")][:3]

                for addr in test_addresses:
                    response = await self.client.read_input_registers(
                        addr, count=1, unit=self.slave_id
                    )
                    if response.isError():
                        raise ConnectionException(f"Cannot read register {addr:#06x}")

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
            except asyncio.TimeoutError as exc:
                _LOGGER.warning("Connection test timed out: %s", exc)
                raise
            except OSError as exc:
                _LOGGER.exception("Unexpected error during connection test: %s", exc)
                raise

    async def _async_setup_client(self) -> bool:  # pragma: no cover
        """Set up the Modbus client if needed.

        Although only invoked in tests within this repository, this helper
        mirrors the logic executed during Home Assistant start-up. It returns
        ``True`` on success and ``False`` on failure.
        """
        try:
            async with self._connection_lock:
                await self._ensure_connection()
            return True
        except (ModbusException, ConnectionException) as exc:
            _LOGGER.exception("Failed to set up Modbus client: %s", exc)
            return False
        except asyncio.TimeoutError as exc:
            _LOGGER.warning("Setting up Modbus client timed out: %s", exc)
            return False
        except OSError as exc:
            _LOGGER.exception("Unexpected error setting up Modbus client: %s", exc)
            return False

    async def _ensure_connection(self) -> None:
        """Ensure Modbus connection is established."""
        if self.client and self.client.connected:
            return
        if self.client is not None:
            await self._disconnect()
        try:
            self.client = AsyncModbusTcpClient(self.host, port=self.port, timeout=self.timeout)
            if not await self.client.connect():
                raise ConnectionException(f"Could not connect to {self.host}:{self.port}")
            _LOGGER.debug("Modbus connection established")
        except (ModbusException, ConnectionException) as exc:
            self.statistics["connection_errors"] += 1
            _LOGGER.exception("Failed to establish connection: %s", exc)
            raise
        except asyncio.TimeoutError as exc:
            self.statistics["connection_errors"] += 1
            _LOGGER.warning("Connection attempt timed out: %s", exc)
            raise
        except OSError as exc:
            self.statistics["connection_errors"] += 1
            _LOGGER.exception("Unexpected error establishing connection: %s", exc)
            raise

    async def _async_update_data(self) -> dict[str, Any]:  # pragma: no cover
        """Fetch data from the device with optimized batch reading.

        This method overrides ``DataUpdateCoordinator._async_update_data``
        and is called by Home Assistant to refresh entity state.
        """
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
            except asyncio.TimeoutError as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["timeout_errors"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    await self._disconnect()

                _LOGGER.warning("Data update timed out: %s", exc)
                raise UpdateFailed(f"Timeout during data update: {exc}") from exc
            except (OSError, ValueError) as exc:
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
                self._find_register_name("input_registers", start_addr + i) for i in range(count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            for attempt in range(1, self.retry + 1):
                try:
                    response = await self._call_modbus(
                        client.read_input_registers,
                        start_addr,
                        count=count,
                        attempt=attempt,
                    )
                    if response is None or response.isError():
                        self._mark_registers_failed(register_names)
                        if attempt == self.retry:
                            _LOGGER.error("Failed to read input registers at 0x%04X", start_addr)
                        else:
                            _LOGGER.info("Retrying input registers at 0x%04X", start_addr)
                        continue

                    for i, value in enumerate(response.registers):
                        addr = start_addr + i
                        register_name = self._find_register_name("input_registers", addr)
                        if (
                            register_name
                            and register_name in self.available_registers["input_registers"]
                        ):
                            processed_value = self._process_register_value(register_name, value)
                            if processed_value is not None:
                                data[register_name] = processed_value
                                self.statistics["total_registers_read"] += 1
                                self._clear_register_failure(register_name)
                                _LOGGER.debug(
                                    "Read input 0x%04X (%s) = %s",
                                    addr,
                                    register_name,
                                    processed_value,
                                )

                    if len(response.registers) < count:
                        missing = register_names[len(response.registers) :]
                        self._mark_registers_failed(missing)
                    break
                except (ModbusException, ConnectionException) as exc:
                    self._mark_registers_failed(register_names)
                    if attempt == self.retry:
                        _LOGGER.error(
                            "Persistent failure reading input registers at 0x%04X",
                            start_addr,
                            exc_info=True,
                        )
                    else:
                        _LOGGER.info(
                            "Retrying input registers at 0x%04X after error: %s",
                            start_addr,
                            exc,
                        )
                    continue
                except asyncio.TimeoutError:
                    self._mark_registers_failed(register_names)
                    _LOGGER.warning(
                        "Timeout reading input registers at 0x%04X (attempt %d/%d)",
                        start_addr,
                        attempt,
                        self.retry,
                    )
                    if attempt == self.retry:
                        _LOGGER.error(
                            "Persistent timeout reading input registers at 0x%04X",
                            start_addr,
                        )
                    continue
                except (OSError, ValueError):
                    self._mark_registers_failed(register_names)
                    _LOGGER.error(
                        "Unexpected error reading input registers at 0x%04X",
                        start_addr,
                        exc_info=True,
                    )
                    break

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
                self._find_register_name("holding_registers", start_addr + i) for i in range(count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            for attempt in range(1, self.retry + 1):
                try:
                    response = await self._call_modbus(
                        client.read_holding_registers,
                        start_addr,
                        count=count,
                        attempt=attempt,
                    )
                    if response is None or response.isError():
                        self._mark_registers_failed(register_names)
                        if attempt == self.retry:
                            _LOGGER.error(
                                "Failed to read holding registers at 0x%04X",
                                start_addr,
                            )
                        else:
                            _LOGGER.info("Retrying holding registers at 0x%04X", start_addr)
                        continue

                    for i, value in enumerate(response.registers):
                        addr = start_addr + i
                        register_name = self._find_register_name("holding_registers", addr)
                        if (
                            register_name
                            and register_name in self.available_registers["holding_registers"]
                        ):
                            processed_value = self._process_register_value(register_name, value)
                            if processed_value is not None:
                                data[register_name] = processed_value
                                self.statistics["total_registers_read"] += 1
                                self._clear_register_failure(register_name)
                                _LOGGER.debug(
                                    "Read holding 0x%04X (%s) = %s",
                                    addr,
                                    register_name,
                                    processed_value,
                                )

                    if len(response.registers) < count:
                        missing = register_names[len(response.registers) :]
                        self._mark_registers_failed(missing)
                    break
                except (ModbusException, ConnectionException) as exc:
                    self._mark_registers_failed(register_names)
                    if attempt == self.retry:
                        _LOGGER.error(
                            "Persistent failure reading holding registers at 0x%04X",
                            start_addr,
                            exc_info=True,
                        )
                    else:
                        _LOGGER.info(
                            "Retrying holding registers at 0x%04X after error: %s",
                            start_addr,
                            exc,
                        )
                    continue
                except asyncio.TimeoutError:
                    self._mark_registers_failed(register_names)
                    _LOGGER.warning(
                        "Timeout reading holding registers at 0x%04X (attempt %d/%d)",
                        start_addr,
                        attempt,
                        self.retry,
                    )
                    if attempt == self.retry:
                        _LOGGER.error(
                            "Persistent timeout reading holding registers at 0x%04X",
                            start_addr,
                        )
                    continue
                except (OSError, ValueError):
                    self._mark_registers_failed(register_names)
                    _LOGGER.error(
                        "Unexpected error reading holding registers at 0x%04X",
                        start_addr,
                        exc_info=True,
                    )
                    break

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
                self._find_register_name("coil_registers", start_addr + i) for i in range(count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            for attempt in range(1, self.retry + 1):
                try:
                    response = await self._call_modbus(
                        client.read_coils,
                        start_addr,
                        count=count,
                        attempt=attempt,
                    )
                    if response is None or response.isError():
                        self._mark_registers_failed(register_names)
                        if attempt == self.retry:
                            _LOGGER.error("Failed to read coil registers at 0x%04X", start_addr)
                        else:
                            _LOGGER.info("Retrying coil registers at 0x%04X", start_addr)
                        continue

                    if not response.bits:
                        if response.bits is None:
                            _LOGGER.error(
                                "No bits returned reading coil registers at 0x%04X",
                                start_addr,
                            )
                        self._mark_registers_failed(register_names)
                        continue

                    for i in range(min(count, len(response.bits))):
                        addr = start_addr + i
                        register_name = self._find_register_name("coil_registers", addr)
                        if (
                            register_name
                            and register_name in self.available_registers["coil_registers"]
                        ):
                            bit = response.bits[i]
                            data[register_name] = bit
                            self.statistics["total_registers_read"] += 1
                            self._clear_register_failure(register_name)
                            _LOGGER.debug(
                                "Read coil 0x%04X (%s) = %s",
                                addr,
                                register_name,
                                bit,
                            )

                    if len(response.bits) < count:
                        missing = register_names[len(response.bits) :]
                        self._mark_registers_failed(missing)
                    break
                except (ModbusException, ConnectionException) as exc:
                    self._mark_registers_failed(register_names)
                    if attempt == self.retry:
                        _LOGGER.error(
                            "Persistent failure reading coil registers at 0x%04X",
                            start_addr,
                            exc_info=True,
                        )
                    else:
                        _LOGGER.info(
                            "Retrying coil registers at 0x%04X after error: %s",
                            start_addr,
                            exc,
                        )
                    continue
                except asyncio.TimeoutError:
                    self._mark_registers_failed(register_names)
                    _LOGGER.warning(
                        "Timeout reading coil registers at 0x%04X (attempt %d/%d)",
                        start_addr,
                        attempt,
                        self.retry,
                    )
                    if attempt == self.retry:
                        _LOGGER.error(
                            "Persistent timeout reading coil registers at 0x%04X",
                            start_addr,
                        )
                    continue
                except (OSError, ValueError):
                    self._mark_registers_failed(register_names)
                    _LOGGER.error(
                        "Unexpected error reading coil registers at 0x%04X",
                        start_addr,
                        exc_info=True,
                    )
                    break

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
                self._find_register_name("discrete_inputs", start_addr + i) for i in range(count)
            ]
            if all(name in failed for name in register_names if name):
                continue
            for attempt in range(1, self.retry + 1):
                try:
                    response = await self._call_modbus(
                        client.read_discrete_inputs,
                        start_addr,
                        count=count,
                        attempt=attempt,
                    )
                    if response is None or response.isError():
                        self._mark_registers_failed(register_names)
                        if attempt == self.retry:
                            _LOGGER.error("Failed to read discrete inputs at 0x%04X", start_addr)
                        else:
                            _LOGGER.info("Retrying discrete inputs at 0x%04X", start_addr)
                        continue

                    if not response.bits:
                        if response.bits is None:
                            _LOGGER.error(
                                "No bits returned reading discrete inputs at 0x%04X",
                                start_addr,
                            )
                        self._mark_registers_failed(register_names)
                        continue

                    for i in range(min(count, len(response.bits))):
                        addr = start_addr + i
                        register_name = self._find_register_name("discrete_inputs", addr)
                        if (
                            register_name
                            and register_name in self.available_registers["discrete_inputs"]
                        ):
                            bit = response.bits[i]
                            data[register_name] = bit
                            self.statistics["total_registers_read"] += 1
                            self._clear_register_failure(register_name)
                            _LOGGER.debug(
                                "Read discrete 0x%04X (%s) = %s",
                                addr,
                                register_name,
                                bit,
                            )

                    if len(response.bits) < count:
                        missing = register_names[len(response.bits) :]
                        self._mark_registers_failed(missing)
                    break
                except (ModbusException, ConnectionException) as exc:
                    self._mark_registers_failed(register_names)
                    if attempt == self.retry:
                        _LOGGER.error(
                            "Persistent failure reading discrete inputs at 0x%04X",
                            start_addr,
                            exc_info=True,
                        )
                    else:
                        _LOGGER.info(
                            "Retrying discrete inputs at 0x%04X after error: %s",
                            start_addr,
                            exc,
                        )
                    continue
                except asyncio.TimeoutError:
                    self._mark_registers_failed(register_names)
                    _LOGGER.warning(
                        "Timeout reading discrete inputs at 0x%04X (attempt %d/%d)",
                        start_addr,
                        attempt,
                        self.retry,
                    )
                    if attempt == self.retry:
                        _LOGGER.error(
                            "Persistent timeout reading discrete inputs at 0x%04X",
                            start_addr,
                        )
                    continue
                except (OSError, ValueError):
                    self._mark_registers_failed(register_names)
                    _LOGGER.error(
                        "Unexpected error reading discrete inputs at 0x%04X",
                        start_addr,
                        exc_info=True,
                    )
                    break

        return data

    def _find_register_name(self, register_type: str, address: int) -> str | None:
        """Find register name by address using pre-built reverse maps."""
        return self._reverse_maps.get(register_type, {}).get(address)

    def _process_register_value(self, register_name: str, value: int) -> Any:
        """Decode a raw register value using its definition."""

        if value == 0x8000:
            return None

        definition = get_register_definition(register_name)
        decoded = definition.decode(value)

        # Schedule registers are decoded to ``HH:MM`` strings; convert to minutes
        if definition.bcd and isinstance(decoded, str):
            try:
                hours, minutes = (int(x) for x in decoded.split(":"))
                return hours * 60 + minutes
            except ValueError:
                return decoded

        if decoded == SENSOR_UNAVAILABLE:
            return SENSOR_UNAVAILABLE

        return decoded

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
        *,
        offset: int = 0,
    ) -> bool:
        """Write to a holding or coil register.

        ``value`` should be supplied in user-friendly units. The register
        definition's :meth:`encode` method is used to convert it to the raw
        Modbus representation before sending to the device.
        """

        refresh_after_write = False
        async with self._connection_lock:
            try:
                await self._ensure_connection()
                if not self.client:
                    raise ConnectionException("Modbus client is not connected")

                original_value = value
                definition = get_register_definition(register_name)

                encoded_values: list[int] | None = None
                address = definition.address + offset

                if definition.length > 1:
                    if isinstance(value, (list, tuple)) and not isinstance(
                        value, (bytes, bytearray, str)
                    ):
                        if len(value) + offset > definition.length:
                            _LOGGER.error(
                                "Register %s expects at most %d values starting at offset %d",
                                register_name,
                                definition.length - offset,
                                offset,
                            )
                            return False
                        try:
                            encoded_values = [int(v) for v in value]
                        except (TypeError, ValueError):
                            _LOGGER.error(
                                "Register %s expects integer values", register_name
                            )
                            return False
                    else:
                        encoded = definition.encode(value)
                        if isinstance(encoded, list):
                            encoded_values = [int(v) for v in encoded]
                        else:
                            encoded_values = [int(encoded)]

                        if offset >= definition.length:
                            _LOGGER.error(
                                "Register %s expects at most %d values starting at offset %d",
                                register_name,
                                definition.length - offset,
                                offset,
                            )
                            return False

                        encoded_values = encoded_values[offset:]
                else:
                    if isinstance(value, (list, tuple)) and not isinstance(
                        value, (bytes, bytearray, str)
                    ):
                        _LOGGER.error("Register %s expects a single value", register_name)
                        return False
                    value = int(definition.encode(value))

                for attempt in range(1, self.retry + 1):
                    try:
                        if definition.function == 3:
                            if encoded_values is not None:
                                success = True
                                for idx in range(0, len(encoded_values), self.effective_batch):
                                    chunk = encoded_values[idx : idx + self.effective_batch]
                                    response = await self._call_modbus(
                                        self.client.write_registers,
                                        address=address + idx,
                                        values=[int(v) for v in chunk],
                                        attempt=attempt,
                                    )
                                    if response is None or response.isError():
                                        success = False
                                        break
                                if not success:
                                    if attempt == self.retry:
                                        _LOGGER.error(
                                            "Error writing to register %s: %s",
                                            register_name,
                                            response,
                                        )
                                        return False
                                    _LOGGER.info("Retrying write to register %s", register_name)
                                    continue
                            else:
                                response = await self._call_modbus(
                                    self.client.write_register,
                                    address=address,
                                    value=int(value),
                                    attempt=attempt,
                                )
                        elif definition.function == 1:
                            response = await self._call_modbus(
                                self.client.write_coil,
                                address=address,
                                value=bool(value),
                                attempt=attempt,
                            )
                        else:
                            _LOGGER.error("Register %s is not writable", register_name)
                            return False

                        if response is None or response.isError():
                            if attempt == self.retry:
                                _LOGGER.error(
                                    "Error writing to register %s: %s",
                                    register_name,
                                    response,
                                )
                                return False
                            _LOGGER.info("Retrying write to register %s", register_name)
                            continue

                        refresh_after_write = refresh
                        _LOGGER.info(
                            "Successfully wrote %s to register %s",
                            original_value,
                            register_name,
                        )
                        break
                    except (ModbusException, ConnectionException) as exc:
                        if attempt == self.retry:
                            _LOGGER.error(
                                "Failed to write register %s",
                                register_name,
                                exc_info=True,
                            )
                            return False
                        _LOGGER.info(
                            "Retrying write to register %s after error: %s",
                            register_name,
                            exc,
                        )
                        continue
                    except asyncio.TimeoutError:
                        _LOGGER.warning(
                            "Writing register %s timed out (attempt %d/%d)",
                            register_name,
                            attempt,
                            self.retry,
                            exc_info=True,
                        )
                        if attempt == self.retry:
                            _LOGGER.error(
                                "Persistent timeout writing register %s",
                                register_name,
                            )
                            return False
                        continue
                    except OSError:
                        _LOGGER.exception("Unexpected error writing register %s", register_name)
                        return False

            except (ModbusException, ConnectionException):  # pragma: no cover - safety
                _LOGGER.exception("Failed to write register %s", register_name)
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
        total_registers = sum(len(v) for v in self.available_registers.values())
        total_registers_json = len(get_all_registers())
        effective_batch = self.effective_batch
        registers_discovered = {key: len(value) for key, value in self.available_registers.items()}
        error_stats = {
            "connection_errors": statistics.get("connection_errors", 0),
            "timeout_errors": statistics.get("timeout_errors", 0),
        }

        diagnostics: dict[str, Any] = {
            "connection": connection,
            "statistics": statistics,
            "performance": self.performance_stats,
            "device_info": self.device_info,
            "available_registers": {
                key: sorted(list(value)) for key, value in self.available_registers.items()
            },
            "capabilities": self.capabilities.as_dict(),
            "scan_result": self.device_scan_result,
            "unknown_registers": self.unknown_registers,
            "scanned_registers": self.scanned_registers,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "firmware_version": self.device_info.get("firmware"),
            "total_available_registers": total_registers,
            "total_registers_json": total_registers_json,
            "effective_batch": effective_batch,
            "deep_scan": self.deep_scan,
            "force_full_register_list": self.force_full_register_list,
            "autoscan": not self.force_full_register_list,
            "registers_discovered": registers_discovered,
            "error_statistics": error_stats,
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
        # Determine the device model. Prefer any model already stored in
        # ``device_info`` but fall back to other sources when it is missing or
        # set to ``UNKNOWN_MODEL``. The scanner may place a detected model in
        # the capabilities result under ``model_type``. As a final fallback, use
        # any model specified in the config entry.
        model = self.device_info.get("model")
        if not model or model == UNKNOWN_MODEL:
            model = (
                self.device_scan_result.get("capabilities", {}).get("model_type")
                if self.device_scan_result
                else None
            )
        if (not model or model == UNKNOWN_MODEL) and self.entry is not None:
            model = cast(
                str | None,
                self.entry.options.get("model") if hasattr(self.entry, "options") else None,
            ) or cast(
                str | None,
                self.entry.data.get("model") if hasattr(self.entry, "data") else None,
            )
        if not model:
            model = UNKNOWN_MODEL
        self.device_info["model"] = model

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.host}:{self.port}:{self.slave_id}")},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=self.device_info.get("firmware", "Unknown"),
            configuration_url=f"http://{self.host}",
        )

    @property
    def device_name(self) -> str:
        """Return the configured or detected device name."""
        return cast(str, self.device_info.get("device_name") or self._device_name)

    @property
    def device_info_dict(self) -> dict[str, Any]:  # pragma: no cover
        """Return device information as a plain dictionary for legacy use.

        Retained for tests and external consumers which expect a simple
        mapping instead of a ``DeviceInfo`` instance.
        """
        return cast(dict[str, Any], self.get_device_info().as_dict())
