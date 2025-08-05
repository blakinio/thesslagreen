"""Enhanced coordinator for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import ModbusTcpClient

from .const import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    INVALID_TEMPERATURE,
    INVALID_FLOW,
)

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator):
    """Enhanced coordinator handling Modbus data updates and register management."""

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
        """Recalculate optimized register groups."""
        if available_registers is not None:
            self.available_registers = available_registers

        self._register_groups = self._compute_optimized_groups()
        _LOGGER.debug(
            "Precomputed %d optimized register groups", 
            sum(len(groups) for groups in self._register_groups.values())
        )

    def _compute_optimized_groups(self) -> Dict[str, List[Tuple[int, int, Dict[str, int]]]]:
        """Pre-compute optimized register groups for efficient batch reading."""
        groups = {}

        # Register type mappings with actual addresses
        register_mappings = {
            "input_registers": INPUT_REGISTERS,
            "holding_registers": HOLDING_REGISTERS,
            "coil_registers": COIL_REGISTERS,
            "discrete_inputs": DISCRETE_INPUT_REGISTERS,
        }

        for reg_type, mapping in register_mappings.items():
            if reg_type not in self.available_registers:
                groups[reg_type] = []
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
            
            _LOGGER.debug(
                "Created %d groups for %s with %d registers",
                len(groups[reg_type]), reg_type, len(available_mapping)
            )

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

            # If address is consecutive (or close with max gap of 5), add to current group
            if addr - last_addr <= 5:  # Allow small gaps for efficiency
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
        
        # Create mapping from register name to relative position in group
        key_map = {name: addr - start_addr for name, addr in group}
        
        return (start_addr, count, key_map)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Optimized data update using batch reading."""
        last_exc: Exception | None = None

        for attempt in range(1, self.retry + 1):
            client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
            try:
                # Connect to device
                connected = await self.hass.async_add_executor_job(client.connect)
                if not connected:
                    raise UpdateFailed("Could not connect to device")

                data: Dict[str, Any] = {}

                # Read all register types using optimized batching
                data.update(
                    await self._read_register_groups(
                        client, "input_registers", self._read_input_registers
                    )
                )
                data.update(
                    await self._read_register_groups(
                        client, "holding_registers", self._read_holding_registers
                    )
                )
                data.update(
                    await self._read_register_groups(
                        client, "coil_registers", self._read_coils
                    )
                )
                data.update(
                    await self._read_register_groups(
                        client, "discrete_inputs", self._read_discrete_inputs
                    )
                )

                # Log successful read
                _LOGGER.debug("Successfully read %d register values", len(data))
                return data

            except Exception as exc:
                last_exc = exc
                _LOGGER.warning(
                    "Data update failed (attempt %d/%d): %s", attempt, self.retry, exc
                )
                await asyncio.sleep(1)  # Brief delay before retry
            finally:
                try:
                    await self.hass.async_add_executor_job(client.close)
                except Exception:
                    pass  # Ignore connection close errors

        raise UpdateFailed(f"Error communicating with device: {last_exc}") from last_exc

    async def _read_register_groups(
        self, client: ModbusTcpClient, register_type: str, read_func
    ) -> Dict[str, Any]:
        """Read register groups with optimized batch operations."""
        data = {}
        groups = self._register_groups.get(register_type, [])
        
        for start_addr, count, key_map in groups:
            try:
                # Perform batch read
                response = await self.hass.async_add_executor_job(
                    read_func, client, start_addr, count, self.slave_id
                )
                
                if response.isError():
                    _LOGGER.warning(
                        "Failed to read %s group at 0x%04X (count=%d): %s",
                        register_type, start_addr, count, response
                    )
                    continue
                
                # Extract values based on register type
                if register_type in ["input_registers", "holding_registers"]:
                    values = response.registers
                elif register_type in ["coil_registers", "discrete_inputs"]:
                    values = response.bits
                else:
                    continue
                
                # Map values to register names and process them
                for name, offset in key_map.items():
                    if offset < len(values):
                        raw_value = values[offset]
                        processed_value = self._process_register_value(name, raw_value)
                        if processed_value is not None:
                            data[name] = processed_value
                        
            except Exception as exc:
                _LOGGER.warning(
                    "Error reading %s group at 0x%04X: %s",
                    register_type, start_addr, exc
                )
                continue
        
        return data

    def _read_input_registers(self, client: ModbusTcpClient, address: int, count: int, slave_id: int):
        """Read input registers."""
        return client.read_input_registers(address, count, slave=slave_id)

    def _read_holding_registers(self, client: ModbusTcpClient, address: int, count: int, slave_id: int):
        """Read holding registers."""
        return client.read_holding_registers(address, count, slave=slave_id)

    def _read_coils(self, client: ModbusTcpClient, address: int, count: int, slave_id: int):
        """Read coils."""
        return client.read_coils(address, count, slave=slave_id)

    def _read_discrete_inputs(self, client: ModbusTcpClient, address: int, count: int, slave_id: int):
        """Read discrete inputs."""
        return client.read_discrete_inputs(address, count, slave=slave_id)

    def _process_register_value(self, key: str, raw_value: int) -> Any:
        """Process raw register value based on register type."""
        # Temperature processing
        if "temperature" in key:
            if raw_value == INVALID_TEMPERATURE:
                return None
            if raw_value >= 0x8000:  # Handle negative temperatures
                raw_value -= 0x10000
            if raw_value > 1000 or raw_value < -1000:  # Sanity check
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

        # Default: return as-is for other types
        return raw_value

    async def async_write_register(self, register_name: str, value: int) -> bool:
        """Write to a holding register."""
        # Check if register exists in holding registers
        if register_name not in HOLDING_REGISTERS:
            _LOGGER.warning("Cannot write to unknown register: %s", register_name)
            return False
        
        address = HOLDING_REGISTERS[register_name]
        
        def _write_register():
            client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
            try:
                if not client.connect():
                    return False
                
                response = client.write_register(address, value, slave=self.slave_id)
                return not response.isError()
                
            except Exception as exc:
                _LOGGER.error("Failed to write register %s: %s", register_name, exc)
                return False
            finally:
                try:
                    client.close()
                except Exception:
                    pass
        
        try:
            success = await self.hass.async_add_executor_job(_write_register)
            if success:
                _LOGGER.debug("Successfully wrote %s = %s", register_name, value)
                # Trigger immediate refresh to get updated values
                await self.async_request_refresh()
            return success
        except Exception as exc:
            _LOGGER.error("Error writing register %s: %s", register_name, exc)
            return False

    async def async_write_coil(self, coil_name: str, value: bool) -> bool:
        """Write to a coil register."""
        # Check if coil exists
        if coil_name not in COIL_REGISTERS:
            _LOGGER.warning("Cannot write to unknown coil: %s", coil_name)
            return False
        
        address = COIL_REGISTERS[coil_name]
        
        def _write_coil():
            client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
            try:
                if not client.connect():
                    return False
                
                response = client.write_coil(address, value, slave=self.slave_id)
                return not response.isError()
                
            except Exception as exc:
                _LOGGER.error("Failed to write coil %s: %s", coil_name, exc)
                return False
            finally:
                try:
                    client.close()
                except Exception:
                    pass
        
        try:
            success = await self.hass.async_add_executor_job(_write_coil)
            if success:
                _LOGGER.debug("Successfully wrote coil %s = %s", coil_name, value)
                await self.async_request_refresh()
            return success
        except Exception as exc:
            _LOGGER.error("Error writing coil %s: %s", coil_name, exc)
            return False

    def get_register_value(self, register_name: str, default: Any = None) -> Any:
        """Get current value of a register."""
        if self.data is None:
            return default
        return self.data.get(register_name, default)

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and cleanup resources."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
        # Coordinator cleanup is handled by parent class