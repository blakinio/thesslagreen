"""Device scanner for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import csv
import inspect
import logging
import re
from dataclasses import asdict, dataclass, field
from importlib.resources import files
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException

if TYPE_CHECKING:  # pragma: no cover
    from pymodbus.client import AsyncModbusTcpClient

from .const import (
    COIL_REGISTERS,
    DEFAULT_SLAVE_ID,
    DISCRETE_INPUT_REGISTERS,
    KNOWN_MISSING_REGISTERS,
    SENSOR_UNAVAILABLE,
)
from .modbus_helpers import _call_modbus
from .registers import HOLDING_REGISTERS, INPUT_REGISTERS
from .utils import _to_snake_case

_LOGGER = logging.getLogger(__name__)

# Specific registers may only accept discrete values
REGISTER_ALLOWED_VALUES: Dict[str, Set[int]] = {
    "mode": {0, 1, 2},
    "season_mode": {0, 1},
    "special_mode": set(range(0, 12)),
    "antifreez_mode": {0, 1},
}


# Registers storing times encoded as HH:MM bytes
TIME_REGISTER_PREFIXES: Tuple[str, ...] = ("schedule_", "airing_")
# Registers storing times as BCD HHMM values
BCD_TIME_PREFIXES: Tuple[str, ...] = ("schedule_", "airing_")

# Registers storing combined airflow and temperature settings
SETTING_PREFIX = "setting_"


def _decode_register_time(value: int) -> Optional[int]:
    """Decode a 16-bit register with HH:MM byte encoding to ``HHMM``.

    The most significant byte stores the hour and the least significant byte
    stores the minute. ``None`` is returned if the value is negative or if the
    extracted hour/minute fall outside of valid ranges.
    """

    if value < 0:
        return None

    hour = (value >> 8) & 0xFF
    minute = value & 0xFF
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour * 100 + minute

    return None


def _decode_bcd_time(value: int) -> Optional[int]:
    """Decode BCD or decimal HHMM values to ``HHMM``."""

    nibbles = [(value >> shift) & 0xF for shift in (12, 8, 4, 0)]
    if all(n <= 9 for n in nibbles):
        hours = nibbles[0] * 10 + nibbles[1]
        minutes = nibbles[2] * 10 + nibbles[3]
        if hours <= 23 and minutes <= 59:
            return hours * 100 + minutes

    hours_dec = value // 100
    minutes_dec = value % 100
    if 0 <= hours_dec <= 23 and 0 <= minutes_dec <= 59:
        return hours_dec * 100 + minutes_dec
    return None


def _decode_setting_value(value: int) -> Optional[Tuple[int, float]]:
    """Decode a register storing airflow and temperature as ``0xAATT``.

    ``AA`` is the airflow in percent and ``TT`` is twice the desired supply
    temperature in degrees Celsius. ``None`` is returned if the value cannot be
    decoded or falls outside expected ranges.
    """

    if value < 0:
        return None

    airflow = (value >> 8) & 0xFF
    temp_double = value & 0xFF

    if airflow > 100 or temp_double > 200:
        return None

    return airflow, temp_double / 2


def _format_register_value(name: str, value: int) -> int | str:
    """Return a human-readable representation of a register value."""

    if name.startswith(BCD_TIME_PREFIXES):
        decoded = _decode_bcd_time(value)
        if decoded is None:
            return value
        return f"{decoded // 100:02d}:{decoded % 100:02d}"

    if name.startswith(SETTING_PREFIX):
        decoded = _decode_setting_value(value)
        if decoded is None:
            return value
        airflow, temp = decoded
        temp_str = f"{temp:g}"
        return f"{airflow}% @ {temp_str}°C"

    return value


# Maximum registers per batch read (Modbus limit)
MAX_BATCH_REGISTERS = 16

# Optional UART configuration registers (Air++ port)
UART_OPTIONAL_REGS = range(0x1168, 0x116C)


@dataclass
class DeviceInfo:
    model: str = "Unknown AirPack"
    firmware: str = "Unknown"
    serial_number: str = "Unknown"


@dataclass
class DeviceCapabilities:
    basic_control: bool = False
    temperature_sensors: Set[str] = field(default_factory=set)
    flow_sensors: Set[str] = field(default_factory=set)
    special_functions: Set[str] = field(default_factory=set)
    expansion_module: bool = False
    constant_flow: bool = False
    gwc_system: bool = False
    bypass_system: bool = False
    heating_system: bool = False
    cooling_system: bool = False
    air_quality: bool = False
    weekly_schedule: bool = False
    sensor_outside_temperature: bool = False
    sensor_supply_temperature: bool = False
    sensor_exhaust_temperature: bool = False
    sensor_fpx_temperature: bool = False
    sensor_duct_supply_temperature: bool = False
    sensor_gwc_temperature: bool = False
    sensor_ambient_temperature: bool = False
    sensor_heating_temperature: bool = False
    temperature_sensors_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ThesslaGreenDeviceScanner:
    """Device scanner for ThesslaGreen AirPack Home - compatible with pymodbus 3.5.*+"""

    def __init__(
        self,
        host: str,
        port: int,
        slave_id: int = DEFAULT_SLAVE_ID,
        timeout: int = 10,
        retry: int = 3,
        backoff: float = 0,
        verbose_invalid_values: bool = False,
        scan_uart_settings: bool = False,
        skip_known_missing: bool = False,
    ) -> None:
        """Initialize device scanner with consistent parameter names."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        self.backoff = backoff
        self.verbose_invalid_values = verbose_invalid_values
        self.scan_uart_settings = scan_uart_settings
        self.skip_known_missing = skip_known_missing

        # Available registers storage
        self.available_registers: Dict[str, Set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

        # Track holding registers that consistently fail to respond so we
        # can avoid retrying them repeatedly during scanning. The value is
        # a failure counter per register address.
        self._holding_failures: Dict[int, int] = {}
        # Cache holding registers that have exceeded retry attempts
        self._failed_holding: Set[int] = set()

        # Track input registers that consistently fail to respond so we can
        # avoid retrying them repeatedly during scanning
        self._input_failures: Dict[int, int] = {}
        self._failed_input: Set[int] = set()

        # Placeholder for register map and value ranges loaded asynchronously
        self._registers: Dict[str, Dict[int, str]] = {}
        self._register_ranges: Dict[str, Tuple[Optional[int], Optional[int]]] = {}

        # Keep track of the Modbus client so it can be closed later
        self._client: Optional["AsyncModbusTcpClient"] = None

        # Track registers for which invalid values have been reported
        self._reported_invalid: Set[str] = set()

    async def _async_setup(self) -> None:
        """Asynchronously load register definitions."""
        self._registers, self._register_ranges = await self._load_registers()

    @classmethod
    async def create(
        cls,
        host: str,
        port: int,
        slave_id: int = DEFAULT_SLAVE_ID,
        timeout: int = 10,
        retry: int = 3,
        backoff: float = 0,
        verbose_invalid_values: bool = False,
        scan_uart_settings: bool = False,
        skip_known_missing: bool = False,
    ) -> "ThesslaGreenDeviceScanner":
        """Factory to create an initialized scanner instance."""
        self = cls(
            host,
            port,
            slave_id,
            timeout,
            retry,
            backoff,
            verbose_invalid_values,
            scan_uart_settings,
            skip_known_missing,
        )
        await self._async_setup()
        return self

    async def _load_registers(
        self,
    ) -> Tuple[Dict[str, Dict[int, str]], Dict[str, Tuple[Optional[int], Optional[int]]]]:
        """Load Modbus register definitions and value ranges from CSV file."""
        csv_path = files(__package__) / "data" / "modbus_registers.csv"

        def _read_csv() -> (
            Tuple[Dict[str, Dict[int, str]], Dict[str, Tuple[Optional[int], Optional[int]]]]
        ):
            register_map: Dict[str, Dict[int, str]] = {"03": {}, "04": {}, "01": {}, "02": {}}
            register_ranges: Dict[str, Tuple[Optional[int], Optional[int]]] = {}
            try:
                with csv_path.open(newline="", encoding="utf-8") as csvfile:
                    reader = csv.DictReader(csvfile)
                    rows: Dict[str, List[Tuple[str, int, Optional[int], Optional[int]]]] = {
                        "03": [],
                        "04": [],
                        "01": [],
                        "02": [],
                    }
                    for row in reader:
                        code = row.get("Function_Code")
                        if not code or code.startswith("#"):
                            continue
                        name_raw = row.get("Register_Name")
                        if not isinstance(name_raw, str) or not name_raw.strip():
                            continue
                        name = _to_snake_case(name_raw)
                        try:
                            addr = int(row.get("Address_DEC", 0))
                        except (TypeError, ValueError):
                            continue
                        min_raw = row.get("Min")
                        max_raw = row.get("Max")

                        def _parse_range(label: str, raw: Optional[str]) -> Optional[int]:
                            if raw in (None, ""):
                                return None

                            text = str(raw).split("#", 1)[0].strip()
                            if not text:
                                _LOGGER.warning(
                                    "Ignoring non-numeric %s for %s: %s", label, name, raw
                                )
                                return None

                            if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
                                _LOGGER.warning(
                                    "Ignoring non-numeric %s for %s: %s", label, name, raw
                                )
                                return None

                            try:
                                return int(float(text))
                            except ValueError:
                                _LOGGER.warning(
                                    "Ignoring non-numeric %s for %s: %s", label, name, raw
                                )
                                return None

                        min_val = _parse_range("Min", min_raw)
                        max_val = _parse_range("Max", max_raw)
                        # Warn if a range is expected but Min/Max is missing
                        if (min_raw not in (None, "") or max_raw not in (None, "")) and (
                            min_val is None or max_val is None
                        ):
                            _LOGGER.warning(
                                "Incomplete range for %s: Min=%s Max=%s",
                                name,
                                min_raw,
                                max_raw,
                            )
                        if code in rows:
                            rows[code].append((name, addr, min_val, max_val))

                    for code, items in rows.items():
                        # Sort by address to ensure deterministic numbering
                        items.sort(key=lambda item: item[1])
                        counts: Dict[str, int] = {}
                        for name, *_ in items:
                            counts[name] = counts.get(name, 0) + 1
                        seen: Dict[str, int] = {}
                        for name, addr, min_val, max_val in items:
                            if addr in register_map[code]:
                                _LOGGER.warning(
                                    "Duplicate register address %s for function code %s: %s",
                                    addr,
                                    code,
                                    name,
                                )
                                continue
                            if counts[name] > 1:
                                idx = seen.get(name, 0) + 1
                                seen[name] = idx
                                name = f"{name}_{idx}"
                            register_map[code][addr] = name
                            if min_val is not None or max_val is not None:
                                register_ranges[name] = (min_val, max_val)

                    # Ensure all required registers are defined in the CSV
                    required_maps = {
                        "04": INPUT_REGISTERS,
                        "03": HOLDING_REGISTERS,
                        "01": COIL_REGISTERS,
                        "02": DISCRETE_INPUT_REGISTERS,
                    }
                    missing: Dict[str, Set[str]] = {}
                    for code, reg_map in required_maps.items():
                        defined = set(register_map.get(code, {}).values())
                        missing_regs = set(reg_map) - defined
                        if missing_regs:
                            missing[code] = missing_regs
                    if missing:
                        messages = [
                            f"{code}: {sorted(list(names))}" for code, names in missing.items()
                        ]
                        raise ValueError(
                            "Required registers missing from CSV: " + ", ".join(messages)
                        )
            except FileNotFoundError:
                _LOGGER.error("Register definition file not found: %s", csv_path)
            return register_map, register_ranges

        return await asyncio.to_thread(_read_csv)

    async def _read_input(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[int]]:
        """Read input registers with retry and backoff."""
        start = address
        end = address + count - 1

        if any(reg in self._failed_input for reg in range(start, end + 1)):
            _LOGGER.debug(
                "Skipping cached failed input registers 0x%04X-0x%04X",
                start,
                end,
            )
            return None

        for attempt in range(1, self.retry + 1):
            try:
                response = await _call_modbus(
                    client.read_input_registers, self.slave_id, address, count=count
                )
                if response is not None and not response.isError():
                    return response.registers
            except ModbusIOException as exc:
                _LOGGER.debug(
                    "Modbus IO error reading input registers 0x%04X-0x%04X on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
                if count == 1:
                    failures = self._input_failures.get(address, 0) + 1
                    self._input_failures[address] = failures
                    if failures >= self.retry and address not in self._failed_input:
                        self._failed_input.add(address)
                        _LOGGER.warning("Device does not expose register 0x%04X", address)
            except (ModbusException, ConnectionException, asyncio.TimeoutError) as exc:
                _LOGGER.debug(
                    "Failed to read input registers 0x%04X-0x%04X on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading input registers 0x%04X-0x%04X on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            if attempt < self.retry:
                await asyncio.sleep((self.backoff or 1) * 2 ** (attempt - 1))

        _LOGGER.warning(
            "Failed to read input registers 0x%04X-0x%04X after %d retries",
            start,
            end,
            self.retry,
        )
        self._failed_input.update(range(start, end + 1))
        _LOGGER.debug("Caching failed input registers 0x%04X-0x%04X", start, end)
        return None

    async def _read_holding(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[int]]:
        """Read holding registers with retry, backoff and failure tracking."""
        if address in self._failed_holding:
            _LOGGER.debug("Skipping cached failed holding register 0x%04X", address)
            return None

        failures = self._holding_failures.get(address, 0)
        if failures >= self.retry:
            _LOGGER.warning("Skipping unsupported holding register 0x%04X", address)
            return None

        for attempt in range(1, self.retry + 1):
            try:
                response = await _call_modbus(
                    client.read_holding_registers, self.slave_id, address, count=count
                )
                if response is None:
                    raise ModbusException("No response")
                if response.isError():
                    raise ModbusException(
                        f"Exception code {response.exception_code}"
                    )
                if address in self._holding_failures:
                    del self._holding_failures[address]
                return response.registers
            except ModbusIOException as exc:
                _LOGGER.debug(
                    "Modbus IO error reading holding 0x%04X (attempt %d/%d): %s",
                    address,
                    attempt,
                    self.retry,
                    exc,
                    exc_info=True,
                )
                if count == 1:
                    failures = self._holding_failures.get(address, 0) + 1
                    self._holding_failures[address] = failures
                    if failures >= self.retry and address not in self._failed_holding:
                        self._failed_holding.add(address)
                        _LOGGER.warning("Device does not expose register 0x%04X", address)
            except (ModbusException, ConnectionException, asyncio.TimeoutError) as exc:
                _LOGGER.debug(
                    "Failed to read holding 0x%04X (attempt %d/%d): %s",
                    address,
                    attempt,
                    self.retry,
                    exc,
                    exc_info=True,
                )
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading holding 0x%04X: %s",
                    address,
                    exc,
                    exc_info=True,
                )
                break

            if attempt < self.retry:
                await asyncio.sleep((self.backoff or 1) * 2 ** (attempt - 1))

        return None

    async def _read_coil(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[bool]]:
        """Read coil registers with retry and backoff."""
        for attempt in range(1, self.retry + 1):
            try:
                response = await _call_modbus(
                    client.read_coils, self.slave_id, address, count=count
                )
                if response is not None and not response.isError():
                    return response.bits[:count]
            except (ModbusException, ConnectionException, asyncio.TimeoutError) as exc:
                _LOGGER.debug(
                    "Failed to read coil 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading coil 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            if attempt < self.retry:
                await asyncio.sleep(2 ** (attempt - 1))

        return None

    async def _read_discrete(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[bool]]:
        """Read discrete input registers with retry and backoff."""
        for attempt in range(1, self.retry + 1):
            try:
                response = await _call_modbus(
                    client.read_discrete_inputs, self.slave_id, address, count=count
                )
                if response is not None and not response.isError():
                    return response.bits[:count]
            except (ModbusException, ConnectionException, asyncio.TimeoutError) as exc:
                _LOGGER.debug(
                    "Failed to read discrete 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading discrete 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            if attempt < self.retry:
                await asyncio.sleep(2 ** (attempt - 1))

        return None

    def _log_invalid_value(self, register_name: str, value: int) -> None:
        """Log invalid register value once per scan session.

        When ``verbose_invalid_values`` is ``False`` the first invalid value is
        logged at ``DEBUG`` level and subsequent ones are suppressed. If the
        flag is ``True`` the first occurrence is logged at ``INFO`` level and
        further occurrences are logged at ``DEBUG`` level.
        """
        formatted = _format_register_value(register_name, value)
        raw = f"0x{value:04X}"
        if register_name not in self._reported_invalid:
            level = logging.INFO if self.verbose_invalid_values else logging.DEBUG
            _LOGGER.log(
                level,
                "Invalid value for %s: raw=%s decoded=%s",
                register_name,
                raw,
                formatted,
            )
            self._reported_invalid.add(register_name)
        elif self.verbose_invalid_values:
            _LOGGER.debug(
                "Invalid value for %s: raw=%s decoded=%s",
                register_name,
                raw,
                formatted,
            )

    def _is_valid_register_value(self, register_name: str, value: int) -> bool:
        """Check if register value is valid (not a sensor error/missing value)."""
        name = register_name.lower()

        # Decode schedule/airing time values before validation
        if name.startswith(TIME_REGISTER_PREFIXES):
            decoded = _decode_register_time(value)
            if decoded is None:
                self._log_invalid_value(register_name, value)
                return False
            value = decoded

        # Validate registers storing schedule times
        if name.startswith(BCD_TIME_PREFIXES):
            if _decode_bcd_time(value) is None:

                self._log_invalid_value(register_name, value)
                return False
            return True

        # Validate registers storing combined airflow/temperature settings
        if name.startswith(SETTING_PREFIX):
            if _decode_setting_value(value) is None:
                self._log_invalid_value(register_name, value)
                return False
            return True

        # Temperature sensors use a sentinel value to indicate no sensor
        if "temperature" in name:
            if value == SENSOR_UNAVAILABLE:
                # Treat the register as unavailable without logging
                return False
            return True

        # Air flow sensors use the same sentinel for no sensor
        if any(x in name for x in ["flow", "air_flow", "flow_rate"]):
            if value in (SENSOR_UNAVAILABLE, 65535):
                self._log_invalid_value(register_name, value)
                return False
            return True

        # Discrete allowed values for specific registers
        if name in REGISTER_ALLOWED_VALUES:
            if value not in REGISTER_ALLOWED_VALUES[name]:
                self._log_invalid_value(register_name, value)
                return False
            return True

        # Use range from CSV if available
        if name in self._register_ranges:
            min_val, max_val = self._register_ranges[name]
            if min_val is not None and value < min_val:
                self._log_invalid_value(register_name, value)
                return False
            if max_val is not None and value > max_val:
                self._log_invalid_value(register_name, value)
                return False

        # Default: consider valid
        return True

    def _analyze_capabilities(self) -> DeviceCapabilities:
        """Analyze available registers to determine device capabilities."""
        caps = DeviceCapabilities()

        # Constant flow detection
        cf_indicators = {
            "constant_flow_active",
            "cf_version",
            "supply_air_flow",
            "exhaust_air_flow",
            "supply_flow_rate",
            "exhaust_flow_rate",
            "supply_percentage",
            "exhaust_percentage",
            "min_percentage",
            "max_percentage",
        }
        cf_registers = self.available_registers["input_registers"].union(
            self.available_registers["holding_registers"]
        )
        caps.constant_flow = bool(cf_indicators.intersection(cf_registers))

        # Systems detection
        caps.gwc_system = any(
            "gwc" in reg.lower()
            for registers in self.available_registers.values()
            for reg in registers
        )
        caps.bypass_system = any(
            "bypass" in reg.lower()
            for registers in self.available_registers.values()
            for reg in registers
        )

        # Expansion module
        caps.expansion_module = "expansion" in self.available_registers["discrete_inputs"]

        # Heating/Cooling systems
        caps.heating_system = any(
            "heating" in reg.lower() or "heater" in reg.lower()
            for registers in self.available_registers.values()
            for reg in registers
        )
        caps.cooling_system = any(
            "cooling" in reg.lower() or "cooler" in reg.lower()
            for registers in self.available_registers.values()
            for reg in registers
        )

        # Temperature sensors
        temp_sensors = [
            "outside_temperature",
            "supply_temperature",
            "exhaust_temperature",
            "fpx_temperature",
            "duct_supply_temperature",
            "gwc_temperature",
            "ambient_temperature",
            "heating_temperature",
        ]
        for sensor in temp_sensors:
            if sensor in self.available_registers["input_registers"]:
                caps.temperature_sensors.add(sensor)
                setattr(caps, f"sensor_{sensor}", True)
        caps.temperature_sensors_count = len(caps.temperature_sensors)

        # Flow sensors (simple pattern match across register types)
        caps.flow_sensors = {
            reg
            for regs in (
                self.available_registers["input_registers"],
                self.available_registers["holding_registers"],
            )
            for reg in regs
            if "flow" in reg
        }

        # Air quality sensors
        caps.air_quality = (
            any(
                sensor in self.available_registers["input_registers"]
                for sensor in [
                    "co2_level",
                    "voc_level",
                    "pm25_level",
                    "air_quality_index",
                ]
            )
            or "contamination_sensor" in self.available_registers["discrete_inputs"]
        )

        # Weekly schedule features - look for any scheduling related registers
        schedule_keywords = {"schedule", "weekly", "airing", "setting"}
        caps.weekly_schedule = any(
            any(keyword in reg.lower() for keyword in schedule_keywords)
            for registers in self.available_registers.values()
            for reg in registers
        )

        # Basic control availability
        caps.basic_control = "mode" in self.available_registers["holding_registers"]

        # Special functions from discrete inputs or input registers
        for func in ["fireplace", "airing_switch"]:
            if func in self.available_registers["discrete_inputs"]:
                caps.special_functions.add(func)
        if "water_removal_active" in self.available_registers["input_registers"]:
            caps.special_functions.add("water_removal")

        return caps

    async def scan(self) -> Tuple[DeviceInfo, DeviceCapabilities, Dict[str, Tuple[int, int]]]:
        """Scan device and return device info, capabilities and present blocks."""
        from pymodbus.client import AsyncModbusTcpClient

        # Store client instance for later cleanup in close()
        self._client = AsyncModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout,
        )
        client = self._client

        try:
            _LOGGER.debug("Connecting to ThesslaGreen device at %s:%s", self.host, self.port)
            connected = await client.connect()
            if not connected:
                raise ConnectionException(f"Failed to connect to {self.host}:{self.port}")

            _LOGGER.debug("Connected successfully, starting device scan")
            self._reported_invalid.clear()

            info = DeviceInfo()
            present_blocks = {}
            # Read firmware version (0x0000, 0x0001, 0x0004)
            fw_data = await self._read_input(client, 0x0000, 5)
            if fw_data and len(fw_data) >= 5:
                fw = f"{fw_data[0]}.{fw_data[1]}.{fw_data[4]}"
            if not fw_data or len(fw_data) < 3:
                _LOGGER.info(
                    "Firmware registers unavailable; firmware version could not be determined"
                )
                fw_data = None
                info.firmware = "Unknown"
            else:
                fw = f"{fw_data[0]}.{fw_data[1]}.{fw_data[2]}"
                info.firmware = fw
                _LOGGER.debug("Firmware version: %s", fw)

            # Read controller serial number (0x0018-0x001D)
            sn_data = await self._read_input(client, 0x0018, 6)
            if sn_data and len(sn_data) >= 6:
                pairs = [f"{sn_data[i]:02X}{sn_data[i+1]:02X}" for i in range(0, 6, 2)]
                info.serial_number = " ".join(pairs)
                _LOGGER.debug("Serial number: %s", info.serial_number)

            # Determine model based on firmware features
            model = "AirPack Home Series 4"
            if fw_data and fw_data[0] >= 4:
                if fw_data[1] >= 85:
                    model = "AirPack⁴ Energy++"
                else:
                    model = "AirPack⁴ Energy+"
            info.model = model
            # Dynamically scan all defined registers
            register_maps = {
                "input_registers": (INPUT_REGISTERS, self._read_input),
                "holding_registers": (HOLDING_REGISTERS, self._read_holding),
                "coil_registers": (COIL_REGISTERS, self._read_coil),
                "discrete_inputs": (DISCRETE_INPUT_REGISTERS, self._read_discrete),
            }

            for reg_type, (reg_map, read_fn) in register_maps.items():
                addr_to_name = {addr: name for name, addr in reg_map.items()}
                addresses = sorted(addr_to_name)
                if self.skip_known_missing:
                    addresses = [
                        a
                        for a in addresses
                        if addr_to_name[a] not in KNOWN_MISSING_REGISTERS.get(reg_type, set())
                    ]
                if reg_type == "holding_registers" and not self.scan_uart_settings:
                    addresses = [a for a in addresses if a not in UART_OPTIONAL_REGS]
                if not addresses:
                    continue

                for start, count in self._group_registers_for_batch_read(addresses):
                    values = await read_fn(client, start, count)
                    if values is None:
                        for addr in range(start, start + count):
                            single = await read_fn(client, addr, 1)
                            if single is None:
                                _LOGGER.debug("Failed to read %s register 0x%04X", reg_type, addr)
                                continue
                            name = addr_to_name.get(addr)
                            if not name:
                                continue
                            value = single[0]
                            if reg_type in ("input_registers", "holding_registers"):
                                if self._is_valid_register_value(name, value):
                                    self.available_registers[reg_type].add(name)
                            else:
                                self.available_registers[reg_type].add(name)
                        if count > 1:
                            for addr in range(start, start + count):
                                single = await read_fn(client, addr, 1)
                                if single is None:
                                    continue
                                name = addr_to_name.get(addr)
                                if not name:
                                    continue
                                value = single[0]
                                if reg_type in ("input_registers", "holding_registers"):
                                    if self._is_valid_register_value(name, value):
                                        self.available_registers[reg_type].add(name)
                                else:
                                    self.available_registers[reg_type].add(name)
                        continue
                    for offset, value in enumerate(values):
                        addr = start + offset
                        name = addr_to_name.get(addr)
                        if not name:
                            continue
                        if reg_type in ("input_registers", "holding_registers"):
                            if self._is_valid_register_value(name, value):
                                self.available_registers[reg_type].add(name)
                        else:
                            self.available_registers[reg_type].add(name)

                present_blocks[reg_type] = (addresses[0], addresses[-1])

            # Dynamically scan registers based on CSV definitions
            csv_register_maps = {
                "input_registers": ("04", self._read_input),
                "holding_registers": ("03", self._read_holding),
                "coil_registers": ("01", self._read_coil),
                "discrete_inputs": ("02", self._read_discrete),
            }

            for reg_type, (code, read_fn) in csv_register_maps.items():
                addr_to_name = self._registers.get(code, {})
                addresses = sorted(addr_to_name)
                if self.skip_known_missing:
                    addresses = [
                        a
                        for a in addresses
                        if addr_to_name[a] not in KNOWN_MISSING_REGISTERS.get(reg_type, set())
                    ]
                if reg_type == "holding_registers" and not self.scan_uart_settings:
                    addresses = [a for a in addresses if a not in UART_OPTIONAL_REGS]
                if not addresses:
                    continue

                for start, count in self._group_registers_for_batch_read(addresses):
                    values = await read_fn(client, start, count)
                    if values is None:
                        for addr in range(start, start + count):
                            single = await read_fn(client, addr, 1)
                            if single is None:
                                _LOGGER.debug("Failed to read %s register 0x%04X", reg_type, addr)
                                continue
                            reg_name = addr_to_name.get(addr)
                            if not reg_name:
                                continue
                            value = single[0]
                            if reg_type in ("input_registers", "holding_registers"):
                                if self._is_valid_register_value(reg_name, value):
                                    self.available_registers[reg_type].add(reg_name)
                            else:
                                self.available_registers[reg_type].add(reg_name)
                        if count > 1:
                            for addr in range(start, start + count):
                                single = await read_fn(client, addr, 1)
                                if single is None:
                                    continue
                                reg_name = addr_to_name.get(addr)
                                if not reg_name:
                                    continue
                                value = single[0]
                                if reg_type in ("input_registers", "holding_registers"):
                                    if self._is_valid_register_value(reg_name, value):
                                        self.available_registers[reg_type].add(reg_name)
                                else:
                                    self.available_registers[reg_type].add(reg_name)
                        continue
                    for offset, value in enumerate(values):
                        addr = start + offset
                        reg_name = addr_to_name.get(addr)
                        if not reg_name:
                            continue
                        if reg_type in ("input_registers", "holding_registers"):
                            if self._is_valid_register_value(reg_name, value):
                                self.available_registers[reg_type].add(reg_name)
                        else:
                            self.available_registers[reg_type].add(reg_name)

            # Analyze capabilities once all register scans are complete
            caps = self._analyze_capabilities()

            # Copy the discovered register address blocks so they can be returned
            register_blocks = present_blocks.copy()
            _LOGGER.info(
                "Device scan completed: %d registers detected, %d capabilities detected",
                sum(len(v) for v in self.available_registers.values()),
                sum(
                    1 for v in caps.as_dict().values() if bool(v) and not isinstance(v, (set, int))
                ),
            )

            return info, caps, register_blocks

        except (ModbusException, ConnectionException) as exc:
            _LOGGER.exception("Device scan failed: %s", exc)
            raise
        except (OSError, asyncio.TimeoutError, ValueError) as exc:
            _LOGGER.exception("Unexpected error during device scan: %s", exc)
            raise

    async def scan_device(self) -> Dict[str, Any]:
        """Scan device and return formatted result - compatible with coordinator."""
        try:
            info, caps, blocks = await self.scan()

            # Count total available registers
            register_count = sum(len(regs) for regs in self.available_registers.values())

            result = {
                "device_info": {
                    "device_name": f"ThesslaGreen {info.model}",
                    "model": info.model,
                    "firmware": info.firmware,
                    "serial_number": info.serial_number,
                },
                "capabilities": caps.as_dict(),
                "available_registers": self.available_registers,
                "register_count": register_count,
                "scan_blocks": blocks,
            }

            _LOGGER.info(
                "Device scan successful: %s v%s, %d registers, %d capabilities",
                info.model,
                info.firmware,
                register_count,
                sum(
                    1 for v in caps.as_dict().values() if bool(v) and not isinstance(v, (set, int))
                ),
            )

            return result

        except (ConnectionException, ModbusException) as exc:
            _LOGGER.exception("Connection failed during device scan: %s", exc)
            raise
        except (OSError, asyncio.TimeoutError, ValueError) as exc:
            _LOGGER.exception("Device scan failed: %s", exc)
            raise
        finally:
            await self.close()

    async def close(self):
        """Close the scanner connection if any."""
        if self._client is not None:
            try:
                result = self._client.close()
                if inspect.isawaitable(result):
                    await result
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug("Error closing Modbus client: %s", exc, exc_info=True)
            except OSError as exc:
                _LOGGER.debug("Unexpected error closing Modbus client: %s", exc, exc_info=True)

        self._client = None
        _LOGGER.debug("Disconnected from ThesslaGreen device")

    def _group_registers_for_batch_read(
        self, addresses: List[int], max_gap: int = 10
    ) -> List[Tuple[int, int]]:
        """Group registers for batch reading optimization."""
        if not addresses:
            return []

        groups = []
        current_start = addresses[0]
        current_end = addresses[0]

        for addr in addresses[1:]:
            if (
                addr - current_end <= max_gap
                and current_end - current_start + 1 < MAX_BATCH_REGISTERS
            ):
                current_end = addr
            else:
                groups.append((current_start, current_end - current_start + 1))
                current_start = addr
                current_end = addr

        groups.append((current_start, current_end - current_start + 1))
        return groups


# Legacy compatibility - ThesslaDeviceScanner alias
ThesslaDeviceScanner = ThesslaGreenDeviceScanner
