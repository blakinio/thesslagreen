"""Enhanced coordinator for ThesslaGreen Modbus integration.
Kompletna obsługa wszystkich rejestrów z diagnostyką i logowaniem błędów.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple

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
    REGISTER_PROCESSING,
)

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator):
    """Enhanced coordinator with comprehensive register support and diagnostics."""

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
        scan_statistics: Dict[str, Any] | None = None,
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
        self.scan_statistics = scan_statistics or {}
        self.device_info_data = device_info or {}
        self.capabilities = capabilities or set()
        
        # Performance tracking
        self._performance_stats = {
            "total_updates": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "last_update_time": None,
            "last_update_duration": 0,
            "average_update_time": 0,
            "error_count": 0,
            "last_error": None,
            "communication_errors": 0,
            "timeout_errors": 0,
            "register_read_stats": {},
            "unavailable_registers": set(),
            "intermittent_registers": set(),
        }
        
        # Enhanced register grouping for optimized batch reads
        self._consecutive_groups = {}
        self._initialize_register_groups()
        
        # Register value cache with validation
        self._register_cache = {}
        self._register_timestamps = {}
        self._register_error_counts = {}
        
        _LOGGER.info(
            "ThesslaGreen coordinator initialized: %s:%s (slave_id=%s), %d register types, %s capabilities",
            host, port, slave_id, 
            len([k for k, v in available_registers.items() if v]),
            len([k for k, v in (capabilities or {}).items() if v]) if isinstance(capabilities, dict) else len(capabilities or [])
        )

    def _initialize_register_groups(self) -> None:
        """Initialize optimized register groups for batch reading with enhanced error handling."""
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
                self._consecutive_groups[reg_type] = []
                continue
                
            # Get addresses for available registers
            available_addresses = {}
            for key in available_keys:
                if key in all_registers:
                    available_addresses[all_registers[key]] = key
            
            if not available_addresses:
                self._consecutive_groups[reg_type] = []
                continue
            
            # Group consecutive addresses for batch reading with size limits
            sorted_addresses = sorted(available_addresses.keys())
            groups = []
            
            if sorted_addresses:
                max_batch_size = 16  # Modbus limit for safety
                max_gap = 10  # Maximum gap between registers to include in same batch
                
                current_start = sorted_addresses[0]
                current_end = sorted_addresses[0]
                current_keys = {0: available_addresses[current_start]}
                
                for addr in sorted_addresses[1:]:
                    gap = addr - current_end
                    batch_size = len(current_keys)
                    
                    if gap <= max_gap and batch_size < max_batch_size:
                        # Consecutive address or small gap, extend current group
                        current_end = addr
                        current_keys[addr - current_start] = available_addresses[addr]
                    else:
                        # Large gap or batch full, save current group and start new one
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
                "Optimized %s: %d registers grouped into %d batches (avg %.1f registers/batch)",
                reg_type, len(available_keys), len(groups),
                len(available_keys) / len(groups) if groups else 0
            )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from ThesslaGreen device with enhanced error handling and diagnostics."""
        start_time = time.time()
        self._performance_stats["total_updates"] += 1
        
        try:
            data = await self.hass.async_add_executor_job(self._update_data_sync)
            
            # Update performance stats
            duration = time.time() - start_time
            self._performance_stats["successful_updates"] += 1
            self._performance_stats["last_update_time"] = datetime.now()
            self._performance_stats["last_update_duration"] = duration
            
            # Calculate rolling average
            if self._performance_stats["successful_updates"] > 1:
                old_avg = self._performance_stats["average_update_time"]
                count = self._performance_stats["successful_updates"]
                self._performance_stats["average_update_time"] = (
                    (old_avg * (count - 1) + duration) / count
                )
            else:
                self._performance_stats["average_update_time"] = duration
            
            # Validate data quality
            data_quality = self._validate_data_quality(data)
            data["_system_info"] = {
                "update_duration": duration,
                "data_quality": data_quality,
                "register_count": len(data),
                "timestamp": datetime.now().isoformat(),
                "coordinator_stats": self._performance_stats.copy(),
            }
            
            _LOGGER.debug(
                "Data update completed: %.3fs, %d registers, %.1f%% quality",
                duration, len(data), data_quality * 100
            )
            
            return data
            
        except Exception as exc:
            self._performance_stats["failed_updates"] += 1
            self._performance_stats["last_error"] = str(exc)
            self._performance_stats["error_count"] += 1
            
            # Classify error type
            if "timeout" in str(exc).lower():
                self._performance_stats["timeout_errors"] += 1
            elif "connection" in str(exc).lower() or "modbus" in str(exc).lower():
                self._performance_stats["communication_errors"] += 1
            
            _LOGGER.error(
                "Data update failed after %.3fs: %s (total errors: %d)",
                time.time() - start_time, exc, self._performance_stats["error_count"]
            )
            raise UpdateFailed(f"Error communicating with device: {exc}")

    def _update_data_sync(self) -> Dict[str, Any]:
        """Synchronous data update with comprehensive error handling."""
        data = {}
        
        try:
            with ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
            ) as client:
                if not client.connect():
                    raise UpdateFailed(f"Failed to connect to {self.host}:{self.port}")
                
                _LOGGER.debug("Connected to device, reading register batches...")
                
                # Read all register types with batch optimization
                for reg_type in ["input_registers", "holding_registers", "coil_registers", "discrete_inputs"]:
                    if reg_type in self.available_registers and self.available_registers[reg_type]:
                        try:
                            reg_data = self._read_register_type_batch(client, reg_type)
                            data.update(reg_data)
                            _LOGGER.debug(
                                "Read %d %s successfully", 
                                len(reg_data), reg_type.replace('_', ' ')
                            )
                        except Exception as exc:
                            _LOGGER.warning(
                                "Failed to read %s: %s", 
                                reg_type.replace('_', ' '), exc
                            )
                            # Continue with other register types
                            continue
                
                # Update register statistics
                self._update_register_stats(data)
                
        except Exception as exc:
            _LOGGER.error("Synchronous data update failed: %s", exc)
            raise
            
        return data

    def _read_register_type_batch(self, client: ModbusTcpClient, reg_type: str) -> Dict[str, Any]:
        """Read a specific register type using optimized batch operations."""
        data = {}
        groups = self._consecutive_groups.get(reg_type, [])
        
        # Map register type to read function
        read_functions = {
            "input_registers": self._read_input_registers_batch,
            "holding_registers": self._read_holding_registers_batch,
            "coil_registers": self._read_coil_registers_batch,
            "discrete_inputs": self._read_discrete_inputs_batch,
        }
        
        if reg_type in read_functions:
            return read_functions[reg_type](client)
        
        return data

    def _read_input_registers_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of input registers - pymodbus 3.5+ Compatible."""
        data = {}
        groups = self._consecutive_groups.get("input_registers", [])
        
        for start_addr, count, key_map in groups:
            try:
                # pymodbus 3.5+ requires keyword arguments
                response = client.read_input_registers(
                    address=start_addr, 
                    count=count, 
                    slave=self.slave_id
                )
                if response.isError():
                    _LOGGER.debug("Error reading input registers at 0x%04X: %s", start_addr, response)
                    self._handle_register_error(start_addr, list(key_map.values()), "input_registers")
                    continue
                    
                # Process each register in the batch with validation
                for offset, key in key_map.items():
                    if offset < len(response.registers):
                        raw_value = response.registers[offset]
                        processed_value = self._process_register_value(key, raw_value, "input")
                        if processed_value is not None:
                            data[key] = processed_value
                            self._update_register_success(key)
                        else:
                            _LOGGER.debug("Invalid value for %s: 0x%04X", key, raw_value)
                            self._handle_register_error(start_addr + offset, [key], "input_registers")
                        
            except Exception as exc:
                _LOGGER.debug("Failed to read input register batch at 0x%04X: %s", start_addr, exc)
                self._handle_register_error(start_addr, list(key_map.values()), "input_registers")
                continue
                
        return data

    def _read_holding_registers_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of holding registers - pymodbus 3.5+ Compatible."""
        data = {}
        groups = self._consecutive_groups.get("holding_registers", [])
        
        for start_addr, count, key_map in groups:
            try:
                # pymodbus 3.5+ requires keyword arguments
                response = client.read_holding_registers(
                    address=start_addr, 
                    count=count, 
                    slave=self.slave_id
                )
                if response.isError():
                    _LOGGER.debug("Error reading holding registers at 0x%04X: %s", start_addr, response)
                    self._handle_register_error(start_addr, list(key_map.values()), "holding_registers")
                    continue
                    
                # Process each register in the batch with validation
                for offset, key in key_map.items():
                    if offset < len(response.registers):
                        raw_value = response.registers[offset]
                        processed_value = self._process_register_value(key, raw_value, "holding")
                        if processed_value is not None:
                            data[key] = processed_value
                            self._update_register_success(key)
                        else:
                            _LOGGER.debug("Invalid value for %s: 0x%04X", key, raw_value)
                            self._handle_register_error(start_addr + offset, [key], "holding_registers")
                        
            except Exception as exc:
                _LOGGER.debug("Failed to read holding register batch at 0x%04X: %s", start_addr, exc)
                self._handle_register_error(start_addr, list(key_map.values()), "holding_registers")
                continue
                
        return data

    def _read_coil_registers_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of coil registers - pymodbus 3.5+ Compatible."""
        data = {}
        groups = self._consecutive_groups.get("coil_registers", [])
        
        for start_addr, count, key_map in groups:
            try:
                # pymodbus 3.5+ requires keyword arguments
                response = client.read_coils(
                    address=start_addr, 
                    count=count, 
                    slave=self.slave_id
                )
                if response.isError():
                    _LOGGER.debug("Error reading coils at 0x%04X: %s", start_addr, response)
                    self._handle_register_error(start_addr, list(key_map.values()), "coil_registers")
                    continue
                    
                # Process each coil in the batch
                for offset, key in key_map.items():
                    if offset < len(response.bits):
                        bit_value = response.bits[offset]
                        data[key] = bool(bit_value)
                        self._update_register_success(key)
                    
            except Exception as exc:
                _LOGGER.debug("Failed to read coil batch at 0x%04X: %s", start_addr, exc)
                self._handle_register_error(start_addr, list(key_map.values()), "coil_registers")
                continue
                
        return data

    def _read_discrete_inputs_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of discrete inputs - pymodbus 3.5+ Compatible."""
        data = {}
        groups = self._consecutive_groups.get("discrete_inputs", [])
        
        for start_addr, count, key_map in groups:
            try:
                # pymodbus 3.5+ requires keyword arguments
                response = client.read_discrete_inputs(
                    address=start_addr, 
                    count=count, 
                    slave=self.slave_id
                )
                if response.isError():
                    _LOGGER.debug("Error reading discrete inputs at 0x%04X: %s", start_addr, response)
                    self._handle_register_error(start_addr, list(key_map.values()), "discrete_inputs")
                    continue
                    
                # Process each discrete input in the batch
                for offset, key in key_map.items():
                    if offset < len(response.bits):
                        bit_value = response.bits[offset]
                        data[key] = bool(bit_value)
                        self._update_register_success(key)
                    
            except Exception as exc:
                _LOGGER.debug("Failed to read discrete input batch at 0x%04X: %s", start_addr, exc)
                self._handle_register_error(start_addr, list(key_map.values()), "discrete_inputs")
                continue
                
        return data

    def _process_register_value(self, key: str, raw_value: int, reg_type: str) -> Any:
        """Enhanced register value processing with comprehensive validation and conversion."""
        # Store raw value for debugging
        self._register_cache[key] = raw_value
        self._register_timestamps[key] = time.time()
        
        # Temperature registers - 0.1°C resolution, handle 0x8000 (no sensor)
        if key in REGISTER_PROCESSING["temperature_registers"]:
            if raw_value == REGISTER_PROCESSING["sensor_unavailable_value"]:
                return None  # Sensor not available
            # Convert to actual temperature with sign handling
            if raw_value > 32767:  # Handle negative temperatures (two's complement)
                temperature = (raw_value - 65536) * 0.1
            else:
                temperature = raw_value * 0.1
            # Sanity check for reasonable temperature range
            if -50.0 <= temperature <= 100.0:
                return round(temperature, 1)
            return None
        
        # Temperature registers with 0.5°C resolution (some comfort settings)
        if key in ["required_temp", "comfort_temperature"] and "temperature" in key:
            if raw_value == REGISTER_PROCESSING["sensor_unavailable_value"]:
                return None
            temperature = raw_value * 0.5
            if 0.0 <= temperature <= 50.0:
                return round(temperature, 1)
            return None
        
        # Percentage registers - 0-100% or extended ranges
        if key in REGISTER_PROCESSING["percentage_registers"]:
            if 0 <= raw_value <= 200:  # Allow extended range
                return raw_value
            return None
        
        # Flow rate registers - m³/h
        if key in REGISTER_PROCESSING["flow_registers"]:
            if raw_value == REGISTER_PROCESSING["invalid_flow_value"]:
                return None  # Invalid flow reading
            if 0 <= raw_value <= 2000:  # Reasonable flow range
                return raw_value
            return None
        
        # Pressure registers - Pa
        if key in REGISTER_PROCESSING["pressure_registers"]:
            if 0 <= raw_value <= 10000:  # Up to 10kPa
                return raw_value
            return None
        
        # Time registers - HHMM format
        if key in REGISTER_PROCESSING["time_registers"]:
            hours = (raw_value >> 8) & 0xFF
            minutes = raw_value & 0xFF
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                return f"{hours:02d}:{minutes:02d}"
            return None
        
        # Mode and enumeration registers
        if "mode" in key:
            if 0 <= raw_value <= 10:  # Reasonable mode range
                return raw_value
            return None
        
        # Filter type register
        if key == "filter_type":
            if 1 <= raw_value <= 4:
                filter_types = {1: "presostat", 2: "płaskie", 3: "CleanPad", 4: "CleanPad Pure"}
                return {"value": raw_value, "description": filter_types.get(raw_value, "unknown")}
            return None
        
        # Serial number components
        if "serial_number" in key:
            if raw_value not in [0, 0xFFFF]:  # Valid serial number part
                return f"{raw_value:04X}"
            return None
        
        # Firmware version components
        if "firmware" in key:
            if 0 < raw_value < 1000:
                return raw_value
            return None
        
        # Device name components (ASCII encoded)
        if "device_name" in key:
            if raw_value != 0:
                char1 = chr((raw_value >> 8) & 0xFF) if (raw_value >> 8) & 0xFF != 0 else ""
                char2 = chr(raw_value & 0xFF) if raw_value & 0xFF != 0 else ""
                return char1 + char2
            return ""
        
        # Error and alarm registers
        if "error" in key or "alarm" in key:
            return raw_value  # Keep original value for error analysis
        
        # Compilation time registers
        if key == "compilation_days":
            if 0 <= raw_value <= 20000:  # Reasonable days since 2000
                return raw_value
            return None
        
        if key == "compilation_seconds":
            if 0 <= raw_value <= 86400:  # Seconds in a day
                return raw_value
            return None
        
        # Operating hours and counters
        if "hours" in key or "interval" in key or "remaining" in key:
            if 0 <= raw_value <= 100000:  # Reasonable counter value
                return raw_value
            return None
        
        # Energy and power registers
        if "energy" in key or "power" in key:
            if 0 <= raw_value <= 50000:  # Reasonable energy/power range
                return raw_value
            return None
        
        # Default: return raw value for unprocessed registers with basic validation
        if 0 <= raw_value <= 65535:
            return raw_value
        
        return None

    def _handle_register_error(self, address: int, register_keys: List[str], reg_type: str) -> None:
        """Handle register read errors with detailed tracking."""
        for key in register_keys:
            if key not in self._register_error_counts:
                self._register_error_counts[key] = 0
            self._register_error_counts[key] += 1
            
            # Mark as unavailable if consistently failing
            if self._register_error_counts[key] > 5:
                self._performance_stats["unavailable_registers"].add(key)
                _LOGGER.warning(
                    "Register %s (0x%04X) marked as unavailable after %d consecutive errors",
                    key, address, self._register_error_counts[key]
                )
            elif self._register_error_counts[key] > 2:
                self._performance_stats["intermittent_registers"].add(key)

    def _update_register_success(self, key: str) -> None:
        """Update register success statistics."""
        # Reset error count on successful read
        if key in self._register_error_counts:
            self._register_error_counts[key] = 0
        
        # Remove from problem sets
        self._performance_stats["unavailable_registers"].discard(key)
        self._performance_stats["intermittent_registers"].discard(key)
        
        # Update read statistics
        if key not in self._performance_stats["register_read_stats"]:
            self._performance_stats["register_read_stats"][key] = {
                "success_count": 0,
                "last_success": None,
            }
        
        self._performance_stats["register_read_stats"][key]["success_count"] += 1
        self._performance_stats["register_read_stats"][key]["last_success"] = time.time()

    def _update_register_stats(self, data: Dict[str, Any]) -> None:
        """Update comprehensive register statistics."""
        current_time = time.time()
        
        for key, value in data.items():
            if not key.startswith("_"):  # Skip system info
                self._update_register_success(key)

    def _validate_data_quality(self, data: Dict[str, Any]) -> float:
        """Calculate data quality score based on successful reads vs expected registers."""
        if not data:
            return 0.0
        
        total_expected = sum(len(regs) for regs in self.available_registers.values())
        actual_reads = len([k for k in data.keys() if not k.startswith("_")])
        
        if total_expected == 0:
            return 1.0
        
        return min(actual_reads / total_expected, 1.0)

    async def async_write_register(self, key: str, value: Any) -> bool:
        """Write to a register with enhanced error handling and validation."""
        if key not in HOLDING_REGISTERS and key not in COIL_REGISTERS:
            _LOGGER.error("Attempted to write to read-only or unknown register: %s", key)
            return False
        
        # Validate value before writing
        if not self._validate_write_value(key, value):
            _LOGGER.error("Invalid value %s for register %s", value, key)
            return False
            
        try:
            success = await self.hass.async_add_executor_job(
                self._write_register_sync, key, value
            )
            
            if success:
                # Update cache and request refresh
                self._register_cache[key] = value
                await self.async_request_refresh()
                _LOGGER.info("Successfully wrote %s = %s", key, value)
            else:
                _LOGGER.error("Failed to write %s = %s", key, value)
                
            return success
            
        except Exception as exc:
            _LOGGER.error("Error writing register %s: %s", key, exc)
            return False

    def _validate_write_value(self, key: str, value: Any) -> bool:
        """Validate value before writing to register."""
        # Temperature registers
        if key in REGISTER_PROCESSING["temperature_registers"]:
            try:
                temp_val = float(value)
                return -50.0 <= temp_val <= 100.0
            except (ValueError, TypeError):
                return False
        
        # Percentage registers
        if key in REGISTER_PROCESSING["percentage_registers"]:
            try:
                pct_val = int(value)
                return 0 <= pct_val <= 200
            except (ValueError, TypeError):
                return False
        
        # Mode registers
        if "mode" in key:
            try:
                mode_val = int(value)
                return 0 <= mode_val <= 10
            except (ValueError, TypeError):
                return False
        
        # Boolean values for coils
        if key in COIL_REGISTERS:
            return isinstance(value, (bool, int)) and value in [0, 1, True, False]
        
        # Default validation
        try:
            int_val = int(value)
            return 0 <= int_val <= 65535
        except (ValueError, TypeError):
            return False

    def _write_register_sync(self, key: str, value: Any) -> bool:
        """Synchronous register write operation with enhanced error handling."""
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
                    # Convert value for register format
                    if key in REGISTER_PROCESSING["temperature_registers"]:
                        # Convert temperature to register format
                        if "comfort" in key or "required" in key:
                            reg_value = int(float(value) * 2)  # 0.5°C resolution
                        else:
                            reg_value = int(float(value) * 10)  # 0.1°C resolution
                    else:
                        reg_value = int(value)
                    
                    # pymodbus 3.5+ requires keyword arguments
                    response = client.write_register(
                        address=address,
                        value=reg_value,
                        slave=self.slave_id
                    )
                elif key in COIL_REGISTERS:
                    address = COIL_REGISTERS[key]
                    # pymodbus 3.5+ requires keyword arguments
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
                    
                _LOGGER.debug("Successfully wrote %s = %s to address 0x%04X", key, value, address)
                return True
                
        except Exception as exc:
            _LOGGER.error("Exception during register write: %s", exc)
            return False

    @property
    def performance_stats(self) -> Dict[str, Any]:
        """Return comprehensive performance statistics."""
        stats = self._performance_stats.copy()
        
        # Add derived statistics
        if stats["total_updates"] > 0:
            stats["success_rate"] = (stats["successful_updates"] / stats["total_updates"]) * 100
            stats["error_rate"] = (stats["failed_updates"] / stats["total_updates"]) * 100
        
        # Add register availability statistics
        total_available = sum(len(regs) for regs in self.available_registers.values())
        stats["total_available_registers"] = total_available
        stats["unavailable_register_count"] = len(stats["unavailable_registers"])
        stats["intermittent_register_count"] = len(stats["intermittent_registers"])
        
        if total_available > 0:
            stats["register_availability"] = (
                (total_available - len(stats["unavailable_registers"])) / total_available * 100
            )
        
        # Add device info
        stats["device_info"] = self.device_info_data
        stats["scan_statistics"] = self.scan_statistics
        
        return stats

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information for Home Assistant device registry."""
        info = {
            "identifiers": {(DOMAIN, f"{self.host}_{self.slave_id}")},
            "name": f"ThesslaGreen AirPack ({self.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home Serie 4",
            "sw_version": self.device_info_data.get("firmware_version", "Unknown"),
        }
        
        # Add serial number if available
        if "serial_number" in self.device_info_data:
            info["serial_number"] = self.device_info_data["serial_number"]
        
        # Add configuration URL
        info["configuration_url"] = f"http://{self.host}"
        
        return info

    async def async_shutdown(self) -> None:
        """Shutdown coordinator gracefully."""
        _LOGGER.info("Shutting down ThesslaGreen coordinator")
        
        # Log final statistics
        stats = self.performance_stats
        _LOGGER.info(
            "Final stats: %d updates (%.1f%% success), %.3fs avg duration, %d errors",
            stats.get("total_updates", 0),
            stats.get("success_rate", 0),
            stats.get("average_update_time", 0),
            stats.get("error_count", 0)
        )
        
        # Clear caches
        self._register_cache.clear()
        self._register_timestamps.clear()
        self._register_error_counts.clear()