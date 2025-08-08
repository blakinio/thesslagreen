"""Enhanced device scanner for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
Autoscan rejestrów + diagnostyka + logowanie błędów
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Union
import time

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ModbusException, ConnectionException
from homeassistant.exceptions import HomeAssistantError

from .const import (
    INPUT_REGISTERS, HOLDING_REGISTERS, COIL_REGISTERS, DISCRETE_INPUTS,
    DEFAULT_TIMEOUT, DEFAULT_RETRY
)

_LOGGER = logging.getLogger(__name__)

class DeviceCapabilities:
    """Represents detected device capabilities."""
    
    def __init__(self):
        self.has_temperature_sensors = False
        self.has_flow_sensors = False
        self.has_gwc = False
        self.has_bypass = False
        self.has_heating = False
        self.has_scheduling = False
        self.has_air_quality = False
        self.has_pressure_sensors = False
        self.has_filter_monitoring = False
        self.has_constant_flow = False
        self.special_functions = []
        self.operating_modes = []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "temperature_sensors": self.has_temperature_sensors,
            "flow_sensors": self.has_flow_sensors,
            "gwc": self.has_gwc,
            "bypass": self.has_bypass,
            "heating": self.has_heating,
            "scheduling": self.has_scheduling,
            "air_quality": self.has_air_quality,
            "pressure_sensors": self.has_pressure_sensors,
            "filter_monitoring": self.has_filter_monitoring,
            "constant_flow": self.has_constant_flow,
            "special_functions": self.special_functions,
            "operating_modes": self.operating_modes,
        }


class ThesslaGreenDeviceScanner:
    """Enhanced device scanner with intelligent register detection.
    Kompatybilne z HA 2025.* + pymodbus 3.5.*+
    Wykrywa wszystkie dostępne rejestry automatycznie.
    """
    
    def __init__(self, host: str, port: int, slave_id: int, timeout: int = DEFAULT_TIMEOUT, retry_count: int = DEFAULT_RETRY):
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry_count = retry_count
        self.client: Optional[AsyncModbusTcpClient] = None
        
        # Scanning configuration
        self.max_batch_size = 16  # Max registers per batch read (ograniczenie MODBUS)
        self.max_gap_size = 8     # Max gap between registers to include in batch
        
        # Results storage
        self.available_registers: Dict[str, Set[str]] = {
            "input": set(),
            "holding": set(),
            "coil": set(),
            "discrete": set()
        }
        
        # Diagnostics and statistics
        self.scan_stats = {
            "scan_start_time": 0,
            "scan_duration": 0,
            "total_attempted": 0,
            "total_successful": 0,
            "register_types_found": 0,
            "input_registers_found": 0,
            "holding_registers_found": 0,
            "coil_registers_found": 0,
            "discrete_registers_found": 0,
            "connection_errors": 0,
            "modbus_errors": 0,
            "timeout_errors": 0,
            "successful_batches": 0,
            "failed_batches": 0,
        }
        
        # Error tracking for diagnostics
        self.error_log: List[Dict[str, Any]] = []
        
    async def connect(self) -> bool:
        """Establish Modbus connection with retry logic."""
        if self.client is not None:
            try:
                await self.client.close()
            except Exception:
                pass
                
        self.client = AsyncModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout,
        )
        
        for attempt in range(self.retry_count):
            try:
                _LOGGER.debug("Connection attempt %d/%d to %s:%d", attempt + 1, self.retry_count, self.host, self.port)
                
                # AsyncModbusTcpClient w pymodbus 3.5+ używa connect() bez await
                success = await self.client.connect()
                if success:
                    _LOGGER.info("Successfully connected to ThesslaGreen device at %s:%d", self.host, self.port)
                    return True
                else:
                    _LOGGER.warning("Connection attempt %d failed", attempt + 1)
                    
            except ConnectionException as exc:
                self.scan_stats["connection_errors"] += 1
                self._log_error("connection", f"Connection error on attempt {attempt + 1}: {exc}")
                _LOGGER.warning("Connection error on attempt %d: %s", attempt + 1, exc)
                
            except Exception as exc:
                self.scan_stats["connection_errors"] += 1
                self._log_error("connection", f"Unexpected error on attempt {attempt + 1}: {exc}")
                _LOGGER.error("Unexpected connection error on attempt %d: %s", attempt + 1, exc)
                
            if attempt < self.retry_count - 1:
                await asyncio.sleep(1)
                
        _LOGGER.error("Failed to connect to device after %d attempts", self.retry_count)
        return False
        
    async def disconnect(self):
        """Disconnect from device."""
        if self.client:
            try:
                await self.client.close()
                _LOGGER.debug("Disconnected from device")
            except Exception as exc:
                _LOGGER.warning("Error during disconnect: %s", exc)
            finally:
                self.client = None
                
    def _log_error(self, error_type: str, message: str, register_info: Optional[Dict] = None):
        """Log error for diagnostics."""
        error_entry = {
            "timestamp": time.time(),
            "type": error_type,
            "message": message,
            "register_info": register_info or {},
        }
        self.error_log.append(error_entry)
        
        # Keep only last 50 errors
        if len(self.error_log) > 50:
            self.error_log = self.error_log[-50:]
            
    def _group_registers_by_range(self, registers: Dict[str, int], max_gap: int = 8) -> List[Dict[str, Any]]:
        """Group registers by address ranges for efficient batch reading.
        
        Args:
            registers: Dict of register_name -> address
            max_gap: Maximum gap between registers to include in same batch
            
        Returns:
            List of register groups for batch reading
        """
        if not registers:
            return []
            
        # Sort registers by address
        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        groups = []
        current_group = {"start": sorted_regs[0][1], "registers": [sorted_regs[0][0]], "addresses": [sorted_regs[0][1]]}
        
        for reg_name, address in sorted_regs[1:]:
            # Check if we can add to current group
            last_addr = current_group["addresses"][-1]
            gap = address - last_addr
            
            if (gap <= max_gap and 
                len(current_group["registers"]) < self.max_batch_size and
                address - current_group["start"] < self.max_batch_size):
                
                # Fill gaps with placeholders
                for gap_addr in range(last_addr + 1, address):
                    current_group["registers"].append(f"_gap_{gap_addr}")
                    current_group["addresses"].append(gap_addr)
                    
                current_group["registers"].append(reg_name)
                current_group["addresses"].append(address)
            else:
                # Start new group
                groups.append(current_group)
                current_group = {"start": address, "registers": [reg_name], "addresses": [address]}
                
        groups.append(current_group)
        return groups
        
    async def _read_register_batch_safe(self, function_code: str, start_addr: int, count: int, register_names: List[str]) -> Dict[str, bool]:
        """Safely read a batch of registers with comprehensive error handling."""
        results = {}
        
        try:
            if function_code == "input":
                response = await self.client.read_input_registers(start_addr, count, slave=self.slave_id)
            elif function_code == "holding":
                response = await self.client.read_holding_registers(start_addr, count, slave=self.slave_id)
            elif function_code == "coil":
                response = await self.client.read_coils(start_addr, count, slave=self.slave_id)
            elif function_code == "discrete":
                response = await self.client.read_discrete_inputs(start_addr, count, slave=self.slave_id)
            else:
                self._log_error("invalid_function", f"Unknown function code: {function_code}")
                return results
                
            if response.isError():
                self.scan_stats["modbus_errors"] += 1
                self.scan_stats["failed_batches"] += 1
                self._log_error("modbus_error", f"Modbus error: {response}", 
                              {"function": function_code, "start": start_addr, "count": count})
                _LOGGER.debug("Modbus error reading %s 0x%04X-0x%04X: %s", function_code, start_addr, start_addr + count - 1, response)
                return results
                
            self.scan_stats["successful_batches"] += 1
            
            # Process results
            if function_code in ["input", "holding"]:
                values = response.registers
            else:  # coil, discrete
                values = response.bits
                
            for i, reg_name in enumerate(register_names):
                if not reg_name.startswith("_gap_"):  # Skip gap placeholders
                    if i < len(values):
                        # Validate register value
                        if self._is_valid_register_value(reg_name, values[i]):
                            results[reg_name] = True
                            self.scan_stats["total_successful"] += 1
                        else:
                            results[reg_name] = False
                            _LOGGER.debug("Invalid value for %s: %s", reg_name, values[i])
                    else:
                        results[reg_name] = False
                        
        except asyncio.TimeoutError:
            self.scan_stats["timeout_errors"] += 1
            self.scan_stats["failed_batches"] += 1
            self._log_error("timeout", f"Timeout reading {function_code} registers at 0x{start_addr:04X}")
            _LOGGER.debug("Timeout reading %s registers 0x%04X-0x%04X", function_code, start_addr, start_addr + count - 1)
            
        except ModbusIOException as exc:
            self.scan_stats["modbus_errors"] += 1
            self.scan_stats["failed_batches"] += 1
            self._log_error("modbus_io", str(exc), {"function": function_code, "start": start_addr, "count": count})
            _LOGGER.debug("Modbus IO error reading %s 0x%04X-0x%04X: %s", function_code, start_addr, start_addr + count - 1, exc)
            
        except ModbusException as exc:
            self.scan_stats["modbus_errors"] += 1
            self.scan_stats["failed_batches"] += 1
            self._log_error("modbus_protocol", str(exc), {"function": function_code, "start": start_addr, "count": count})
            _LOGGER.debug("Modbus protocol error reading %s 0x%04X-0x%04X: %s", function_code, start_addr, start_addr + count - 1, exc)
            
        except Exception as exc:
            self.scan_stats["modbus_errors"] += 1
            self.scan_stats["failed_batches"] += 1
            self._log_error("unexpected", str(exc), {"function": function_code, "start": start_addr, "count": count})
            _LOGGER.warning("Unexpected error reading %s 0x%04X-0x%04X: %s", function_code, start_addr, start_addr + count - 1, exc)
            
        return results
        
    def _is_valid_register_value(self, register_name: str, value: Union[int, bool]) -> bool:
        """Validate register value based on register type and expected ranges."""
        if isinstance(value, bool):
            return True  # Boolean values are always valid
            
        if not isinstance(value, int):
            return False
            
        # Temperature sensors - 0x8000 means sensor not available
        if "temperature" in register_name:
            if value == 0x8000 or value == 32768:
                return False  # Sensor not available
            # Valid temperature range: -99.9°C to +99.9°C (in 0.1°C units)
            if value > 32767:  # Handle negative temperatures
                temp_value = (value - 65536) * 0.1
            else:
                temp_value = value * 0.1
            return -100.0 <= temp_value <= 100.0
            
        # Flow rates and percentages
        if any(x in register_name for x in ["flow", "percentage", "speed"]):
            return 0 <= value <= 65535  # Allow full range for flow sensors
            
        # General register value range
        return 0 <= value <= 65535
        
    async def _scan_register_type(self, register_type: str, registers: Dict[str, int]) -> List[str]:
        """Scan specific register type with optimized batch reading."""
        if not registers:
            return []
            
        _LOGGER.info("Scanning %s registers: %d total", register_type, len(registers))
        self.scan_stats["total_attempted"] += len(registers)
        
        # Group registers for efficient reading
        groups = self._group_registers_by_range(registers, self.max_gap_size)
        available = []
        
        _LOGGER.debug("Created %d register groups for %s scanning", len(groups), register_type)
        
        for group in groups:
            start_addr = group["start"]
            register_names = group["registers"]
            count = len(register_names)
            
            # Filter out gap placeholders for logging
            real_registers = [name for name in register_names if not name.startswith("_gap_")]
            _LOGGER.debug("Scanning %s batch 0x%04X-0x%04X (%d registers, %d real): %s", 
                         register_type, start_addr, start_addr + count - 1, count, len(real_registers), real_registers[:5])
            
            # Read batch with error handling
            batch_results = await self._read_register_batch_safe(register_type, start_addr, count, register_names)
            
            if batch_results:
                available.extend([name for name, is_available in batch_results.items() if is_available])
                
        _LOGGER.info("%s registers scan complete: %d/%d registers found", register_type.title(), len(available), len(registers))
        
        # Update type-specific statistics
        if register_type == "input":
            self.scan_stats["input_registers_found"] = len(available)
        elif register_type == "holding":
            self.scan_stats["holding_registers_found"] = len(available)
        elif register_type == "coil":
            self.scan_stats["coil_registers_found"] = len(available)
        elif register_type == "discrete":
            self.scan_stats["discrete_registers_found"] = len(available)
            
        return available
        
    async def scan_device(self) -> Optional[Dict[str, Any]]:
        """Perform comprehensive device scan with diagnostics."""
        _LOGGER.info("Starting comprehensive device scan for %s:%d (slave_id=%d)", self.host, self.port, self.slave_id)
        
        self.scan_stats["scan_start_time"] = time.time()
        
        try:
            # Connect to device
            if not await self.connect():
                return None
                
            # Scan all register types
            self.available_registers["input"] = set(await self._scan_register_type("input", INPUT_REGISTERS))
            self.available_registers["holding"] = set(await self._scan_register_type("holding", HOLDING_REGISTERS))
            self.available_registers["coil"] = set(await self._scan_register_type("coil", COIL_REGISTERS))
            self.available_registers["discrete"] = set(await self._scan_register_type("discrete", DISCRETE_INPUTS))
            
            # Calculate final statistics
            self.scan_stats["scan_duration"] = time.time() - self.scan_stats["scan_start_time"]
            
            total_found = sum(len(regs) for regs in self.available_registers.values())
            self.scan_stats["register_types_found"] = sum(1 for regs in self.available_registers.values() if regs)
            
            _LOGGER.info("Device scan completed in %.2fs: %d/%d registers found across %d types", 
                        self.scan_stats["scan_duration"], total_found, self.scan_stats["total_attempted"], 
                        self.scan_stats["register_types_found"])
            
            if total_found == 0:
                _LOGGER.error("No valid registers found - device may not be ThesslaGreen AirPack or connection issue")
                return None
                
            # Extract device information
            device_info = await self._extract_device_info()
            
            # Analyze capabilities
            capabilities = self._analyze_capabilities()
            
            # Create scan result
            scan_result = {
                "available_registers": {
                    "input_registers": self.available_registers["input"],
                    "holding_registers": self.available_registers["holding"],
                    "coil_registers": self.available_registers["coil"], 
                    "discrete_inputs": self.available_registers["discrete"],
                },
                "device_info": device_info,
                "capabilities": capabilities.to_dict(),
                "scan_statistics": self.scan_stats.copy(),
                "diagnostics": {
                    "error_log": self.error_log.copy(),
                    "success_rate": self.scan_stats["total_successful"] / max(1, self.scan_stats["total_attempted"]) * 100,
                    "batch_success_rate": self.scan_stats["successful_batches"] / max(1, self.scan_stats["successful_batches"] + self.scan_stats["failed_batches"]) * 100,
                }
            }
            
            _LOGGER.info("Device scan result: %.1f%% register success rate, %.1f%% batch success rate",
                        scan_result["diagnostics"]["success_rate"],
                        scan_result["diagnostics"]["batch_success_rate"])
            
            return scan_result
            
        except Exception as exc:
            self._log_error("scan_failed", f"Device scan failed: {exc}")
            _LOGGER.error("Device scan failed: %s", exc, exc_info=True)
            return None
            
        finally:
            await self.disconnect()
            
    async def _extract_device_info(self) -> Dict[str, Any]:
        """Extract device information from available registers."""
        device_info = {
            "device_name": f"ThesslaGreen AirPack",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home Serie 4",
        }
        
        if not self.client:
            return device_info
            
        try:
            # Try to read firmware version
            if all(reg in self.available_registers["input"] for reg in ["firmware_major", "firmware_minor"]):
                try:
                    major_response = await self.client.read_input_registers(INPUT_REGISTERS["firmware_major"], 1, slave=self.slave_id)
                    minor_response = await self.client.read_input_registers(INPUT_REGISTERS["firmware_minor"], 1, slave=self.slave_id)
                    
                    if not major_response.isError() and not minor_response.isError():
                        major = major_response.registers[0]
                        minor = minor_response.registers[0]
                        
                        # Try to read patch version if available
                        patch = 0
                        if "firmware_patch" in self.available_registers["input"]:
                            patch_response = await self.client.read_input_registers(INPUT_REGISTERS["firmware_patch"], 1, slave=self.slave_id)
                            if not patch_response.isError():
                                patch = patch_response.registers[0]
                                
                        device_info["firmware"] = f"{major}.{minor}.{patch}"
                        device_info["device_name"] = f"ThesslaGreen AirPack (v{major}.{minor})"
                        
                except Exception as exc:
                    _LOGGER.debug("Failed to read firmware version: %s", exc)
                    
            # Try to read serial number
            serial_parts = []
            for i in range(1, 7):
                reg_name = f"serial_number_{i}"
                if reg_name in self.available_registers["input"]:
                    try:
                        response = await self.client.read_input_registers(INPUT_REGISTERS[reg_name], 1, slave=self.slave_id)
                        if not response.isError() and response.registers[0] != 0:
                            serial_parts.append(f"{response.registers[0]:04X}")
                    except Exception:
                        continue
                        
            if serial_parts:
                device_info["serial_number"] = "".join(serial_parts)
                
            # Add connection info
            device_info["host"] = self.host
            device_info["port"] = self.port
            device_info["slave_id"] = self.slave_id
            
        except Exception as exc:
            _LOGGER.warning("Error extracting device info: %s", exc)
            
        return device_info
        
    def _analyze_capabilities(self) -> DeviceCapabilities:
        """Analyze available registers to determine device capabilities."""
        capabilities = DeviceCapabilities()
        
        input_regs = self.available_registers["input"]
        holding_regs = self.available_registers["holding"]
        coil_regs = self.available_registers["coil"]
        discrete_regs = self.available_registers["discrete"]
        
        # Temperature sensors
        temp_sensors = {"outside_temperature", "supply_temperature", "exhaust_temperature", 
                       "fpx_temperature", "duct_supply_temperature", "gwc_temperature", "ambient_temperature"}
        capabilities.has_temperature_sensors = bool(input_regs & temp_sensors)
        
        # Flow sensors
        flow_sensors = {"supply_flowrate", "exhaust_flowrate", "supply_percentage", "exhaust_percentage"}
        capabilities.has_flow_sensors = bool(input_regs & flow_sensors)
        
        # GWC system
        gwc_registers = {"gwc_temperature", "gwc_mode", "gwc_activation_temp", "gwc"} 
        capabilities.has_gwc = bool((input_regs | holding_regs | coil_regs) & gwc_registers)
        
        # Bypass system
        bypass_registers = {"bypass", "bypass_activation_temp", "bypassing_factor"}
        capabilities.has_bypass = bool((input_regs | holding_regs | coil_regs) & bypass_registers)
        
        # Heating system
        heating_registers = {"duct_supply_temperature", "heating_cable", "duct_warter_heater_pump"}
        capabilities.has_heating = bool((input_regs | coil_regs) & heating_registers)
        
        # Scheduling
        schedule_registers = {reg for reg in holding_regs if "schedule" in reg}
        capabilities.has_scheduling = len(schedule_registers) > 0
        
        # Air quality
        air_quality_registers = {"co2_concentration", "voc_level", "humidity", "air_quality"}
        capabilities.has_air_quality = bool(input_regs & air_quality_registers)
        
        # Pressure sensors
        pressure_registers = {"supply_pressure", "exhaust_pressure", "filter_pressure"}
        capabilities.has_pressure_sensors = bool(input_regs & pressure_registers)
        
        # Filter monitoring
        filter_registers = {"filter_time_remaining", "filter_operating_hours", "filter_alarm"}
        capabilities.has_filter_monitoring = bool((input_regs | holding_regs) & filter_registers)
        
        # Constant flow
        constant_flow_registers = {"constant_flow_active", "constant_pressure_setpoint"}
        capabilities.has_constant_flow = bool((input_regs | holding_regs) & constant_flow_registers)
        
        # Special functions
        special_functions = []
        if "okap_mode" in holding_regs or "hood" in coil_regs:
            special_functions.append("OKAP")
        if "kominek_mode" in holding_regs:
            special_functions.append("KOMINEK")
        if "wietrzenie_mode" in holding_regs:
            special_functions.append("WIETRZENIE")
        if "pusty_dom_mode" in holding_regs:
            special_functions.append("PUSTY_DOM")
        if "boost_mode" in holding_regs:
            special_functions.append("BOOST")
            
        capabilities.special_functions = special_functions
        
        # Operating modes
        operating_modes = []
        if "mode" in holding_regs:
            operating_modes.extend(["AUTO", "MANUAL", "TEMPORARY"])
        if "on_off_panel_mode" in holding_regs:
            operating_modes.append("ON_OFF")
            
        capabilities.operating_modes = operating_modes
        
        _LOGGER.info("Device capabilities detected: temp=%s, flow=%s, gwc=%s, bypass=%s, heating=%s, special=%s",
                    capabilities.has_temperature_sensors, capabilities.has_flow_sensors,
                    capabilities.has_gwc, capabilities.has_bypass, capabilities.has_heating,
                    capabilities.special_functions)
        
        return capabilities