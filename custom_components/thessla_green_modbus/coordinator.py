"""Optimized data coordinator for ThesslaGreen Modbus integration - Enhanced Performance."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    DOMAIN,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    INVALID_TEMPERATURE,
    INVALID_FLOW,
)
from .device_scanner import ThesslaGreenDeviceScanner

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Optimized coordinator for ThesslaGreen Modbus communication."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        scan_interval: int,
        timeout: int,
        retry: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        self.available_registers: dict[str, set[str]] = {}
        self.device_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        
        # Performance optimization: pre-computed register groups
        self._register_groups: dict[str, list[tuple[int, int, dict[str, int]]]] = {}
        self._last_successful_read: dict[str, float] = {}
        self._failed_registers: set[str] = set()

    async def async_config_entry_first_refresh(self) -> None:
        """Perform initial refresh including device scanning."""
        _LOGGER.info("Starting optimized device scan...")
        
        # Scan device capabilities first
        scanner = ThesslaGreenDeviceScanner(self.host, self.port, self.slave_id)
        
        try:
            scan_result = await scanner.scan_device()
            self.available_registers = scan_result["available_registers"]
            self.device_info = scan_result["device_info"]
            self.capabilities = scan_result["capabilities"]
            
            # Pre-compute register groups for optimal reading
            self._precompute_register_groups()
            
            _LOGGER.info(
                "Optimized device scan successful. Found %d registers, %d capabilities",
                sum(len(regs) for regs in self.available_registers.values()),
                len([k for k, v in self.capabilities.items() if v])
            )
            
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            # Set minimal configuration for basic operation
            self.available_registers = {"input_registers": set(), "holding_registers": set()}
            self.device_info = {"device_name": "ThesslaGreen", "firmware": "Unknown"}
            self.capabilities = {}
        
        # Perform initial data refresh
        await super().async_config_entry_first_refresh()

    def _precompute_register_groups(self) -> None:
        """Precompute optimal register groups for batch reading."""
        self._register_groups = {
            "input_registers": self._group_registers(INPUT_REGISTERS, self.available_registers.get("input_registers", set())),
            "holding_registers": self._group_registers(HOLDING_REGISTERS, self.available_registers.get("holding_registers", set())),
            "coil_registers": self._group_registers(COIL_REGISTERS, self.available_registers.get("coil_registers", set())),
            "discrete_inputs": self._group_registers(DISCRETE_INPUT_REGISTERS, self.available_registers.get("discrete_inputs", set())),
        }
        
        total_groups = sum(len(groups) for groups in self._register_groups.values())
        _LOGGER.debug("Precomputed %d optimized register groups", total_groups)

    def _group_registers(self, register_map: dict, available_keys: set) -> list[tuple[int, int, dict[str, int]]]:
        """Group consecutive registers for batch reading."""
        if not available_keys:
            return []
        
        # Filter available registers and sort by address
        available_regs = {key: addr for key, addr in register_map.items() if key in available_keys}
        if not available_regs:
            return []
        
        sorted_regs = sorted(available_regs.items(), key=lambda x: x[1])
        groups = []
        current_group = []
        
        for key, addr in sorted_regs:
            if not current_group:
                current_group.append((key, addr))
            elif addr == current_group[-1][1] + 1:
                current_group.append((key, addr))
            else:
                # Process current group
                if current_group:
                    groups.append(self._create_group(current_group))
                current_group = [(key, addr)]
        
        # Process last group
        if current_group:
            groups.append(self._create_group(current_group))
        
        return groups

    def _create_group(self, registers: list[tuple[str, int]]) -> tuple[int, int, dict[str, int]]:
        """Create a register group tuple."""
        start_addr = registers[0][1]
        count = len(registers)
        key_map = {key: i for i, (key, _) in enumerate(registers)}
        return (start_addr, count, key_map)

    async def _async_update_data(self) -> dict[str, Any]:
        """Optimized data update using batch reading."""
        return await asyncio.get_event_loop().run_in_executor(None, self._update_data_sync)

    def _update_data_sync(self) -> dict[str, Any]:
        """Synchronous optimized data update."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        data = {}
        
        try:
            if not client.connect():
                raise UpdateFailed("Could not connect to device")
            
            # Read input registers
            data.update(self._read_register_groups(client, "input_registers", client.read_input_registers))
            
            # Read holding registers
            data.update(self._read_register_groups(client, "holding_registers", client.read_holding_registers))
            
            # Read coils
            data.update(self._read_register_groups(client, "coil_registers", client.read_coils))
            
            # Read discrete inputs
            data.update(self._read_register_groups(client, "discrete_inputs", client.read_discrete_inputs))
            
        except Exception as exc:
            _LOGGER.error("Data update failed: %s", exc)
            raise UpdateFailed(f"Error communicating with device: {exc}") from exc
        finally:
            client.close()
        
        return data

    def _read_register_groups(self, client, register_type: str, read_func) -> dict[str, Any]:
        """Read register groups with optimized batch operations."""
        data = {}
        groups = self._register_groups.get(register_type, [])
        
        for start_addr, count, key_map in groups:
            try:
                response = read_func(start_addr, count, slave=self.slave_id)
                
                if response.isError():
                    _LOGGER.debug("Error reading %s group at 0x%04X: %s", register_type, start_addr, response)
                    continue
                
                # Extract values based on register type
                if register_type in ["input_registers", "holding_registers"]:
                    values = response.registers
                else:  # coils or discrete inputs
                    values = response.bits[:count]
                
                # Map values to keys
                for key, offset in key_map.items():
                    if offset < len(values):
                        raw_value = values[offset]
                        data[key] = self._process_register_value(key, raw_value)
                        
            except Exception as exc:
                _LOGGER.debug("Exception reading %s group at 0x%04X: %s", register_type, start_addr, exc)
                continue
        
        return data

    def _process_register_value(self, key: str, raw_value: Any) -> Any:
        """Process raw register value based on key type."""
        # Temperature processing
        if "temperature" in key:
            if raw_value == INVALID_TEMPERATURE or raw_value > 1000:
                return None
            return round(raw_value / 10.0, 1) if raw_value > 100 else raw_value
        
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

    async def async_write_register(self, key: str, value: int) -> bool:
        """Optimized register writing with retry logic."""
        if key not in HOLDING_REGISTERS:
            _LOGGER.error("Unknown register key: %s", key)
            return False

        register_address = HOLDING_REGISTERS[key]
        
        for attempt in range(self.retry):
            try:
                success = await asyncio.get_event_loop().run_in_executor(
                    None, self._write_register_sync, register_address, value
                )
                if success:
                    return True
                    
                if attempt < self.retry - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))  # Progressive delay
                    
            except Exception as exc:
                _LOGGER.debug("Write attempt %d failed for register %s: %s", attempt + 1, key, exc)
                if attempt < self.retry - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))

        _LOGGER.error("Failed to write register %s after %d attempts", key, self.retry)
        return False

    def _write_register_sync(self, address: int, value: int) -> bool:
        """Optimized synchronous register writing."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            if not client.connect():
                return False

            result = client.write_register(address, value, slave=self.slave_id)
            if result.isError():
                _LOGGER.debug("Error writing register 0x%04X: %s", address, result)
                return False

            _LOGGER.debug("Successfully wrote value %s to register 0x%04X", value, address)
            return True

        except Exception as exc:
            _LOGGER.debug("Exception writing register 0x%04X: %s", address, exc)
            return False
        finally:
            client.close()

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down optimized coordinator")
        self._register_groups.clear()
        self._failed_registers.clear()