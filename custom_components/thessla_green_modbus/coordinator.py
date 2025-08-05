"""Poprawiony coordinator z kompatybilnością pymodbus 3.x+"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import ModbusTcpClient

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator):
    """Coordinator handling Modbus data updates and register management."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        scan_interval: int = 30,
        timeout: int = 10,
        retry: int = 3,
        available_registers: Dict[str, set] | None = None,
        device_info: Dict[str, Any] | None = None,
        capabilities: Dict[str, Any] | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="thessla_green_modbus",
            update_interval=timedelta(seconds=scan_interval),
        )

        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        self.available_registers = available_registers or {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }
        self.device_info = device_info or {}
        self.capabilities = capabilities or {}

        # Precompute optimized register groups for batch reading
        self.rebuild_register_groups()

    def rebuild_register_groups(self, available_registers: Dict[str, set] | None = None) -> None:
        """Recalculate optimized register groups.

        Optionally accepts a new mapping of available registers and updates
        the coordinator before computing the groups. This method is exposed so
        that a full device scan can rebuild the groups without reinstantiating
        the coordinator.
        """

        if available_registers is not None:
            self.available_registers = available_registers

        self._register_groups = self._compute_optimized_groups()
        _LOGGER.debug(
            "Precomputed %d optimized register groups", len(self._register_groups)
        )

    # Legacy method name for backward compatibility
    def _precompute_register_groups(self, available_registers: Dict[str, set] | None = None) -> None:
        self.rebuild_register_groups(available_registers)

    def _compute_optimized_groups(self) -> Dict[str, List[Tuple[int, int, Dict[str, int]]]]:
        """Pre-compute optimized register groups for efficient batch reading."""
        groups = {}

        # Mapowanie rejestrów do adresów - DOSTOSUJ DO TWOJEGO URZĄDZENIA
        register_mappings = {
            "input_registers": {
                "outside_temperature": 0x0010,
                "supply_temperature": 0x0011,
                "exhaust_temperature": 0x0012,
                "fpx_temperature": 0x0013,
                "firmware_major": 0x0000,
                "firmware_minor": 0x0001,
                "firmware_build": 0x0002,
            },
            "holding_registers": {
                "mode": 0x1000,
                "season_mode": 0x1001,
                "special_mode": 0x1002,
                "air_flow_rate_manual": 0x1003,
                "air_flow_rate_override": 0x1004,
            },
            "coil_registers": {
                "manual_mode": 0x0000,
                "fan_boost": 0x0001,
                "bypass_enable": 0x0002,
                "gwc_enable": 0x0003,
            },
            "discrete_inputs": {
                "filter_alarm": 0x0000,
                "frost_protection": 0x0001,
                "summer_mode": 0x0002,
                "fireplace": 0x000E,
                "fire_alarm": 0x000F,
            }
        }

        for reg_type, mapping in register_mappings.items():
            if reg_type not in self.available_registers:
                continue

            # Filter only available registers
            available_mapping = {
                name: addr for name, addr in mapping.items()
                if name in self.available_registers[reg_type]
            }

            if not available_mapping:
                groups[reg_type] = []
                continue

            # Group consecutive registers for batch reading
            groups[reg_type] = self._create_consecutive_groups(available_mapping)

        return groups

    def _create_consecutive_groups(self, register_mapping: Dict[str, int]) -> List[Tuple[int, int, Dict[str, int]]]:
        """Create groups of consecutive registers for efficient batch reading."""
        if not register_mapping:
            return []

        # Sort registers by address
        sorted_registers = sorted(register_mapping.items(), key=lambda x: x[1])
        groups = []
        current_group = [sorted_registers[0]]

        for name, addr in sorted_registers[1:]:
            last_addr = current_group[-1][1]

            # If address is consecutive (or close), add to current group
            if addr - last_addr <= 5:  # Allow small gaps
                current_group.append((name, addr))
            else:
                # Start new group
                groups.append(self._group_to_read_params(current_group))
                current_group = [(name, addr)]

        # Add the last group
        if current_group:
            groups.append(self._group_to_read_params(current_group))

        return groups

    def _group_to_read_params(self, group: List[Tuple[str, int]]) -> Tuple[int, int, Dict[str, int]]:
        """Convert group of registers to read parameters."""
        start_addr = group[0][1]
        end_addr = group[-1][1]
        count = end_addr - start_addr + 1
        key_map = {name: addr - start_addr for name, addr in group}
        return (start_addr, count, key_map)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Optimized data update using batch reading."""
        # Run the synchronous Modbus calls in the executor thread pool
        return await self.hass.async_add_executor_job(self._update_data_sync)

    def _update_data_sync(self) -> Dict[str, Any]:
        """Synchronous optimized data update with retry support."""
        last_exc: Exception | None = None

        for attempt in range(1, self.retry + 1):
            client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
            try:
                if not client.connect():
                    raise UpdateFailed("Could not connect to device")

                data: Dict[str, Any] = {}

                # Read all register types with optimized batching
                data.update(self._read_register_groups(client, "input_registers", self._read_input_registers))
                data.update(self._read_register_groups(client, "holding_registers", self._read_holding_registers))
                data.update(self._read_register_groups(client, "coil_registers", self._read_coils))
                data.update(self._read_register_groups(client, "discrete_inputs", self._read_discrete_inputs))

                return data

            except Exception as exc:
                last_exc = exc
                _LOGGER.error(
                    "Data update failed (attempt %d/%d): %s", attempt, self.retry, exc
                )
            finally:
                client.close()

        raise UpdateFailed(f"Error communicating with device: {last_exc}") from last_exc

    def _read_register_groups(self, client: ModbusTcpClient, register_type: str, read_func) -> Dict[str, Any]:
        """Read register groups with optimized batch operations."""
        data = {}

        if register_type not in self._register_groups:
            return data

        for start_addr, count, key_map in self._register_groups[register_type]:
            try:
                # Call the provided read function using the modern pymodbus API
                result = read_func(client, start_addr, count)
                if result and not result.isError():
                    # Extract values for each register in the group
                    if hasattr(result, 'registers'):
                        # For input/holding registers
                        for name, offset in key_map.items():
                            if offset < len(result.registers):
                                data[name] = self._process_register_value(name, result.registers[offset])
                    elif hasattr(result, 'bits'):
                        # For coils/discrete inputs
                        for name, offset in key_map.items():
                            if offset < len(result.bits):
                                data[name] = result.bits[offset]

            except Exception as exc:
                _LOGGER.debug("Failed to read %s group at 0x%04X: %s", register_type, start_addr, exc)

        return data

    def _read_input_registers(self, client: ModbusTcpClient, address: int, count: int):
        """Read input registers with the pymodbus 3.x API."""
        try:
            return client.read_input_registers(
                address=address,
                count=count,
                slave=self.slave_id
            )
        except Exception as exc:
            _LOGGER.debug("Failed to read input registers 0x%04X-0x%04X: %s",
                         address, address + count - 1, exc)
            return None

    def _read_holding_registers(self, client: ModbusTcpClient, address: int, count: int):
        """Read holding registers with the pymodbus 3.x API."""
        try:
            return client.read_holding_registers(
                address=address,
                count=count,
                slave=self.slave_id
            )
        except Exception as exc:
            _LOGGER.debug("Failed to read holding registers 0x%04X-0x%04X: %s",
                         address, address + count - 1, exc)
            return None

    def _read_coils(self, client: ModbusTcpClient, address: int, count: int):
        """Read coils with the pymodbus 3.x API."""
        try:
            return client.read_coils(
                address=address,
                count=count,
                slave=self.slave_id
            )
        except Exception as exc:
            _LOGGER.debug("Failed to read coils 0x%04X-0x%04X: %s",
                         address, address + count - 1, exc)
            return None

    def _read_discrete_inputs(self, client: ModbusTcpClient, address: int, count: int):
        """Read discrete inputs with the pymodbus 3.x API."""
        try:
            return client.read_discrete_inputs(
                address=address,
                count=count,
                slave=self.slave_id
            )
        except Exception as exc:
            _LOGGER.debug("Failed to read discrete inputs 0x%04X-0x%04X: %s",
                         address, address + count - 1, exc)
            return None

    async def async_write_register(self, key: str, value: int) -> bool:
        """Write a register with proper address mapping."""

        # Mapowanie kluczy do adresów - DOSTOSUJ DO TWOJEGO URZĄDZENIA
        REGISTER_ADDRESS_MAP = {
            # Holding registers
            "mode": 0x1000,
            "season_mode": 0x1001,
            "special_mode": 0x1002,
            "air_flow_rate_manual": 0x1003,
            "air_flow_rate_override": 0x1004,
            "on_off_panel_mode": 0x1005,

            # Coils (dla write_coil)
            "manual_mode": 0x0000,
            "fan_boost": 0x0001,
            "bypass_enable": 0x0002,
            "gwc_enable": 0x0003,
        }

        if key not in REGISTER_ADDRESS_MAP:
            _LOGGER.error("Unknown register key: %s", key)
            return False

        address = REGISTER_ADDRESS_MAP[key]

        def _write_sync():
            client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
            try:
                if not client.connect():
                    return False

                # Determine if it's a coil or holding register
                if key in ["manual_mode", "fan_boost", "bypass_enable", "gwc_enable"]:
                    # Write coil (boolean)
                    result = client.write_coil(
                        address=address,
                        value=bool(value),
                        slave=self.slave_id
                    )
                else:
                    # Write holding register (integer)
                    result = client.write_register(
                        address=address,
                        value=value,
                        slave=self.slave_id
                    )

                success = result and not result.isError()
                if success:
                    _LOGGER.debug("Successfully wrote %s=%s to 0x%04X", key, value, address)
                else:
                    _LOGGER.error("Failed to write %s=%s to 0x%04X: %s", key, value, address, result)
                return success

            except Exception as exc:
                _LOGGER.error("Exception writing register %s: %s", key, exc)
                return False
            finally:
                client.close()

        # Run the synchronous write in the executor
        success = await self.hass.async_add_executor_job(_write_sync)
        if success:
            await self.async_request_refresh()
        return success

    def _process_register_value(self, key: str, raw_value: Any) -> Any:
        """Process raw register value based on key type."""
        # Invalid values
        INVALID_TEMPERATURE = 0x8000  # 32768
        INVALID_FLOW = 65535

        # Temperature processing
        if "temperature" in key:
            if raw_value == INVALID_TEMPERATURE:
                return None
            if raw_value >= 0x8000:
                raw_value -= 0x10000
            if raw_value > 1000 or raw_value < -1000:
                return None
            return round(raw_value / 10.0, 1)

        # Flow processing
        elif "flow" in key or "flowrate" in key:
            if raw_value == INVALID_FLOW or raw_value > 10000:
                return None
            return raw_value

        # Percentage processing
        elif "percentage" in key:
            return max(0, min(100, raw_value))

        # Voltage processing (DAC)
        elif "dac" in key:
            return round(raw_value / 1000.0, 2)  # Convert mV to V

        # Boolean processing
        elif key in ["constant_flow_active", "gwc_mode", "bypass_mode", "on_off_panel_mode"]:
            return bool(raw_value)

        # Default: return as-is
        return raw_value

    def get_register_value(self, register_name: str, default: Any = None) -> Any:
        """Get current value of a register."""
        if self.data is None:
            return default
        return self.data.get(register_name, default)
