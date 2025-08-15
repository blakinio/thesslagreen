"""Device scanner for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import csv
import inspect
import logging
from dataclasses import asdict, dataclass, field
from importlib.resources import files
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from .modbus_exceptions import ConnectionException, ModbusException

if TYPE_CHECKING:  # pragma: no cover
    from pymodbus.client import AsyncModbusTcpClient

from .const import COIL_REGISTERS, DEFAULT_SLAVE_ID, DISCRETE_INPUT_REGISTERS, SENSOR_UNAVAILABLE
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

# Registers storing times as BCD HHMM values
BCD_TIME_PREFIXES: Tuple[str, ...] = (
    "schedule_",
    "setting_",
    "airing_",
    "manual_airing_",
)


def _decode_bcd_time(value: int) -> Optional[int]:
    """Decode a BCD encoded HHMM value to an integer.

    Each nibble is treated as a separate decimal digit.  If any nibble is
    greater than 9 the value is considered malformed and ``None`` is returned.
    The device represents midnight at the end of the day as ``0x2400`` which
    is treated as ``00:00``.
    """

    h_tens = (value >> 12) & 0xF
    h_units = (value >> 8) & 0xF
    m_tens = (value >> 4) & 0xF
    m_units = value & 0xF
    if any(n > 9 for n in (h_tens, h_units, m_tens, m_units)):
        return None
    hours = h_tens * 10 + h_units
    minutes = m_tens * 10 + m_units
    if hours == 24 and minutes == 0:
        return 0
    if hours > 23 or minutes > 59:
        return None
    return hours * 100 + minutes


# Maximum registers per batch read (Modbus limit)
MAX_BATCH_REGISTERS = 16


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
    ) -> None:
        """Initialize device scanner with consistent parameter names."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry

        # Available registers storage
        self.available_registers: Dict[str, Set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

        # Placeholder for register map and value ranges loaded asynchronously
        self._registers: Dict[str, Dict[int, str]] = {}
        self._register_ranges: Dict[str, Tuple[Optional[int], Optional[int]]] = {}

        # Keep track of the Modbus client so it can be closed later
        self._client: Optional["AsyncModbusTcpClient"] = None

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
    ) -> "ThesslaGreenDeviceScanner":
        """Factory to create an initialized scanner instance."""
        self = cls(host, port, slave_id, timeout, retry)
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
                        min_val: Optional[int]
                        max_val: Optional[int]
                        try:
                            min_val = int(float(min_raw)) if min_raw not in (None, "") else None
                        except ValueError:
                            min_val = None
                        try:
                            max_val = int(float(max_raw)) if max_raw not in (None, "") else None
                        except ValueError:
                            max_val = None

                        # Adjust ranges for registers storing BCD times
                        if name.startswith(BCD_TIME_PREFIXES):
                            min_val = (min_val * 100) if min_val is not None else 0
                            max_val = (max_val * 100) if max_val is not None else 2359

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
            except FileNotFoundError:
                _LOGGER.error("Register definition file not found: %s", csv_path)
            return register_map, register_ranges

        return await asyncio.to_thread(_read_csv)

    async def _read_input(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[int]]:
        """Read input registers with retry logic."""
        for attempt in range(1, self.retry + 1):
            try:
                response = await _call_modbus(
                    client.read_input_registers, self.slave_id, address, count=count
                )
                if response is not None and not response.isError():
                    return response.registers
                _LOGGER.debug(
                    "Attempt %d failed to read input 0x%04X: %s",
                    attempt,
                    address,
                    response,
                )
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Attempt %d failed to read input 0x%04X: %s",
                    attempt,
                    address,
                    exc,
                    exc_info=True,
                )
            except (OSError, asyncio.TimeoutError) as exc:
                _LOGGER.error(
                    "Unexpected error reading input 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            # Fallback to holding registers if input read fails
            _LOGGER.debug(
                "Falling back to holding registers for input 0x%04X (attempt %d)",
                address,
                attempt,
            )
            try:
                response = await _call_modbus(
                    client.read_holding_registers, self.slave_id, address, count=count
                )
                if response is not None and not response.isError():
                    return response.registers
                _LOGGER.debug(
                    "Fallback attempt %d failed to read holding 0x%04X: %s",
                    attempt,
                    address,
                    response,
                )
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Fallback attempt %d failed to read holding 0x%04X: %s",
                    attempt,
                    address,
                    exc,
                    exc_info=True,
                )
            except (OSError, asyncio.TimeoutError) as exc:
                _LOGGER.error(
                    "Unexpected error reading holding 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            if attempt < self.retry:
                await asyncio.sleep(0.5)
        return None

    async def _read_holding(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[int]]:
        """Read holding registers with retry logic and exponential backoff."""

        delay = 0.5
        last_error: Optional[Exception] = None

        for attempt in range(1, self.retry + 1):
            try:
                response = await _call_modbus(
                    client.read_holding_registers, self.slave_id, address, count=count
                )
                if response is not None and not response.isError():
                    return response.registers

                if response is None:
                    last_error = ConnectionException("No response")
                _LOGGER.debug(
                    "Attempt %d failed to read holding 0x%04X: %s",
                    attempt,
                    address,
                    response,
                )
            except (ModbusException, ConnectionException) as exc:
                last_error = exc
                _LOGGER.debug(
                    "Attempt %d failed to read holding 0x%04X: %s",
                    attempt,
                    address,
                    exc,
                    exc_info=True,
                )
            except (OSError, asyncio.TimeoutError) as exc:
                last_error = exc
                _LOGGER.error(
                    "Unexpected error reading holding 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            if attempt < self.retry:
                await asyncio.sleep(delay)
                delay *= 2

        if last_error is not None:
            _LOGGER.error(
                "Failed to read holding 0x%04X after %d attempts: %s",
                address,
                self.retry,
                last_error,
            )
            raise ConnectionException(
                f"Failed to read holding 0x{address:04X}: {last_error}"
            ) from last_error

        _LOGGER.error("Failed to read holding 0x%04X after %d attempts", address, self.retry)
        return None

    async def _read_coil(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[bool]]:
        """Read coil registers with retry logic."""
        for attempt in range(1, self.retry + 1):
            try:
                response = await _call_modbus(
                    client.read_coils, self.slave_id, address, count=count
                )
                if response is not None and not response.isError():
                    return response.bits[:count]
                _LOGGER.debug(
                    "Attempt %d failed to read coil 0x%04X: %s",
                    attempt,
                    address,
                    response,
                )
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Attempt %d failed to read coil 0x%04X: %s",
                    attempt,
                    address,
                    exc,
                    exc_info=True,
                )
            except (OSError, asyncio.TimeoutError) as exc:
                _LOGGER.error(
                    "Unexpected error reading coil 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break
            if attempt < self.retry:
                await asyncio.sleep(0.5)
        return None

    async def _read_discrete(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[bool]]:
        """Read discrete input registers with retry logic."""
        for attempt in range(1, self.retry + 1):
            try:
                response = await _call_modbus(
                    client.read_discrete_inputs, self.slave_id, address, count=count
                )
                if response is not None and not response.isError():
                    return response.bits[:count]
                _LOGGER.debug(
                    "Attempt %d failed to read discrete 0x%04X: %s",
                    attempt,
                    address,
                    response,
                )
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Attempt %d failed to read discrete 0x%04X: %s",
                    attempt,
                    address,
                    exc,
                    exc_info=True,
                )
            except (OSError, asyncio.TimeoutError) as exc:
                _LOGGER.error(
                    "Unexpected error reading discrete 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break
            if attempt < self.retry:
                await asyncio.sleep(0.5)
        return None

    def _is_valid_register_value(self, register_name: str, value: int) -> bool:
        """Check if register value is valid (not a sensor error/missing value)."""
        name = register_name.lower()

        # Decode BCD time values before validation
        if name.startswith(BCD_TIME_PREFIXES):
            decoded = _decode_bcd_time(value)
            if decoded is None:
                _LOGGER.debug("Invalid BCD time for %s: %s", register_name, value)
                return False
            value = decoded

        # Temperature sensors may report a sentinel value when the sensor is unavailable.
        # Log the condition but still treat the register as valid so it is discovered.
        if "temperature" in name:
            if value == SENSOR_UNAVAILABLE:
                _LOGGER.debug("Sensor unavailable for %s: %s", register_name, value)
            return True

        # Air flow sensors use the same sentinel for no sensor
        if any(x in name for x in ["flow", "air_flow", "flow_rate"]):
            if value in (SENSOR_UNAVAILABLE, 65535):
                _LOGGER.debug("Invalid value for %s: %s", register_name, value)
                return False
            return True

        # Discrete allowed values for specific registers
        if name in REGISTER_ALLOWED_VALUES:
            if value not in REGISTER_ALLOWED_VALUES[name]:
                _LOGGER.debug("Invalid value for %s: %s", register_name, value)
                return False
            return True

        # Use range from CSV if available
        if name in self._register_ranges:
            min_val, max_val = self._register_ranges[name]
            if min_val is not None and value < min_val:
                _LOGGER.debug("Invalid value for %s: %s", register_name, value)
                return False
            if max_val is not None and value > max_val:
                _LOGGER.debug("Invalid value for %s: %s", register_name, value)
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

            info = DeviceInfo()
            present_blocks = {}
            # Read firmware version
            fw_data = await self._read_input(client, 0x0000, 5)
            if fw_data and len(fw_data) >= 3:
                fw = f"{fw_data[0]}.{fw_data[1]}.{fw_data[2]}"
                info.firmware = fw
                _LOGGER.debug("Firmware version: %s", fw)

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
                if not addresses:
                    continue

                for start, count in self._group_registers_for_batch_read(addresses):
                    values = await read_fn(client, start, count)
                    if values is None:
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
                if not addresses:
                    continue

                for start, count in self._group_registers_for_batch_read(addresses):
                    values = await read_fn(client, start, count)
                    if values is None:
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
                    1
                    for v in caps.as_dict().values()
                    if (isinstance(v, bool) and v)
                    or (bool(v) and not isinstance(v, (set, int, bool)))
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
                    1
                    for v in caps.as_dict().values()
                    if (isinstance(v, bool) and v)
                    or (bool(v) and not isinstance(v, (set, int, bool)))
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
