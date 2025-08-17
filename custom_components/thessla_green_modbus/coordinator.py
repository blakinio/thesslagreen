"""Data update coordinator for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    COIL_REGISTERS,
    DEFAULT_SCAN_INTERVAL,
    DISCRETE_INPUT_REGISTERS,
    DOMAIN,
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
        self.entry = entry

        self.client: ThesslaGreenModbusClient | None = None
        self.available_registers: Dict[str, Set[str]] = {
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

    # ------------------------------------------------------------------
    # Performance statistics
    # ------------------------------------------------------------------
    @property
    def performance_stats(self) -> Dict[str, Any]:
        return {
            "total_registers_read": self.statistics.get("total_registers_read", 0),
            "failed_batches": len(self._failed_registers),
            "last_successful_read": self._last_successful_read,
            "status": "ok" if not self._failed_registers else "degraded",
        }
