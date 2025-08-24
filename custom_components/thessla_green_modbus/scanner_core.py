"""Device scanner for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import inspect
import logging
import collections.abc
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Self, cast

from .capability_rules import CAPABILITY_PATTERNS
from .const import (
    DEFAULT_SLAVE_ID,
    KNOWN_MISSING_REGISTERS,
    SENSOR_UNAVAILABLE,
    SENSOR_UNAVAILABLE_REGISTERS,
    UNKNOWN_MODEL,
)
from .modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from .modbus_helpers import _call_modbus, group_reads as _group_reads
from .registers import get_all_registers
from .utils import _decode_bcd_time, BCD_TIME_PREFIXES
from .scanner_helpers import (
    REGISTER_ALLOWED_VALUES,
    _format_register_value,
    MAX_BATCH_REGISTERS,
    UART_OPTIONAL_REGS,
    SAFE_REGISTERS,
)

if TYPE_CHECKING:  # pragma: no cover
    from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)

# Register definition caches - populated lazily
REGISTER_DEFINITIONS: dict[str, Any] = {}
INPUT_REGISTERS: dict[str, int] = {}
HOLDING_REGISTERS: dict[str, int] = {}
COIL_REGISTERS: dict[str, int] = {}
DISCRETE_INPUT_REGISTERS: dict[str, int] = {}
MULTI_REGISTER_SIZES: dict[str, int] = {}


def _build_register_maps() -> None:
    """Populate register lookup maps from current register definitions."""
    regs = get_all_registers()

    REGISTER_DEFINITIONS.clear()
    REGISTER_DEFINITIONS.update({r.name: r for r in regs})

    INPUT_REGISTERS.clear()
    INPUT_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == "04"}
    )

    HOLDING_REGISTERS.clear()
    HOLDING_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == "03"}
    )

    COIL_REGISTERS.clear()
    COIL_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == "01"}
    )

    DISCRETE_INPUT_REGISTERS.clear()
    DISCRETE_INPUT_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == "02"}
    )

    MULTI_REGISTER_SIZES.clear()
    MULTI_REGISTER_SIZES.update(
        {
            name: reg.length
            for name, reg in REGISTER_DEFINITIONS.items()
            if reg.function == "03" and reg.length > 1
        }
    )


def _ensure_register_maps() -> None:
    """Ensure register lookup maps are populated."""
    if not REGISTER_DEFINITIONS:
        _build_register_maps()


@dataclass
class DeviceInfo(collections.abc.Mapping):  # pragma: no cover
    """Basic identifying information about a ThesslaGreen unit.

    The attributes are populated dynamically and accessed via ``as_dict`` in
    diagnostics; they therefore appear unused in static analysis.

    Attributes:
        device_name: User configured name reported by the unit.
        model: Reported model name used to identify the device type.
        firmware: Firmware version string for compatibility checks.
        serial_number: Unique hardware identifier for the unit.
    """

    device_name: str = "Unknown"
    model: str = UNKNOWN_MODEL
    firmware: str = "Unknown"
    serial_number: str = "Unknown"
    firmware_available: bool = True  # pragma: no cover
    capabilities: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def items(self):
        return self.as_dict().items()

    def keys(self):
        return self.as_dict().keys()

    def values(self):
        return self.as_dict().values()

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self):
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


# Attributes of this dataclass are read dynamically at runtime to determine
# which features the device exposes; static analysis may therefore mark them
# as unused even though they are relied upon.
@dataclass(slots=True)
class DeviceCapabilities(collections.abc.Mapping):  # pragma: no cover
    """Feature flags and sensor availability detected on the device.

    Although capabilities are typically determined once during the initial scan,
    the dataclass caches the result of :meth:`as_dict` for efficiency. Any
    attribute assignment will clear this cache so subsequent calls reflect the
    new values. The capability sets are mutable; modify them via assignment to
    trigger cache invalidation.
    """
    basic_control: bool = False
    temperature_sensors: set[str] = field(
        default_factory=set
    )  # Names of temperature sensors
    flow_sensors: set[str] = field(
        default_factory=set
    )  # Airflow sensor identifiers  # pragma: no cover
    special_functions: set[str] = field(
        default_factory=set
    )  # Optional feature flags  # pragma: no cover
    expansion_module: bool = False  # pragma: no cover
    constant_flow: bool = False  # pragma: no cover
    gwc_system: bool = False  # pragma: no cover
    bypass_system: bool = False  # pragma: no cover
    heating_system: bool = False  # pragma: no cover
    cooling_system: bool = False  # pragma: no cover
    air_quality: bool = False  # pragma: no cover
    weekly_schedule: bool = False  # pragma: no cover
    sensor_outside_temperature: bool = False  # pragma: no cover
    sensor_supply_temperature: bool = False  # pragma: no cover
    sensor_exhaust_temperature: bool = False  # pragma: no cover
    sensor_fpx_temperature: bool = False  # pragma: no cover
    sensor_duct_supply_temperature: bool = False  # pragma: no cover
    sensor_gwc_temperature: bool = False  # pragma: no cover
    sensor_ambient_temperature: bool = False  # pragma: no cover
    sensor_heating_temperature: bool = False  # pragma: no cover
    temperature_sensors_count: int = 0  # pragma: no cover
    _as_dict_cache: dict[str, Any] | None = field(init=False, repr=False, default=None)

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: D401 - simple cache invalidation
        """Set attribute and invalidate cached ``as_dict`` result."""
        if name != "_as_dict_cache" and getattr(self, "_as_dict_cache", None) is not None:
            object.__setattr__(self, "_as_dict_cache", None)
        object.__setattr__(self, name, value)

    def as_dict(self) -> dict[str, Any]:
        """Return capabilities as a dictionary with set values sorted.

        The result is cached on first call to avoid repeated ``dataclasses.asdict``
        invocations when capabilities are accessed multiple times.
        """

        if self._as_dict_cache is None:
            data = asdict(self)
            for key, value in data.items():
                if isinstance(value, set):
                    data[key] = sorted(value)
            object.__setattr__(self, "_as_dict_cache", data)
        return self._as_dict_cache

    def items(self):
        return self.as_dict().items()

    def keys(self):
        return self.as_dict().keys()

    def values(self):
        return self.as_dict().values()

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self):
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


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
        deep_scan: bool = False,
        full_register_scan: bool = False,
        scan_max_block_size: int = MAX_BATCH_REGISTERS,
    ) -> None:
        """Initialize device scanner with consistent parameter names."""
        _ensure_register_maps()
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        self.backoff = backoff
        self.verbose_invalid_values = verbose_invalid_values
        self.scan_uart_settings = scan_uart_settings
        self.skip_known_missing = skip_known_missing
        self.deep_scan = deep_scan
        self.full_register_scan = full_register_scan
        self.max_block_size = scan_max_block_size

        # Available registers storage
        self.available_registers: dict[str, set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

        # Detected device capabilities
        self.capabilities: DeviceCapabilities = DeviceCapabilities()

        # Placeholder for register map and value ranges loaded asynchronously
        self._registers: Dict[str, Dict[int, str]] = {}
        self._register_ranges: Dict[str, Tuple[Optional[int], Optional[int]]] = {}

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

        # Collect addresses skipped due to Modbus errors or invalid values
        self.failed_addresses: dict[str, dict[str, set[int]]] = {
            "modbus_exceptions": {
                "input_registers": set(),
                "holding_registers": set(),
                "coil_registers": set(),
                "discrete_inputs": set(),
            },
            "invalid_values": {
                "input_registers": set(),
                "holding_registers": set(),
            },
        }

        # Pre-compute addresses of known missing registers for batch grouping
        self._known_missing_addresses: set[int] = set()
        for reg_type, names in KNOWN_MISSING_REGISTERS.items():
            mapping = {
                "input_registers": INPUT_REGISTERS,
                "holding_registers": HOLDING_REGISTERS,
                "coil_registers": COIL_REGISTERS,
                "discrete_inputs": DISCRETE_INPUT_REGISTERS,
            }[reg_type]
            for name in names:
                if (addr := mapping.get(name)) is None:
                    continue
                size = MULTI_REGISTER_SIZES.get(name, 1)
                self._known_missing_addresses.update(range(addr, addr + size))

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
        deep_scan: bool = False,
        full_register_scan: bool = False,
        scan_max_block_size: int = MAX_BATCH_REGISTERS,
    ) -> Self:
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
            deep_scan,
            full_register_scan,
            scan_max_block_size,
        )
        await self._async_setup()

        # Ensure low-level register read helpers are attached to the instance
        # so tests and callers can patch them as needed.
        self._read_holding = cls._read_holding.__get__(self, cls)  # type: ignore[method-assign]
        self._read_coil = cls._read_coil.__get__(self, cls)  # type: ignore[method-assign]
        self._read_discrete = cls._read_discrete.__get__(self, cls)  # type: ignore[method-assign]

        return self

    async def close(self) -> None:
        """Close the underlying Modbus client connection."""

        client = self._client
        if client is None:
            return

        try:
            result = client.close()
            if inspect.isawaitable(result):
                await result
        except (OSError, ConnectionException, ModbusIOException):
            _LOGGER.debug("Error closing Modbus client", exc_info=True)
        finally:
            self._client = None

    async def verify_connection(self) -> None:
        """Verify basic Modbus connectivity by reading a few safe registers.

        A handful of well-known registers are read from the device to confirm
        that the TCP connection and Modbus protocol are functioning. Any
        failure will raise a ``ModbusException`` or ``ConnectionException`` so
        callers can surface an appropriate error to the user.
        """

        from pymodbus.client import AsyncModbusTcpClient

        client = AsyncModbusTcpClient(self.host, port=self.port, timeout=self.timeout)
        try:
            connected = await asyncio.wait_for(client.connect(), timeout=self.timeout)
            if not connected:
                raise ConnectionException("Failed to connect")

            for func, name in SAFE_REGISTERS:
                reg = REGISTER_DEFINITIONS.get(name)
                if reg is None:
                    continue
                addr = reg.address
                try:
                    if func == "04":
                        await asyncio.wait_for(
                            _call_modbus(
                                client.read_input_registers,
                                self.slave_id,
                                addr,
                                count=1,
                            ),
                            timeout=self.timeout,
                        )
                    else:  # "03"
                        await asyncio.wait_for(
                            _call_modbus(
                                client.read_holding_registers,
                                self.slave_id,
                                addr,
                                count=1,
                            ),
                            timeout=self.timeout,
                        )
                except asyncio.TimeoutError as exc:  # pragma: no cover - network issues
                    _LOGGER.warning("Timeout reading %s", name)
                    raise ConnectionException(f"Timeout reading {name}") from exc
                except ModbusException:
                    raise
                except Exception as exc:  # pragma: no cover - forward unexpected
                    raise ModbusException(f"Error reading {name}: {exc}") from exc
        finally:
            await client.close()

    def _is_valid_register_value(self, name: str, value: int) -> bool:
        """Validate a register value against known constraints.

        This check is intentionally lightweight – it ensures that obvious
        placeholder values (like ``SENSOR_UNAVAILABLE``) and values outside the
        ranges defined in the register metadata are ignored.  The method mirrors
        behaviour expected by the tests but does not aim to provide exhaustive
        validation of every register.
        """

        if name in SENSOR_UNAVAILABLE_REGISTERS and value == SENSOR_UNAVAILABLE:
            return False

        allowed = REGISTER_ALLOWED_VALUES.get(name)
        if allowed is not None and value not in allowed:
            return False

        if name.startswith(BCD_TIME_PREFIXES) and name != "schedule_start_time":
            if _decode_bcd_time(value) is None:
                return False

        if range_vals := self._register_ranges.get(name):
            min_val, max_val = range_vals
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False

        return True

    def _analyze_capabilities(self) -> DeviceCapabilities:
        """Derive device capabilities from discovered registers."""

        caps = DeviceCapabilities()
        inputs = self.available_registers["input_registers"]
        holdings = self.available_registers["holding_registers"]
        coils = self.available_registers["coil_registers"]
        discretes = self.available_registers["discrete_inputs"]

        # Temperature sensors
        temp_map = {
            "sensor_outside_temperature": "outside_temperature",
            "sensor_supply_temperature": "supply_temperature",
            "sensor_exhaust_temperature": "exhaust_temperature",
            "sensor_fpx_temperature": "fpx_temperature",
            "sensor_duct_supply_temperature": "duct_supply_temperature",
            "sensor_gwc_temperature": "gwc_temperature",
            "sensor_ambient_temperature": "ambient_temperature",
            "sensor_heating_temperature": "heating_temperature",
        }
        for attr, reg in temp_map.items():
            if reg in inputs:
                setattr(caps, attr, True)
                caps.temperature_sensors.add(reg)

        caps.temperature_sensors_count = len(caps.temperature_sensors)  # pragma: no cover

        # Expansion module and GWC detection via discrete inputs/coils
        if "expansion" in discretes:
            caps.expansion_module = True  # pragma: no cover
        if "gwc" in coils or "gwc_temperature" in inputs:
            caps.gwc_system = True  # pragma: no cover

        if "bypass" in coils:
            caps.bypass_system = True  # pragma: no cover
        if any(reg.startswith("schedule_") for reg in holdings):
            caps.weekly_schedule = True  # pragma: no cover

        if any(
            reg in inputs
            for reg in [
                "constant_flow_active",
                "supply_flow_rate",
                "supply_air_flow",
                "cf_version",
            ]
        ):
            caps.constant_flow = True  # pragma: no cover

        # Generic capability detection based on register name patterns
        all_registers = inputs | holdings | coils | discretes
        for attr, patterns in CAPABILITY_PATTERNS.items():
            if getattr(caps, attr):
                continue
            if any(pat in reg for reg in all_registers for pat in patterns):
                setattr(caps, attr, True)

        return caps

    def _group_registers_for_batch_read(
        self, addresses: list[int], *, max_gap: int = 1, max_batch: int | None = None
    ) -> list[tuple[int, int]]:
        """Group consecutive register addresses for efficient batch reads.

        ``max_gap`` is retained for backward compatibility with older callers
        even though the helper no longer uses it directly.  The implementation
        delegates grouping to the shared ``group_reads`` helper so that the
        scanner benefits from the same optimisation logic used elsewhere in the
        project.  Any registers that have previously been marked as missing are
        split into their own single-register groups to avoid unnecessary
        failures when reading surrounding ranges.
        """

        if not addresses:
            return []

        # ``max_gap`` is unused but kept for API compatibility
        _ = max_gap

        if max_batch is None:
            max_batch = self.max_block_size

        # First, compute contiguous blocks using the generic ``group_reads``
        # helper.  ``max_gap`` is kept for API compatibility but is not
        # required when using ``group_reads`` which already splits on gaps.
        groups = _group_reads(addresses, max_block_size=max_batch)

        if not self._known_missing_addresses:
            return groups

        # Split out any known missing addresses so they are queried
        # individually without preventing neighbouring registers from being
        # read in batches.
        adjusted: list[tuple[int, int]] = []
        for start, length in groups:
            end = start + length
            current_start: int | None = None
            current_len = 0
            for addr in range(start, end):
                if addr in self._known_missing_addresses:
                    if current_len:
                        assert current_start is not None
                        adjusted.append((current_start, current_len))
                        current_len = 0
                    adjusted.append((addr, 1))
                    current_start = None
                else:
                    if current_len == 0:
                        current_start = addr
                    current_len += 1
            if current_len:
                assert current_start is not None
                adjusted.append((current_start, current_len))

        return adjusted

    async def scan(self) -> dict[str, Any]:
        """Perform the actual register scan using an established connection."""
        client = self._client
        if client is None:
            raise ConnectionException("Client not connected")

        device = DeviceInfo()

        # Basic firmware/serial information
        info_regs = await self._read_input(client, 0, 30) or []
        major: int | None = None
        minor: int | None = None
        patch: int | None = None
        firmware_err: Exception | None = None

        for name in ("version_major", "version_minor", "version_patch"):
            idx = INPUT_REGISTERS[name]
            if len(info_regs) > idx:
                try:
                    value = info_regs[idx]
                except Exception as exc:  # pragma: no cover - best effort
                    firmware_err = exc
                    continue
                if name == "version_major":
                    major = value
                elif name == "version_minor":
                    minor = value
                else:
                    patch = value

        missing_regs: list[str] = []
        if None in (major, minor, patch):
            for name, value in (
                ("version_major", major),
                ("version_minor", minor),
                ("version_patch", patch),
            ):
                if value is None and name in INPUT_REGISTERS:
                    addr = INPUT_REGISTERS[name]
                    single = await self._read_input(client, addr, 1, skip_cache=True)
                    if single:
                        if name == "version_major":
                            major = single[0]
                        elif name == "version_minor":
                            minor = single[0]
                        else:
                            patch = single[0]
                    else:
                        missing_regs.append(f"{name} (0x{addr:04X})")

        if None not in (major, minor, patch):
            device.firmware = f"{major}.{minor}.{patch}"
        else:
            details: list[str] = []
            if missing_regs:
                details.append("missing " + ", ".join(missing_regs))
            if firmware_err is not None:
                details.append(str(firmware_err))
            msg = "Failed to read firmware version registers"
            if details:
                msg += ": " + "; ".join(details)
            _LOGGER.warning(msg)
            device.firmware_available = False  # pragma: no cover
        try:
            start = INPUT_REGISTERS["serial_number"]
            parts = info_regs[start : start + REGISTER_DEFINITIONS["serial_number"].length]  # noqa: E203
            if parts:
                device.serial_number = "".join(f"{p:04X}" for p in parts)
        except Exception:  # pragma: no cover
            pass
        try:
            start = HOLDING_REGISTERS["device_name"]
            name_regs = await self._read_holding(
                client, start, REGISTER_DEFINITIONS["device_name"].length
            ) or []
            if name_regs:
                name_bytes = bytearray()
                for reg in name_regs:
                    name_bytes.append((reg >> 8) & 0xFF)
                    name_bytes.append(reg & 0xFF)
                device.device_name = name_bytes.decode("ascii").rstrip("\x00")
        except Exception:  # pragma: no cover
            pass
        unknown_registers: dict[str, dict[int, Any]] = {
            "input_registers": {},
            "holding_registers": {},
            "coil_registers": {},
            "discrete_inputs": {},
        }
        scanned_registers: dict[str, int] = {
            "input_registers": 0,
            "holding_registers": 0,
            "coil_registers": 0,
            "discrete_inputs": 0,
        }

        input_max = max(self._registers.get("04", {}).keys(), default=-1)
        holding_max = max(self._registers.get("03", {}).keys(), default=-1)
        coil_max = max(self._registers.get("01", {}).keys(), default=-1)
        discrete_max = max(self._registers.get("02", {}).keys(), default=-1)

        if self.full_register_scan:
            for addr in range(0, input_max + 1):
                scanned_registers["input_registers"] += 1
                input_data = await self._read_input(client, addr, 1, skip_cache=True)
                if not input_data:
                    continue
                reg_name = self._registers.get("04", {}).get(addr)
                if reg_name and self._is_valid_register_value(reg_name, input_data[0]):
                    self.available_registers["input_registers"].add(reg_name)
                else:
                    unknown_registers["input_registers"][addr] = input_data[0]
                    if reg_name:
                        self.failed_addresses["invalid_values"]["input_registers"].add(addr)
                        self._log_invalid_value(reg_name, input_data[0])

            for addr in range(0, holding_max + 1):
                scanned_registers["holding_registers"] += 1
                holding_data = await self._read_holding(client, addr, 1, skip_cache=True)
                if not holding_data:
                    continue
                reg_name = self._registers.get("03", {}).get(addr)
                if reg_name and self._is_valid_register_value(reg_name, holding_data[0]):
                    self.available_registers["holding_registers"].add(reg_name)
                else:
                    unknown_registers["holding_registers"][addr] = holding_data[0]
                    if reg_name:
                        self.failed_addresses["invalid_values"]["holding_registers"].add(addr)
                        self._log_invalid_value(reg_name, holding_data[0])

            for addr in range(0, coil_max + 1):
                scanned_registers["coil_registers"] += 1
                coil_data = await self._read_coil(client, addr, 1)
                if not coil_data:
                    continue
                if (reg_name := self._registers.get("01", {}).get(addr)) is not None:
                    self.available_registers["coil_registers"].add(reg_name)
                else:
                    unknown_registers["coil_registers"][addr] = coil_data[0]

            for addr in range(0, discrete_max + 1):
                scanned_registers["discrete_inputs"] += 1
                discrete_data = await self._read_discrete(client, addr, 1)
                if not discrete_data:
                    continue
                if (reg_name := self._registers.get("02", {}).get(addr)) is not None:
                    self.available_registers["discrete_inputs"].add(reg_name)
                else:
                    unknown_registers["discrete_inputs"][addr] = discrete_data[0]
        else:
            # Scan Input Registers in batches
            input_addr_to_name: dict[int, str] = {}
            input_addresses: list[int] = []
            for name, addr in INPUT_REGISTERS.items():
                if self.skip_known_missing and name in KNOWN_MISSING_REGISTERS["input_registers"]:
                    continue
                input_addr_to_name[addr] = name
                input_addresses.append(addr)

            for start, count in self._group_registers_for_batch_read(input_addresses):
                input_data = await self._read_input(client, start, count)
                if input_data is None:
                    for offset in range(count):
                        addr = start + offset
                        if addr not in input_addr_to_name:
                            continue
                        single = await self._read_input(client, addr, 1, skip_cache=True)
                        if single and self._is_valid_register_value(
                            input_addr_to_name[addr], single[0]
                        ):
                            self.available_registers["input_registers"].add(
                                input_addr_to_name[addr]
                            )
                        elif single is not None:
                            self.failed_addresses["invalid_values"]["input_registers"].add(
                                addr
                            )
                            self._log_invalid_value(
                                input_addr_to_name[addr], single[0]
                            )
                    continue

                for offset, value in enumerate(input_data):
                    addr = start + offset
                    if reg_name := input_addr_to_name.get(addr):
                        if self._is_valid_register_value(reg_name, value):
                            self.available_registers["input_registers"].add(reg_name)
                        else:
                            self.failed_addresses["invalid_values"]["input_registers"].add(
                                addr
                            )
                            self._log_invalid_value(reg_name, value)

            # Scan Holding Registers in batches
            holding_info: dict[int, tuple[str, int]] = {}
            holding_addresses: list[int] = []
            for name, addr in HOLDING_REGISTERS.items():
                if not self.scan_uart_settings and addr in UART_OPTIONAL_REGS:
                    continue
                if self.skip_known_missing and name in KNOWN_MISSING_REGISTERS["holding_registers"]:
                    continue
                size = MULTI_REGISTER_SIZES.get(name, 1)
                holding_info[addr] = (name, size)
                holding_addresses.extend(range(addr, addr + size))

            for start, count in self._group_registers_for_batch_read(holding_addresses):
                holding_data = await self._read_holding(client, start, count)
                if holding_data is None:
                    for offset in range(count):
                        addr = start + offset
                        if addr not in holding_info:
                            continue
                        name, size = holding_info[addr]
                        single = await self._read_holding(client, addr, size, skip_cache=True)
                        if single and self._is_valid_register_value(name, single[0]):
                            self.available_registers["holding_registers"].add(name)
                        elif single is not None:
                            self.failed_addresses["invalid_values"]["holding_registers"].add(
                                addr
                            )
                            self._log_invalid_value(name, single[0])
                    continue

                for offset, value in enumerate(holding_data):
                    addr = start + offset
                    if addr in holding_info:
                        name, _size = holding_info[addr]
                        if self._is_valid_register_value(name, value):
                            self.available_registers["holding_registers"].add(name)
                        else:
                            self.failed_addresses["invalid_values"]["holding_registers"].add(
                                addr
                            )
                            self._log_invalid_value(name, value)

            # Always expose diagnostic registers so error entities exist even
            # when the device does not implement them.
            for name in HOLDING_REGISTERS:
                if name.startswith(("e_", "s_")) or name in {"alarm", "error"}:
                    self.available_registers["holding_registers"].add(name)

            # Scan Coil Registers in batches
            coil_addr_to_name: dict[int, str] = {}
            coil_addresses: list[int] = []
            for name, addr in COIL_REGISTERS.items():
                if self.skip_known_missing and name in KNOWN_MISSING_REGISTERS["coil_registers"]:
                    continue
                coil_addr_to_name[addr] = name
                coil_addresses.append(addr)

            for start, count in self._group_registers_for_batch_read(coil_addresses):
                coil_data = await self._read_coil(client, start, count)
                if coil_data is None:
                    for offset in range(count):
                        addr = start + offset
                        if addr not in coil_addr_to_name:
                            continue
                        single_coil = await self._read_coil(client, addr, 1)
                        if single_coil is not None:
                            self.available_registers["coil_registers"].add(coil_addr_to_name[addr])
                    continue
                for offset, value in enumerate(coil_data):
                    addr = start + offset
                    if addr in coil_addr_to_name and value is not None:
                        self.available_registers["coil_registers"].add(coil_addr_to_name[addr])

            # Scan Discrete Input Registers in batches
            discrete_addr_to_name: dict[int, str] = {}
            discrete_addresses: list[int] = []
            for name, addr in DISCRETE_INPUT_REGISTERS.items():
                if self.skip_known_missing and name in KNOWN_MISSING_REGISTERS["discrete_inputs"]:
                    continue
                discrete_addr_to_name[addr] = name
                discrete_addresses.append(addr)

            for start, count in self._group_registers_for_batch_read(discrete_addresses):
                discrete_data = await self._read_discrete(client, start, count)
                if discrete_data is None:
                    for offset in range(count):
                        addr = start + offset
                        if addr not in discrete_addr_to_name:
                            continue
                        single_discrete = await self._read_discrete(client, addr, 1)
                        if single_discrete is not None:
                            self.available_registers["discrete_inputs"].add(
                                discrete_addr_to_name[addr]
                            )
                    continue
                for offset, value in enumerate(discrete_data):
                    addr = start + offset
                    if addr in discrete_addr_to_name and value is not None:
                        self.available_registers["discrete_inputs"].add(discrete_addr_to_name[addr])

        caps = self._analyze_capabilities()
        self.capabilities = caps
        device.capabilities = [
            key for key, val in caps.as_dict().items() if isinstance(val, bool) and val
        ]

        if self.full_register_scan:
            scan_blocks = {
                "input_registers": (
                    0 if input_max >= 0 else None,
                    input_max if input_max >= 0 else None,
                ),
                "holding_registers": (
                    0 if holding_max >= 0 else None,
                    holding_max if holding_max >= 0 else None,
                ),
                "coil_registers": (
                    0 if coil_max >= 0 else None,
                    coil_max if coil_max >= 0 else None,
                ),
                "discrete_inputs": (
                    0 if discrete_max >= 0 else None,
                    discrete_max if discrete_max >= 0 else None,
                ),
            }
        else:
            scan_blocks = {
                "input_registers": (
                    (
                        min(INPUT_REGISTERS.values()),
                        max(INPUT_REGISTERS.values()),
                    )
                    if INPUT_REGISTERS
                    else (None, None)
                ),
                "holding_registers": (
                    (
                        min(HOLDING_REGISTERS.values()),
                        max(HOLDING_REGISTERS.values()),
                    )
                    if HOLDING_REGISTERS
                    else (None, None)
                ),
                "coil_registers": (
                    (
                        min(COIL_REGISTERS.values()),
                        max(COIL_REGISTERS.values()),
                    )
                    if COIL_REGISTERS
                    else (None, None)
                ),
                "discrete_inputs": (
                    (
                        min(DISCRETE_INPUT_REGISTERS.values()),
                        max(DISCRETE_INPUT_REGISTERS.values()),
                    )
                    if DISCRETE_INPUT_REGISTERS
                    else (None, None)
                ),
            }
        self._log_skipped_ranges()

        raw_registers: dict[int, int] = {}
        if self.deep_scan:
            for start, count in self._group_registers_for_batch_read(list(range(0x012D))):
                data = await self._read_input(client, start, count)
                if data is None:
                    continue
                for offset, value in enumerate(data):
                    raw_registers[start + offset] = value

        # Determine expected registers that were not successfully read
        register_maps = {
            "input_registers": INPUT_REGISTERS,
            "holding_registers": HOLDING_REGISTERS,
            "coil_registers": COIL_REGISTERS,
            "discrete_inputs": DISCRETE_INPUT_REGISTERS,
        }
        missing_registers: dict[str, dict[str, int]] = {}
        for reg_type, mapping in register_maps.items():
            missing: dict[str, int] = {}
            for name, addr in mapping.items():
                if self.skip_known_missing and name in KNOWN_MISSING_REGISTERS[reg_type]:
                    continue
                if name not in self.available_registers[reg_type]:
                    missing[name] = addr
            if missing:
                missing_registers[reg_type] = missing

        if missing_registers:
            details = []
            for reg_type, regs in missing_registers.items():
                formatted = ", ".join(
                    f"{name}=0x{addr:04X}"
                    for name, addr in sorted(regs.items(), key=lambda item: item[1])
                )
                details.append(f"{reg_type}: {formatted}")
            _LOGGER.warning(
                "The following registers were not found during scan: %s", "; ".join(details)
            )

        result = {
            "available_registers": self.available_registers,
            "device_info": device.as_dict(),
            "capabilities": caps.as_dict(),
            "register_count": sum(len(v) for v in self.available_registers.values()),
            "scan_blocks": scan_blocks,
            "unknown_registers": unknown_registers,
            "scanned_registers": scanned_registers,
            "missing_registers": missing_registers,
            "failed_addresses": {
                "modbus_exceptions": {
                    k: sorted(v)
                    for k, v in self.failed_addresses["modbus_exceptions"].items()
                    if v
                },
                "invalid_values": {
                    k: sorted(v)
                    for k, v in self.failed_addresses["invalid_values"].items()
                    if v
                },
            },
        }
        if self.deep_scan:
            result["raw_registers"] = raw_registers
            result["total_addresses_scanned"] = len(raw_registers)

        return result

    async def scan_device(self) -> dict[str, Any]:
        """Open the Modbus connection, perform a scan and close the client."""
        from pymodbus.client import AsyncModbusTcpClient

        self._client = AsyncModbusTcpClient(self.host, port=self.port, timeout=self.timeout)

        try:
            connected = await asyncio.wait_for(
                self._client.connect(), timeout=self.timeout
            )
            if not connected:
                raise ConnectionException("Failed to connect")
            result = await self.scan()
            if not isinstance(result, dict):
                raise TypeError("scan() must return a dict")
            return result
        finally:
            await self.close()

    async def _load_registers(
        self,
    ) -> Tuple[
        Dict[str, Dict[int, str]],
        Dict[str, Tuple[Optional[int], Optional[int]]],
    ]:
        """Load Modbus register definitions and value ranges."""
        register_map: Dict[str, Dict[int, str]] = {"03": {}, "04": {}, "01": {}, "02": {}}
        register_ranges: Dict[str, Tuple[Optional[int], Optional[int]]] = {}
        for reg in get_all_registers():
            if not reg.name:
                continue
            register_map[reg.function][reg.address] = reg.name
            if reg.min is not None or reg.max is not None:
                register_ranges[reg.name] = (reg.min, reg.max)
        return register_map, register_ranges

    def _sleep_time(self, attempt: int) -> float:
        """Return delay for a retry attempt based on backoff."""
        if self.backoff:
            return float(self.backoff * 2 ** (attempt - 1))
        return 0.0

    def _log_skipped_ranges(self) -> None:
        """Log summary of ranges skipped due to Modbus exceptions."""
        if self._unsupported_input_ranges:
            ranges = ", ".join(
                f"0x{start:04X}-0x{end:04X} (exception code {code})"
                for (start, end), code in sorted(self._unsupported_input_ranges.items())
            )
            _LOGGER.warning("Skipping unsupported input registers %s", ranges)
        if self._unsupported_holding_ranges:
            ranges = ", ".join(
                f"0x{start:04X}-0x{end:04X} (exception code {code})"
                for (start, end), code in sorted(self._unsupported_holding_ranges.items())
            )
            _LOGGER.warning("Skipping unsupported holding registers %s", ranges)

        for reg_type, addrs in self.failed_addresses["modbus_exceptions"].items():
            if addrs:
                hexes = ", ".join(f"0x{addr:04X}" for addr in sorted(addrs))
                _LOGGER.warning("Failed to read %s at %s", reg_type, hexes)

        for reg_type, addrs in self.failed_addresses["invalid_values"].items():
            if addrs:
                hexes = ", ".join(f"0x{addr:04X}" for addr in sorted(addrs))
                _LOGGER.debug("Invalid values for %s at %s", reg_type, hexes)

    def _log_invalid_value(self, name: str, raw: int) -> None:
        """Log a register value that failed validation."""
        if name in self._reported_invalid:
            level = logging.DEBUG
        else:
            level = logging.INFO if self.verbose_invalid_values else logging.DEBUG
            self._reported_invalid.add(name)
        decoded = _format_register_value(name, raw)
        _LOGGER.log(level, "Invalid value for %s: raw=0x%04X decoded=%s", name, raw, decoded)

    def _mark_input_supported(self, address: int) -> None:
        """Remove address from cached unsupported input ranges after success."""
        self._failed_input.discard(address)
        for (start, end), code in list(self._unsupported_input_ranges.items()):
            if start <= address <= end:
                del self._unsupported_input_ranges[(start, end)]
                if start <= address - 1:
                    self._unsupported_input_ranges[(start, address - 1)] = code
                if address + 1 <= end:
                    self._unsupported_input_ranges[(address + 1, end)] = code

    def _mark_holding_supported(self, address: int) -> None:
        """Remove address from cached unsupported holding ranges after success."""
        self._failed_holding.discard(address)
        for (start, end), code in list(self._unsupported_holding_ranges.items()):
            if start <= address <= end:
                del self._unsupported_holding_ranges[(start, end)]
                if start <= address - 1:
                    self._unsupported_holding_ranges[(start, address - 1)] = code
                if address + 1 <= end:
                    self._unsupported_holding_ranges[(address + 1, end)] = code

    def _mark_holding_unsupported(self, start: int, end: int, code: int) -> None:
        """Track unsupported holding register range without overlaps."""
        for (exist_start, exist_end), exist_code in list(self._unsupported_holding_ranges.items()):
            if exist_end < start or exist_start > end:
                continue
            del self._unsupported_holding_ranges[(exist_start, exist_end)]
            if exist_start < start:
                self._unsupported_holding_ranges[(exist_start, start - 1)] = exist_code
            if end < exist_end:
                self._unsupported_holding_ranges[(end + 1, exist_end)] = exist_code
        self._unsupported_holding_ranges[(start, end)] = code

    def _mark_input_unsupported(self, start: int, end: int, code: int | None) -> None:
        """Cache unsupported input register range, merging overlaps."""

        for (old_start, old_end), _ in list(self._unsupported_input_ranges.items()):
            if end < old_start or start > old_end:
                continue
            del self._unsupported_input_ranges[(old_start, old_end)]
            start = min(start, old_start)
            end = max(end, old_end)

        self._unsupported_input_ranges[(start, end)] = code or 0

    async def _read_input(
        self,
        client: "AsyncModbusTcpClient",
        address: int,
        count: int,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        """Read input registers with retry and backoff.

        ``skip_cache`` is used when probing individual registers after a block
        read failed. When ``True`` the cached set of failed registers is not
        checked, allowing each register to be queried once before being cached
        as missing.
        """
        start = address
        end = address + count - 1

        if not skip_cache:
            for skip_start, skip_end in self._unsupported_input_ranges:
                if skip_start <= start and end <= skip_end:
                    self.failed_addresses["modbus_exceptions"]["input_registers"].update(
                        range(start, end + 1)
                    )
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
            self.failed_addresses["modbus_exceptions"]["input_registers"].update(
                range(skip_start, skip_end + 1)
            )
            return None

        for attempt in range(1, self.retry + 1):
            try:
                response: Any = await asyncio.wait_for(
                    _call_modbus(
                        client.read_input_registers, self.slave_id, address, count=count
                    ),
                    timeout=self.timeout,
                )
                if response is not None:
                    if response.isError():
                        code = getattr(response, "exception_code", None)
                        self._failed_input.update(range(start, end + 1))
                        self._mark_input_unsupported(start, end, code)
                        self.failed_addresses["modbus_exceptions"]["input_registers"].update(
                            range(start, end + 1)
                        )
                        return None
                    if skip_cache and count == 1:
                        self._mark_input_supported(address)
                    registers = cast(list[int], response.registers)
                    _LOGGER.debug(
                        "Read input registers 0x%04X-0x%04X: %s",
                        start,
                        end,
                        registers,
                    )
                    return registers
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
            except asyncio.TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading input 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break
            except OSError as exc:
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
                        self.failed_addresses["modbus_exceptions"]["input_registers"].add(
                            address
                        )
                        _LOGGER.warning("Device does not expose register 0x%04X", address)
            except asyncio.TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading input registers 0x%04X-0x%04X on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break
            except (ModbusException, ConnectionException) as exc:
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
                response = await asyncio.wait_for(
                    _call_modbus(
                        client.read_holding_registers, self.slave_id, address, count=count
                    ),
                    timeout=self.timeout,
                )
                if response is not None:
                    if response.isError():
                        code = getattr(response, "exception_code", None)
                        self._failed_input.update(range(start, end + 1))
                        self._mark_input_unsupported(start, end, code)
                        self.failed_addresses["modbus_exceptions"]["input_registers"].update(
                            range(start, end + 1)
                        )
                        return None
                    if skip_cache and count == 1:
                        self._mark_input_supported(address)
                    registers = cast(list[int], response.registers)
                    _LOGGER.debug(
                        "Read holding registers 0x%04X-0x%04X (fallback): %s",
                        start,
                        end,
                        registers,
                    )
                    return registers
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
            except asyncio.TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading holding 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading holding 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            if attempt < self.retry:
                try:
                    await asyncio.sleep(self._sleep_time(attempt))
                except asyncio.CancelledError:
                    _LOGGER.debug("Sleep cancelled while retrying input 0x%04X", address)
                    raise

        self.failed_addresses["modbus_exceptions"]["input_registers"].update(
            range(start, end + 1)
        )
        _LOGGER.error(
            "Failed to read input registers 0x%04X-0x%04X after %d retries",
            start,
            end,
            self.retry,
        )
        return None

    async def _read_holding(
        self,
        client: "AsyncModbusTcpClient",
        address: int,
        count: int,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        """Read holding registers with retry, backoff and failure tracking.

        ``skip_cache`` is used when probing individual registers after a block
        read failed. When ``True`` the cached sets of unsupported ranges and
        failed registers are ignored, allowing each register to be queried
        once before being cached again.
        """
        start = address
        end = address + count - 1

        if not skip_cache:
            for skip_start, skip_end in self._unsupported_holding_ranges:
                if skip_start <= start and end <= skip_end:
                    self.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                        range(start, end + 1)
                    )
                    return None

            if address in self._failed_holding:
                _LOGGER.debug("Skipping cached failed holding register 0x%04X", address)
                self.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)
                return None

        failures = self._holding_failures.get(address, 0)
        if failures >= self.retry:
            _LOGGER.warning("Skipping unsupported holding register 0x%04X", address)
            self.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)
            return None

        for attempt in range(1, self.retry + 1):
            try:
                response: Any = await asyncio.wait_for(
                    _call_modbus(
                        client.read_holding_registers, self.slave_id, address, count=count
                    ),
                    timeout=self.timeout,
                )
                if response is not None:
                    if response.isError():
                        code = getattr(response, "exception_code", None)
                        self._failed_holding.update(range(start, end + 1))
                        self._mark_holding_unsupported(start, end, code or 0)
                        self.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                            range(start, end + 1)
                        )
                        return None
                    if skip_cache and count == 1:
                        self._mark_holding_supported(address)
                    if address in self._holding_failures:
                        del self._holding_failures[address]
                    registers = cast(list[int], response.registers)
                    _LOGGER.debug(
                        "Read holding registers 0x%04X-0x%04X: %s",
                        start,
                        end,
                        registers,
                    )
                    return registers
            except asyncio.TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading holding 0x%04X (attempt %d/%d): %s",
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
                        self.failed_addresses["modbus_exceptions"]["holding_registers"].add(
                            address
                        )
                        _LOGGER.warning("Device does not expose register 0x%04X", address)
            except (ModbusException, ConnectionException) as exc:
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
                        self.failed_addresses["modbus_exceptions"]["holding_registers"].add(
                            address
                        )
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

            if attempt < self.retry:
                try:
                    await asyncio.sleep(self._sleep_time(attempt))
                except asyncio.CancelledError:
                    _LOGGER.debug("Sleep cancelled while retrying holding 0x%04X", address)
                    raise

        _LOGGER.error(
            "Failed to read holding registers 0x%04X-0x%04X after %d retries",
            start,
            end,
            self.retry,
        )
        self.failed_addresses["modbus_exceptions"]["holding_registers"].update(
            range(start, end + 1)
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
                response: Any = await asyncio.wait_for(
                    _call_modbus(
                        client.read_coils, self.slave_id, address, count=count
                    ),
                    timeout=self.timeout,
                )
                if response is not None and not response.isError():
                    bits = cast(list[bool], response.bits[:count])
                    _LOGGER.debug(
                        "Read coil registers 0x%04X-0x%04X: %s",
                        address,
                        address + count - 1,
                        bits,
                    )
                    return bits
            except asyncio.TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading coil 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
            except (ModbusException, ConnectionException) as exc:
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
                    await asyncio.sleep(self._sleep_time(attempt))
                except asyncio.CancelledError:
                    _LOGGER.debug("Sleep cancelled while retrying coil 0x%04X", address)
                    raise
        self.failed_addresses["modbus_exceptions"]["coil_registers"].update(
            range(address, address + count)
        )
        _LOGGER.error(
            "Failed to read coil registers 0x%04X-0x%04X after %d retries",
            address,
            address + count - 1,
            self.retry,
        )
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
                response: Any = await asyncio.wait_for(
                    _call_modbus(
                        client.read_discrete_inputs,
                        self.slave_id,
                        address,
                        count=count,
                    ),
                    timeout=self.timeout,
                )
                if response is not None and not response.isError():
                    bits = cast(list[bool], response.bits[:count])
                    _LOGGER.debug(
                        "Read discrete inputs 0x%04X-0x%04X: %s",
                        address,
                        address + count - 1,
                        bits,
                    )
                    return bits
            except asyncio.TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading discrete 0x%04X on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
            except (ModbusException, ConnectionException) as exc:
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
                    await asyncio.sleep(self._sleep_time(attempt))
                except asyncio.CancelledError:
                    _LOGGER.debug("Sleep cancelled while retrying discrete 0x%04X", address)
                    raise
        self.failed_addresses["modbus_exceptions"]["discrete_inputs"].update(
            range(address, address + count)
        )
        _LOGGER.error(
            "Failed to read discrete inputs 0x%04X-0x%04X after %d retries",
            address,
            address + count - 1,
            self.retry,
        )
        return None
