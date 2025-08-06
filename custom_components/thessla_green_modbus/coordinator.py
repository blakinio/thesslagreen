"""Enhanced coordinator for ThesslaGreen Modbus integration - HA 2025.7+ & pymodbus 3.5+ Compatible."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, Dict, Set

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COIL_REGISTERS,
    DISCRETE_INPUTS,
    DOMAIN,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    REGISTER_GROUPS,
)

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator):
    """Enhanced coordinator for ThesslaGreen Modbus integration - HA 2025.7+ & pymodbus 3.5+ Compatible."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        scan_interval: int,
        timeout: int,
        retry: int,
        available_registers: Dict[str, Set[str]],
        device_info: Dict[str, Any] = None,
        capabilities: Set[str] = None,
    ) -> None:
        """Initialize the enhanced coordinator."""
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
        self.available_registers = available_registers
        self.device_info = device_info or {}
        self.capabilities = capabilities or set()
        
        # Enhanced optimization features (HA 2025.7+)
        self._consecutive_groups: Dict[str, list] = {}
        self._failed_registers: Set[str] = set()
        self._last_successful_read: Dict[str, float] = {}
        self._read_cache: Dict[str, Any] = {}
        self._batch_read_enabled = True
        
        # Performance metrics
        self._read_stats = {
            "total_reads": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "average_read_time": 0.0,
            "last_update_time": 0.0,
        }
        
        # Pre-compute consecutive register groups for batch reading
        self._initialize_register_groups()
        
        _LOGGER.info(
            "Enhanced coordinator initialized: %s:%s (slave_id=%s, interval=%ss, timeout=%ss)",
            host, port, slave_id, scan_interval, timeout
        )

    def _initialize_register_groups(self) -> None:
        """Pre-compute consecutive register groups for optimized batch reading."""
        _LOGGER.debug("Initializing optimized register groups for batch reading...")
        
        register_types = {
            "input_registers": INPUT_REGISTERS,
            "holding_registers": HOLDING_REGISTERS,
            "coil_registers": COIL_REGISTERS,
            "discrete_inputs": DISCRETE_INPUTS,
        }
        
        for reg_type, all_registers in register_types.items():
            available_keys = self.available_registers.get(reg_type, set())
            if not available_keys:
                continue
                
            # Get addresses for available registers
            available_addresses = {}
            for key in available_keys:
                if key in all_registers:
                    available_addresses[all_registers[key]] = key
            
            if not available_addresses:
                continue
            
            # Group consecutive addresses for batch reading
            sorted_addresses = sorted(available_addresses.keys())
            groups = []
            
            if sorted_addresses:
                current_start = sorted_addresses[0]
                current_end = sorted_addresses[0]
                current_keys = {0: available_addresses[current_start]}
                
                for addr in sorted_addresses[1:]:
                    if addr == current_end + 1:
                        # Consecutive address, extend current group
                        current_end = addr
                        current_keys[addr - current_start] = available_addresses[addr]
                    else:
                        # Non-consecutive, save current group and start new one
                        if len(current_keys) > 0:
                            groups.append((current_start, current_end - current_start + 1, current_keys))
                        
                        current_start = addr
                        current_end = addr
                        current_keys = {0: available_addresses[addr]}
                
                # Don't forget the last group
                if len(current_keys) > 0:
                    groups.append((current_start, current_end - current_start + 1, current_keys))
            
            self._consecutive_groups[reg_type] = groups
            
            _LOGGER.debug(
                "Optimized %s: %d registers grouped into %d batches",
                reg_type, len(available_keys), len(groups)
            )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from ThesslaGreen device with enhanced error handling and performance metrics."""
        start_time = time.time()
        
        try:
            data = await self.hass.async_add_executor_job(self._update_data_sync)
            
            if data:
                data = self._post_process_data(data)
                self._read_stats["successful_reads"] += 1
            else:
                self._read_stats["failed_reads"] += 1
                
            self._read_stats["total_reads"] += 1
            
            update_time = time.time() - start_time
            self._read_stats["last_update_time"] = update_time
            
            # Update average read time
            if self._read_stats["total_reads"] > 0:
                self._read_stats["average_read_time"] = (
                    self._read_stats["average_read_time"] * (self._read_stats["total_reads"] - 1) + update_time
                ) / self._read_stats["total_reads"]
            
            success_rate = (self._read_stats["successful_reads"] / self._read_stats["total_reads"]) * 100
            
            _LOGGER.debug(
                "Data update completed in %.2fs (avg: %.2fs, success rate: %.1f%%)",
                update_time,
                self._read_stats["average_read_time"],
                success_rate,
            )
            
            return data or {}
            
        except Exception as exc:
            self._read_stats["failed_reads"] += 1
            self._read_stats["total_reads"] += 1
            _LOGGER.error("Error updating data: %s", exc)
            raise UpdateFailed(f"Error communicating with device: {exc}")

    def _update_data_sync(self) -> Dict[str, Any]:
        """Synchronous data update with enhanced batch reading and error handling."""
        all_data = {}
        
        try:
            with ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
            ) as client:
                if not client.connect():
                    _LOGGER.error("Failed to connect to %s:%s", self.host, self.port)
                    return {}
                
                # Enhanced batch reading for optimal performance
                if self._batch_read_enabled:
                    all_data.update(self._read_input_registers_batch(client))
                    all_data.update(self._read_holding_registers_batch(client))
                    all_data.update(self._read_coil_registers_batch(client))
                    all_data.update(self._read_discrete_inputs_batch(client))
                
                return all_data
                
        except Exception as exc:
            _LOGGER.error("Modbus communication error: %s", exc)
            return {}

    def _read_input_registers_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of input registers - pymodbus 3.5+ Compatible."""
        data = {}
        groups = self._consecutive_groups.get("input_registers", [])
        
        for start_addr, count, key_map in groups:
            try:
                # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                response = client.read_input_registers(
                    address=start_addr, 
                    count=count, 
                    slave=self.slave_id
                )
                if response.isError():
                    _LOGGER.debug("Error reading input registers at %s: %s", start_addr, response)
                    continue
                    
                # ✅ FIXED: Process each register in the batch with correct indexing
                for offset, key in key_map.items():
                    if offset < len(response.registers):
                        raw_value = response.registers[offset]
                        processed_value = self._process_register_value(key, raw_value)
                        if processed_value is not None:
                            data[key] = processed_value
                        
            except Exception as exc:
                _LOGGER.debug("Failed to read input register batch at %s: %s", start_addr, exc)
                continue
                
        return data

    def _read_holding_registers_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of holding registers - pymodbus 3.5+ Compatible."""
        data = {}
        groups = self._consecutive_groups.get("holding_registers", [])
        
        for start_addr, count, key_map in groups:
            try:
                # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                response = client.read_holding_registers(
                    address=start_addr, 
                    count=count, 
                    slave=self.slave_id
                )
                if response.isError():
                    _LOGGER.debug("Error reading holding registers at %s: %s", start_addr, response)
                    continue
                    
                # ✅ FIXED: Process each register in the batch with correct indexing
                for offset, key in key_map.items():
                    if offset < len(response.registers):
                        raw_value = response.registers[offset]
                        processed_value = self._process_register_value(key, raw_value)
                        if processed_value is not None:
                            data[key] = processed_value
                        
            except Exception as exc:
                _LOGGER.debug("Failed to read holding register batch at %s: %s", start_addr, exc)
                continue
                
        return data

    def _read_coil_registers_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of coil registers - pymodbus 3.5+ Compatible."""
        data = {}
        groups = self._consecutive_groups.get("coil_registers", [])
        
        for start_addr, count, key_map in groups:
            try:
                # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                response = client.read_coils(
                    address=start_addr, 
                    count=count, 
                    slave=self.slave_id
                )
                if response.isError():
                    _LOGGER.debug("Error reading coils at %s: %s", start_addr, response)
                    continue
                    
                # ✅ FIXED: Process each coil in the batch with correct indexing
                for offset, key in key_map.items():
                    if offset < len(response.bits):
                        bit_value = response.bits[offset]
                        data[key] = bool(bit_value)
                    
            except Exception as exc:
                _LOGGER.debug("Failed to read coil batch at %s: %s", start_addr, exc)
                continue
                
        return data

    def _read_discrete_inputs_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of discrete inputs - pymodbus 3.5+ Compatible."""
        data = {}
        groups = self._consecutive_groups.get("discrete_inputs", [])
        
        for start_addr, count, key_map in groups:
            try:
                # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                response = client.read_discrete_inputs(
                    address=start_addr, 
                    count=count, 
                    slave=self.slave_id
                )
                if response.isError():
                    _LOGGER.debug("Error reading discrete inputs at %s: %s", start_addr, response)
                    continue
                    
                # ✅ FIXED: Process each discrete input in the batch with correct indexing
                for offset, key in key_map.items():
                    if offset < len(response.bits):
                        bit_value = response.bits[offset]
                        data[key] = bool(bit_value)
                    
            except Exception as exc:
                _LOGGER.debug("Failed to read discrete input batch at %s: %s", start_addr, exc)
                continue
                
        return data

    def _process_register_value(self, key: str, raw_value: int) -> Any:
        """Enhanced register value processing with better validation."""
        try:
            # Handle different value types based on register key
            if "temperature" in key:
                # Temperature values are typically in 0.1°C units
                if raw_value == 0x8000 or raw_value > 32767:  # Invalid/disconnected sensor
                    return None
                # Convert signed 16-bit
                if raw_value > 32767:
                    raw_value = raw_value - 65536
                return raw_value  # Return raw value, conversion handled in entities
                
            elif "percentage" in key or "efficiency" in key:
                # Percentage values 0-100%
                if 0 <= raw_value <= 100:
                    return raw_value
                return None
                
            elif "flow" in key and "rate" in key:
                # Flow rate values in m³/h
                if 0 <= raw_value <= 1000:
                    return raw_value
                return None
                
            elif key in ["mode", "special_mode", "comfort_mode", "gwc_mode", "bypass_mode"]:
                # Mode values - validate range
                if 0 <= raw_value <= 20:  # Reasonable mode range
                    return raw_value
                return None
                
            elif "error_code" in key or "warning_code" in key:
                # Error/warning codes
                if 0 <= raw_value <= 50:  # Reasonable code range
                    return raw_value
                return None
                
            else:
                # Generic integer values
                if 0 <= raw_value <= 65535:  # Valid 16-bit unsigned range
                    return raw_value
                return None
                
        except (ValueError, TypeError) as exc:
            _LOGGER.debug("Failed to process register %s value %s: %s", key, raw_value, exc)
            return None

    def _post_process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced post-processing with validation and derived values."""
        if not data:
            return data
            
        try:
            # Convert temperature values from raw to actual temperatures (0.1°C resolution)
            for temp_key in ["outside_temperature", "supply_temperature", "exhaust_temperature", "extract_temperature"]:
                if temp_key in data and data[temp_key] is not None:
                    data[temp_key] = data[temp_key] / 10.0
                    
            # Calculate derived values if base values are available
            if ("supply_temperature" in data and "exhaust_temperature" in data and 
                "outside_temperature" in data and data["supply_temperature"] is not None and
                data["exhaust_temperature"] is not None and data["outside_temperature"] is not None):
                
                supply_temp = data["supply_temperature"]
                exhaust_temp = data["exhaust_temperature"]
                outside_temp = data["outside_temperature"]
                
                # Calculate heat recovery efficiency
                temp_diff_total = abs(outside_temp - exhaust_temp)
                temp_diff_recovered = abs(supply_temp - outside_temp)
                
                if temp_diff_total > 0:
                    efficiency = (temp_diff_recovered / temp_diff_total) * 100
                    data["calculated_efficiency"] = min(max(efficiency, 0), 100)  # Clamp to 0-100%
                    
            # Calculate flow balance if both flow rates are available
            if ("supply_flowrate" in data and "exhaust_flowrate" in data and
                data["supply_flowrate"] is not None and data["exhaust_flowrate"] is not None):
                
                supply_flow = data["supply_flowrate"]
                exhaust_flow = data["exhaust_flowrate"]
                
                data["flow_balance"] = supply_flow - exhaust_flow
                
                # Determine flow balance status
                balance_diff = abs(data["flow_balance"])
                if balance_diff <= 5:  # Within 5 m³/h tolerance
                    data["flow_balance_status"] = "balanced"
                elif data["flow_balance"] > 0:
                    data["flow_balance_status"] = "supply_dominant"
                else:
                    data["flow_balance_status"] = "exhaust_dominant"
                    
        except (ValueError, TypeError, KeyError) as exc:
            _LOGGER.debug("Error in post-processing: %s", exc)
            
        return data

    async def async_write_register(self, key: str, value: Any) -> bool:
        """Write a single register value with enhanced error handling."""
        if key not in HOLDING_REGISTERS and key not in COIL_REGISTERS:
            _LOGGER.error("Attempted to write to read-only or unknown register: %s", key)
            return False
            
        try:
            success = await self.hass.async_add_executor_job(
                self._write_register_sync, key, value
            )
            
            if success:
                # Refresh data after successful write
                await self.async_request_refresh()
                
            return success
            
        except Exception as exc:
            _LOGGER.error("Error writing register %s: %s", key, exc)
            return False

    def _write_register_sync(self, key: str, value: Any) -> bool:
        """Synchronous register write operation."""
        try:
            with ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
            ) as client:
                if not client.connect():
                    _LOGGER.error("Failed to connect for register write")
                    return False
                    
                if key in HOLDING_REGISTERS:
                    address = HOLDING_REGISTERS[key]
                    # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                    response = client.write_register(
                        address=address,
                        value=int(value),
                        slave=self.slave_id
                    )
                elif key in COIL_REGISTERS:
                    address = COIL_REGISTERS[key]
                    # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                    response = client.write_coil(
                        address=address,
                        value=bool(value),
                        slave=self.slave_id
                    )
                else:
                    return False
                    
                if response.isError():
                    _LOGGER.error("Modbus write error for %s: %s", key, response)
                    return False
                    
                _LOGGER.debug("Successfully wrote %s = %s", key, value)
                return True
                
        except Exception as exc:
            _LOGGER.error("Exception during register write: %s", exc)
            return False

    @property
    def performance_stats(self) -> Dict[str, Any]:
        """Return performance statistics."""
        success_rate = 0.0
        if self._read_stats["total_reads"] > 0:
            success_rate = (self._read_stats["successful_reads"] / self._read_stats["total_reads"]) * 100
            
        return {
            "status": "connected" if self.last_update_success else "disconnected",
            "total_reads": self._read_stats["total_reads"],
            "successful_reads": self._read_stats["successful_reads"],
            "failed_reads": self._read_stats["failed_reads"],
            "success_rate": success_rate,
            "average_read_time": self._read_stats["average_read_time"],
            "last_update_time": self._read_stats["last_update_time"],
            "failed_registers": len(self._failed_registers),
        }

    @property
    def last_update_success_time(self) -> Any:
        """Return last successful update time - compatible with entity expectations."""
        from datetime import datetime
        
        # Return current datetime if last update was successful
        if self.last_update_success:
            return datetime.now()
        
        # Return None if no successful update
        return None

    @property
    def device_scan_result(self) -> Dict[str, Any]:
        """Return device scan result - compatibility property."""
        return {
            "device_info": self.device_info,
            "capabilities": self.capabilities,
        }

    @device_scan_result.setter
    def device_scan_result(self, value: Dict[str, Any]) -> None:
        """Update device scan result and related attributes."""
        if not isinstance(value, dict):
            raise ValueError("device_scan_result must be a dictionary")

        self.device_info = value.get("device_info", {})
        self.capabilities = value.get("capabilities", set())
