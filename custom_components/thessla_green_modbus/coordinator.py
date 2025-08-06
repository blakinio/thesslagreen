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
            data = await self.hass.async_add_executor_job(self._fetch_modbus_data)
            
            # Update performance metrics
            read_time = time.time() - start_time
            self._read_stats["total_reads"] += 1
            self._read_stats["successful_reads"] += 1
            self._read_stats["last_update_time"] = read_time
            
            # Calculate rolling average
            current_avg = self._read_stats["average_read_time"]
            self._read_stats["average_read_time"] = (current_avg * 0.9) + (read_time * 0.1)
            
            _LOGGER.debug(
                "Data update completed in %.2fs (avg: %.2fs, success rate: %.1f%%)",
                read_time,
                self._read_stats["average_read_time"],
                (self._read_stats["successful_reads"] / self._read_stats["total_reads"]) * 100
            )
            
            return data
            
        except Exception as exc:
            self._read_stats["total_reads"] += 1
            self._read_stats["failed_reads"] += 1
            _LOGGER.error("Enhanced coordinator update failed: %s", exc)
            raise UpdateFailed(f"Error communicating with device: {exc}")

    def _fetch_modbus_data(self) -> Dict[str, Any]:
        """Enhanced Modbus data fetching with batch optimization - pymodbus 3.5+ Compatible."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        data = {}
        
        try:
            if not client.connect():
                raise UpdateFailed("Failed to connect to Modbus device")
            
            # Enhanced batch reading for each register type (HA 2025.7+ & pymodbus 3.5+)
            register_readers = {
                "input_registers": self._read_input_registers_batch,
                "holding_registers": self._read_holding_registers_batch,
                "coil_registers": self._read_coil_registers_batch,
                "discrete_inputs": self._read_discrete_inputs_batch,
            }
            
            for reg_type, reader_func in register_readers.items():
                if reg_type in self._consecutive_groups:
                    try:
                        reg_data = reader_func(client)
                        data.update(reg_data)
                    except Exception as exc:
                        _LOGGER.warning("Failed to read %s: %s", reg_type, exc)
                        # Continue with other register types
                        continue
            
            # Post-process data with enhanced validation
            data = self._post_process_data(data)
            
        finally:
            client.close()
            
        return data

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
                    
                # Process each register in the batch
                for key, offset in key_map.items():
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
                    
                for key, offset in key_map.items():
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
                    
                for key, offset in key_map.items():
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
                    
                for key, offset in key_map.items():
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
        # Remove None values
        processed_data = {k: v for k, v in data.items() if v is not None}
        
        # Calculate derived values
        try:
            # Calculate heat recovery efficiency if we have temperatures
            outside_temp = processed_data.get("outside_temperature")
            supply_temp = processed_data.get("supply_temperature")
            exhaust_temp = processed_data.get("exhaust_temperature")
            
            if all(t is not None for t in [outside_temp, supply_temp, exhaust_temp]):
                try:
                    # Convert from 0.1°C units to °C
                    outside_c = outside_temp / 10.0
                    supply_c = supply_temp / 10.0
                    exhaust_c = exhaust_temp / 10.0
                    
                    if abs(outside_c - exhaust_c) > 1.0:  # Avoid division by zero
                        efficiency = ((supply_c - outside_c) / (exhaust_c - outside_c)) * 100
                        if 0 <= efficiency <= 100:
                            processed_data["calculated_efficiency"] = round(efficiency, 1)
                except (ZeroDivisionError, ValueError):
                    pass
            
            # Calculate flow balance
            supply_flow = processed_data.get("supply_flowrate")
            exhaust_flow = processed_data.get("exhaust_flowrate")
            
            if supply_flow is not None and exhaust_flow is not None:
                flow_balance = supply_flow - exhaust_flow
                processed_data["flow_balance"] = flow_balance
                
                # Flow balance status
                if abs(flow_balance) < 10:
                    processed_data["flow_balance_status"] = "balanced"
                elif flow_balance > 0:
                    processed_data["flow_balance_status"] = "supply_dominant"
                else:
                    processed_data["flow_balance_status"] = "exhaust_dominant"
            
        except Exception as exc:
            _LOGGER.debug("Error in post-processing: %s", exc)
        
        return processed_data

    async def async_write_register(self, register_key: str, value: int) -> bool:
        """Enhanced register writing with better error handling - pymodbus 3.5+ Compatible."""
        # Check if register is writable (only holding registers and coils)
        if register_key in HOLDING_REGISTERS:
            register_address = HOLDING_REGISTERS[register_key]
            register_type = "holding"
        elif register_key in COIL_REGISTERS:
            register_address = COIL_REGISTERS[register_key]
            register_type = "coil"
        else:
            _LOGGER.error("Register %s is not writable", register_key)
            return False
        
        try:
            success = await self.hass.async_add_executor_job(
                self._write_register_sync, register_address, value, register_type
            )
            
            if success:
                # Update local data cache for immediate UI feedback
                self.data[register_key] = value
                # Request refresh to get actual device state
                await self.async_request_refresh()
                _LOGGER.debug("Successfully wrote %s = %d", register_key, value)
                return True
            else:
                _LOGGER.error("Failed to write register %s", register_key)
                return False
                
        except Exception as exc:
            _LOGGER.error("Exception writing register %s: %s", register_key, exc)
            return False

    def _write_register_sync(self, address: int, value: int, register_type: str) -> bool:
        """Synchronous register writing - pymodbus 3.5+ Compatible."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            if not client.connect():
                return False
            
            if register_type == "holding":
                # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                response = client.write_register(
                    address=address, 
                    value=value, 
                    slave=self.slave_id
                )
            elif register_type == "coil":
                # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                response = client.write_coil(
                    address=address, 
                    value=bool(value), 
                    slave=self.slave_id
                )
            else:
                return False
            
            return not response.isError()
            
        except Exception as exc:
            _LOGGER.debug("Error writing register %d: %s", address, exc)
            return False
        finally:
            client.close()

    @property 
    def device_info(self) -> Dict[str, Any]:
        """Return device information for entity registry."""
        return {
            "identifiers": {(DOMAIN, f"{self.host}_{self.slave_id}")},
            "name": f"ThesslaGreen ({self.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": self.device_scan_result.get("device_info", {}).get("firmware", "Unknown"),
            "configuration_url": f"http://{self.host}",
        }

    @property
    def performance_stats(self) -> Dict[str, Any]:
        """Return coordinator performance statistics."""
        total_reads = self._read_stats["total_reads"]
        if total_reads == 0:
            return {"status": "no_data"}
        
        success_rate = (self._read_stats["successful_reads"] / total_reads) * 100
        
        return {
            "total_reads": total_reads,
            "successful_reads": self._read_stats["successful_reads"],
            "failed_reads": self._read_stats["failed_reads"],
            "success_rate": round(success_rate, 1),
            "average_read_time": round(self._read_stats["average_read_time"], 2),
            "last_update_time": round(self._read_stats["last_update_time"], 2),
            "batch_groups": {k: len(v) for k, v in self._consecutive_groups.items()},
        }