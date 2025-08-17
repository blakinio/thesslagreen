"""Device scanner for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import csv
import logging
import re
import inspect
from dataclasses import asdict, dataclass, field
from importlib.resources import files
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

from .utils import (
    BCD_TIME_PREFIXES,
    TIME_REGISTER_PREFIXES,
    _decode_bcd_time,
    _decode_register_time,
    _to_snake_case,
)
from .const import COIL_REGISTERS, DEFAULT_SLAVE_ID, DISCRETE_INPUT_REGISTERS
from .modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple

from .const import COIL_REGISTERS, DEFAULT_SLAVE_ID, DISCRETE_INPUT_REGISTERS
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import _call_modbus
from .registers import HOLDING_REGISTERS, INPUT_REGISTERS

if TYPE_CHECKING:  # pragma: no cover
    from pymodbus.client import AsyncModbusTcpClient

if TYPE_CHECKING:  # pragma: no cover
    from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)

# Specific registers may only accept discrete values
REGISTER_ALLOWED_VALUES: dict[str, set[int]] = {
    "mode": {0, 1, 2},
    "season_mode": {0, 1},
    "special_mode": set(range(0, 12)),
    "antifreeze_mode": {0, 1},
}


# Registers storing combined airflow and temperature settings
SETTING_PREFIX = "setting_"


def _decode_setting_value(value: int) -> tuple[int, float] | None:
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

    if name == "manual_airing_time_to_start":
        raw_value = value
        value = ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
        decoded = _decode_register_time(value)
        if decoded is None:
            return f"0x{raw_value:04X} (invalid)"
        return f"{decoded // 60:02d}:{decoded % 60:02d}"

    if name.startswith(BCD_TIME_PREFIXES):
        decoded = _decode_bcd_time(value)
        if decoded is None:
            return f"0x{value:04X} (invalid)"
        return f"{decoded // 60:02d}:{decoded % 60:02d}"

    if name.startswith(TIME_REGISTER_PREFIXES):
        decoded = _decode_register_time(value)
        if decoded is None:
            return f"0x{value:04X} (invalid)"
        return f"{decoded // 60:02d}:{decoded % 60:02d}"

    if name.startswith(SETTING_PREFIX):
        decoded = _decode_setting_value(value)
        if decoded is None:
            return value
        airflow, temp = decoded
        temp_str = f"{temp:g}"
        return f"{airflow}% @ {temp_str}°C"

    return value


def _decode_season_mode(value: int) -> Optional[int]:
    """Decode season mode register which may place value in high byte."""
    if value in (0xFF00, 0xFFFF):
        return None
    high = (value >> 8) & 0xFF
    low = value & 0xFF
    if high and low:
        return None
    return high or low


SPECIAL_VALUE_DECODERS: Dict[str, Callable[[int], Optional[int]]] = {
    "season_mode": _decode_season_mode,
}


# Maximum registers per batch read (Modbus limit)
MAX_BATCH_REGISTERS = 16

# Optional UART configuration registers (Air-B and Air++ ports)
# According to the Series 4 Modbus documentation, both the Air-B
# (0x1164-0x1167) and Air++ (0x1168-0x116B) register blocks are
# optional and may be absent on devices without the corresponding
# hardware. They are skipped by default unless UART scanning is
# explicitly enabled.
UART_OPTIONAL_REGS = range(0x1164, 0x116C)


@dataclass
class DeviceInfo:
    """Basic identifying information about a ThesslaGreen unit.

    Attributes:
        model: Reported model name used to identify the device type.
        firmware: Firmware version string for compatibility checks.
        serial_number: Unique hardware identifier for the unit.
    """

    model: str = "Unknown AirPack"
    firmware: str = "Unknown"
    serial_number: str = "Unknown"
    firmware_available: bool = True
    capabilities: list[str] = field(default_factory=list)


@dataclass
class DeviceCapabilities:
    """Feature flags and sensor availability detected on the device.

    Each attribute indicates whether a hardware capability or sensor is
    available, allowing the integration to enable or disable related
    features dynamically.

    Attributes:
        basic_control: Support for fundamental fan and temperature control.
        temperature_sensors: Names of built-in temperature sensors.
        flow_sensors: Names of sensors measuring airflow.
        special_functions: Additional reported feature flags.
        expansion_module: Presence of an expansion module.
        constant_flow: Ability to maintain constant airflow.
        gwc_system: Ground heat exchanger integration.
        bypass_system: Motorized bypass capability.
        heating_system: Support for heating modules.
        cooling_system: Support for cooling modules.
        air_quality: Availability of air quality sensors.
        weekly_schedule: Built-in weekly scheduling support.
        sensor_outside_temperature: Outside temperature sensor present.
        sensor_supply_temperature: Supply air temperature sensor present.
        sensor_exhaust_temperature: Exhaust air temperature sensor present.
        sensor_fpx_temperature: FPX (preheater) temperature sensor present.
        sensor_duct_supply_temperature: Duct supply temperature sensor present.
        sensor_gwc_temperature: GWC (ground heat exchanger) temperature sensor present.
        sensor_ambient_temperature: Ambient room temperature sensor present.
        sensor_heating_temperature: Heating system temperature sensor present.
        temperature_sensors_count: Total number of available temperature sensors.
    """

    basic_control: bool = False
    temperature_sensors: set[str] = field(default_factory=set)  # Names of temperature sensors
    flow_sensors: set[str] = field(default_factory=set)  # Airflow sensor identifiers
    special_functions: set[str] = field(default_factory=set)  # Optional feature flags
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
        self.available_registers: dict[str, set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

        # Placeholder for register map, value ranges and firmware versions loaded
        # asynchronously
        self._registers: Dict[str, Dict[int, str]] = {}
        self._register_ranges: Dict[str, Tuple[Optional[int], Optional[int]]] = {}
        self._register_versions: Dict[str, Tuple[int, ...]] = {}

        # Track holding registers that consistently fail to respond so we
        # can avoid retrying them repeatedly during scanning. The value is
        # a failure counter per register address.
        self._holding_failures: dict[int, int] = {}
        # Cache holding registers that have exceeded retry attempts
        self._failed_holding: set[int] = set()

        # Track input registers that consistently fail to respond so we can
        # avoid retrying them repeatedly during scanning
        self._input_failures: dict[int, int] = {}
        self._failed_input: set[int] = set()
        # Track ranges that have already been logged as skipped in the current scan
        self._input_skip_log_ranges: set[tuple[int, int]] = set()

        # Cache register ranges that returned Modbus exception codes 2-4 so
        # they can be skipped on subsequent reads without additional warnings
        self._unsupported_input_ranges: dict[tuple[int, int], int] = {}
        self._unsupported_holding_ranges: dict[tuple[int, int], int] = {}

        # Keep track of the Modbus client so it can be closed later
        self._client: "AsyncModbusTcpClient" | None = None

        # Track registers for which invalid values have been reported
        self._reported_invalid: set[str] = set()

    async def _async_setup(self) -> None:
        """Asynchronously load register definitions."""
        result = await self._load_registers()
        if len(result) == 3:
            self._registers, self._register_ranges, self._register_versions = result
        else:
            self._registers, self._register_ranges = result  # type: ignore[misc]
            self._register_versions = {}

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

    async def close(self) -> None:
        """Close the underlying Modbus client connection."""
        client = self._client
        # Prevent further use even if closing fails
        self._client = None
        if client is None:
            return
        try:
            result = client.close()
            if inspect.isawaitable(result):
                await result
        except (OSError, ConnectionException, ModbusIOException):
            _LOGGER.debug("Error closing Modbus client", exc_info=True)

    async def _load_registers(
        self,
    ) -> Tuple[
        Dict[str, Dict[int, str]],
        Dict[str, Tuple[Optional[int], Optional[int]]],
        Dict[str, Tuple[int, ...]],
    ]:
        """Load Modbus register definitions, ranges and firmware versions."""
        csv_path = files(__package__) / "data" / "modbus_registers.csv"

        def _parse_csv() -> Tuple[
            Dict[str, Dict[int, str]],
            Dict[str, Tuple[Optional[int], Optional[int]]],
            Dict[str, Tuple[int, ...]],
        ]:
            register_map: Dict[str, Dict[int, str]] = {"03": {}, "04": {}, "01": {}, "02": {}}
            register_ranges: Dict[str, Tuple[Optional[int], Optional[int]]] = {}
            register_versions: Dict[str, Tuple[int, ...]] = {}
            try:
                with csv_path.open(newline="", encoding="utf-8") as csvfile:
                    reader = csv.DictReader(csvfile)
                    rows: Dict[
                        str,
                        List[
                            Tuple[str, int, Optional[int], Optional[int], Optional[Tuple[int, ...]]]
                        ],
                    ] = {"03": [], "04": [], "01": [], "02": []}
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
                        version_raw = row.get("Software_Version")

                        def _parse_range(label: str, raw: str | None) -> int | None:
                            if raw in (None, ""):
                                return None
                            text = str(raw).split("#", 1)[0].strip()
                            if not text or not re.fullmatch(
                                r"[+-]?(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?)",
                                text,
                            ):
                                _LOGGER.warning(
                                    "Ignoring non-numeric %s for %s: %s", label, name, raw
                                )
                                return None
                            try:
                                return (
                                    int(text, 0)
                                    if text.lower().startswith(("0x", "+0x", "-0x"))
                                    else int(float(text))
                                )
                            except ValueError:
                                _LOGGER.warning(
                                    "Ignoring non-numeric %s for %s: %s", label, name, raw
                                )
                                return None

                        min_val = _parse_range("Min", min_raw)
                        max_val = _parse_range("Max", max_raw)
                        if (min_raw not in (None, "") or max_raw not in (None, "")) and (
                            min_val is None or max_val is None
                        ):
                            _LOGGER.warning(
                                "Incomplete range for %s: Min=%s Max=%s", name, min_raw, max_raw
                            )

                        if name.startswith(BCD_TIME_PREFIXES):
                            min_val = (min_val * 100) if min_val is not None else 0
                            max_val = (max_val * 100) if max_val is not None else 2359

                        version_tuple: Optional[Tuple[int, ...]] = None
                        if version_raw:
                            try:
                                version_tuple = tuple(
                                    int(part) for part in str(version_raw).split(".")
                                )
                            except ValueError:
                                version_tuple = None

                        rows[code].append((name, addr, min_val, max_val, version_tuple))

                    for code, items in rows.items():
                        items.sort(key=lambda item: item[1])
                        counts: Dict[str, int] = {}
                        for name, *_ in items:
                            counts[name] = counts.get(name, 0) + 1

                        seen: Dict[str, int] = {}
                        for name, addr, min_val, max_val, ver in items:
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
                            if ver is not None:
                                register_versions[name] = ver

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
            return register_map, register_ranges, register_versions

        return await asyncio.to_thread(_parse_csv)


async def _read_input(
    self,
    client: "AsyncModbusTcpClient",
    address: int,
    count: int,
    *,
    skip_cache: bool = False,
    log_exceptions: bool = True,
) -> list[int] | None:
    """Read input registers with retry and backoff.

    ``skip_cache`` is used when probing individual registers after a block
    read failed. When ``True`` the cached set of failed registers is not
    checked, allowing each register to be queried once before being cached
    as missing.
    """
    start = address
    end = address + count - 1

    for skip_start, skip_end in self._unsupported_input_ranges:
        if skip_start <= start and end <= skip_end:
            return None

    if not skip_cache and any(reg in self._failed_input for reg in range(start, end + 1)):
        first = next(reg for reg in range(start, end + 1) if reg in self._failed_input)
        skip_start = skip_end = first
        while skip_start - 1 in self._failed_input:
            skip_start -= 1
        while skip_end + 1 in self._failed_input:
            skip_end += 1
        if (skip_start, skip_end) not in self._input_skip_log_ranges:
            _LOGGER.debug(
                "Skipping cached failed input registers 0x%04X-0x%04X",
                skip_start,
                skip_end,
            )
            self._input_skip_log_ranges.add((skip_start, skip_end))
        return None

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
            break

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
    self,
    client: "AsyncModbusTcpClient",
    address: int,
    count: int,
    *,
    log_exceptions: bool = True,
) -> list[int] | None:
    """Read holding registers with retry, backoff and failure tracking."""
    start = address
    end = address + count - 1

    for skip_start, skip_end in self._unsupported_holding_ranges:
        if skip_start <= start and end <= skip_end:
            return None

    if address in self._failed_holding:
        _LOGGER.debug("Skipping cached failed holding register 0x%04X", address)
        return None

    failures = self._holding_failures.get(address, 0)
    if failures >= self.retry:
        _LOGGER.warning("Skipping unsupported holding register 0x%04X", address)
        return None

    exception_code: int | None = None
    for attempt in range(1, self.retry + 1):
        try:
            response = await _call_modbus(
                client.read_holding_registers, self.slave_id, address, count=count
            )
            if response is not None:
                if response.isError():
                    exception_code = getattr(response, "exception_code", None)
                    break
                if address in self._holding_failures:
                    del self._holding_failures[address]
                return response.registers
        except (ModbusException, ConnectionException, asyncio.TimeoutError) as exc:
            _LOGGER.debug(
                "Failed to read holding 0x%04X (attempt %d/%d): %s",
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
        except asyncio.CancelledError:
            _LOGGER.debug(
                "Cancelled reading holding 0x%04X on attempt %d/%d",
                address,
                attempt,
                self.retry,
            )
            raise
        except OSError as exc:
            _LOGGER.error(
                "Unexpected error reading holding 0x%04X on attempt %d: %s",
                address,
                attempt,
                exc,
                exc_info=True,
            )
            break

        if attempt < self.retry and exception_code is None:
            try:
                await asyncio.sleep((self.backoff or 1) * 2 ** (attempt - 1))
            except asyncio.CancelledError:
                _LOGGER.debug("Sleep cancelled while retrying holding 0x%04X", address)
                raise

    if exception_code is not None:
        self._failed_holding.update(range(start, end + 1))
        new_range = (start, end) not in self._unsupported_holding_ranges
        self._unsupported_holding_ranges[(start, end)] = exception_code
        if log_exceptions and new_range:
            _LOGGER.warning(
                "Skipping unsupported holding registers 0x%04X-0x%04X (exception code %d)",
                start,
                end,
                exception_code,
            )
        return None

    _LOGGER.warning(
        "Failed to read holding registers 0x%04X-0x%04X after %d retries",
        start,
        end,
        self.retry,
    )
    return None


async def _read_coil(
    self,
    client: "AsyncModbusTcpClient",
    address: int,
    count: int,
) -> list[bool] | None:
    """Read coil registers with retry and backoff."""
    for attempt in range(1, self.retry + 1):
        try:
            response = await _call_modbus(client.read_coils, self.slave_id, address, count=count)
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
        except asyncio.CancelledError:
            _LOGGER.debug(
                "Cancelled reading coil 0x%04X on attempt %d",
                address,
                attempt,
            )
            raise
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
            try:
                await asyncio.sleep(2 ** (attempt - 1))
            except asyncio.CancelledError:
                _LOGGER.debug("Sleep cancelled while retrying coil 0x%04X", address)
                raise
    return None


async def _read_discrete(
    self,
    client: "AsyncModbusTcpClient",
    address: int,
    count: int,
) -> list[bool] | None:
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
        except asyncio.CancelledError:
            _LOGGER.debug(
                "Cancelled reading discrete 0x%04X on attempt %d",
                address,
                attempt,
            )
            raise
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
            try:
                await asyncio.sleep(2 ** (attempt - 1))
            except asyncio.CancelledError:
                _LOGGER.debug("Sleep cancelled while retrying discrete 0x%04X", address)
                raise
    return None
