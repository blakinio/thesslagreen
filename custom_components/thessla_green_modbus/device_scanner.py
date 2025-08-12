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

from .modbus_exceptions import ConnectionException, ModbusException

if TYPE_CHECKING:  # pragma: no cover
    from pymodbus.client import AsyncModbusTcpClient

from .const import COIL_REGISTERS, DEFAULT_SLAVE_ID, DISCRETE_INPUT_REGISTERS, SENSOR_UNAVAILABLE
from .modbus_helpers import _call_modbus
from .registers import HOLDING_REGISTERS, INPUT_REGISTERS

_LOGGER = logging.getLogger(__name__)


def _to_snake_case(name: str) -> str:
    """Convert register names to snake_case."""
    replacements = {"flowrate": "flow_rate"}
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = re.sub(r"[\s\-/]", "_", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"(?<=\D)(\d)", r"_\1", name)
    name = re.sub(r"__+", "_", name)
    name = name.lower()
    token_map = {"temp": "temperature"}
    tokens = [token_map.get(token, token) for token in name.split("_")]
    return "_".join(tokens)


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

    def as_dict(self) -> Dict:
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

        # Load register map from CSV
        self._registers: Dict[str, Dict[int, str]] = self._load_registers()

        # Keep track of the Modbus client so it can be closed later
        self._client: Optional["AsyncModbusTcpClient"] = None

    def _load_registers(self) -> Dict[str, Dict[int, str]]:
        """Load Modbus register definitions from CSV file."""
        register_map: Dict[str, Dict[int, str]] = {"03": {}, "04": {}, "01": {}, "02": {}}
        csv_path = files(__package__) / "data" / "modbus_registers.csv"
        try:
            with csv_path.open(newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    code = row.get("Function_Code")
                    if not code or code.startswith("#"):
                        continue
                    name = _to_snake_case(row.get("Register_Name", ""))
                    try:
                        addr = int(row.get("Address_DEC", 0))
                    except (TypeError, ValueError):
                        continue
                    if code in register_map:
                        if addr in register_map[code]:
                            _LOGGER.warning(
                                "Duplicate register address %s for function code %s: %s", addr, code, name
                            )
                            continue
                        register_map[code][addr] = name
        except FileNotFoundError:
            _LOGGER.error("Register definition file not found: %s", csv_path)
        return register_map

    async def _read_input(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[int]]:
        """Read input registers."""
        try:
            response = await _call_modbus(
                client.read_input_registers, self.slave_id, address, count=count
            )
            if not response.isError():
                return response.registers
        except (ModbusException, ConnectionException) as exc:
            _LOGGER.debug("Failed to read input 0x%04X: %s", address, exc, exc_info=True)
        except (OSError, asyncio.TimeoutError) as exc:
            _LOGGER.error("Unexpected error reading input 0x%04X: %s", address, exc, exc_info=True)
        return None

    async def _read_holding(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[int]]:
        """Read holding registers."""
        try:
            response = await _call_modbus(
                client.read_holding_registers, self.slave_id, address, count=count
            )
            if not response.isError():
                return response.registers
        except (ModbusException, ConnectionException) as exc:
            _LOGGER.debug("Failed to read holding 0x%04X: %s", address, exc, exc_info=True)
        except (OSError, asyncio.TimeoutError) as exc:
            _LOGGER.error(
                "Unexpected error reading holding 0x%04X: %s", address, exc, exc_info=True
            )
        return None

    async def _read_coil(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[bool]]:
        """Read coil registers."""
        try:
            response = await _call_modbus(client.read_coils, self.slave_id, address, count=count)
            if not response.isError():
                return response.bits[:count]
        except (ModbusException, ConnectionException) as exc:
            _LOGGER.debug("Failed to read coil 0x%04X: %s", address, exc, exc_info=True)
        except (OSError, asyncio.TimeoutError) as exc:
            _LOGGER.error("Unexpected error reading coil 0x%04X: %s", address, exc, exc_info=True)
        return None

    async def _read_discrete(
        self, client: "AsyncModbusTcpClient", address: int, count: int
    ) -> Optional[List[bool]]:
        """Read discrete input registers."""
        try:
            response = await _call_modbus(
                client.read_discrete_inputs, self.slave_id, address, count=count
            )
            if not response.isError():
                return response.bits[:count]
        except (ModbusException, ConnectionException) as exc:
            _LOGGER.debug("Failed to read discrete 0x%04X: %s", address, exc, exc_info=True)
        except (OSError, asyncio.TimeoutError) as exc:
            _LOGGER.error(
                "Unexpected error reading discrete 0x%04X: %s", address, exc, exc_info=True
            )
        return None

    def _is_valid_register_value(self, register_name: str, value: int) -> bool:
        """Check if register value is valid (not a sensor error/missing value)."""
        # Temperature sensors use a sentinel value to indicate no sensor
        if "temperature" in register_name.lower():
            return value != SENSOR_UNAVAILABLE

        # Air flow sensors use the same sentinel for no sensor
        if any(x in register_name.lower() for x in ["flow", "air_flow", "flow_rate"]):
            return value != SENSOR_UNAVAILABLE and value != 65535

        # Mode values should be in valid range
        if "mode" in register_name.lower():
            return 0 <= value <= 4

        # Default: consider valid
        return True

    def _analyze_capabilities(self) -> DeviceCapabilities:
        """Analyze available registers to determine device capabilities."""
        caps = DeviceCapabilities()

        # Constant flow detection
        caps.constant_flow = any(
            "constant_flow" in reg or "cf_" in reg
            for reg in (
                self.available_registers["input_registers"].union(
                    self.available_registers["holding_registers"]
                )
            )
        )

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

        # Flow sensors (simple pattern match)
        caps.flow_sensors = {
            reg for reg in self.available_registers["input_registers"] if "flow" in reg
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

        # Weekly schedule features
        caps.weekly_schedule = any(
            "schedule" in reg.lower() or "weekly" in reg.lower()
            for registers in self.available_registers.values()
            for reg in registers
        )

        # Basic control availability
        caps.basic_control = "mode" in self.available_registers["holding_registers"]

        # Special functions from discrete inputs
        for func in ["fireplace", "airing_switch"]:
            if func in self.available_registers["discrete_inputs"]:
                caps.special_functions.add(func)

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
            if addr - current_end <= max_gap and current_end - current_start + 1 < 16:
                current_end = addr
            else:
                groups.append((current_start, current_end - current_start + 1))
                current_start = addr
                current_end = addr

        groups.append((current_start, current_end - current_start + 1))
        return groups


# Legacy compatibility - ThesslaDeviceScanner alias
ThesslaDeviceScanner = ThesslaGreenDeviceScanner
