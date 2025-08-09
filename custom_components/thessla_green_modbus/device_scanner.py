"""POPRAWIONY Device scanner dla ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
FIX: Exception handling, register availability detection, diagnostics
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Union
import time

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ModbusException, ConnectionException
from pymodbus.pdu import ExceptionResponse
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
    """POPRAWIONY Enhanced device scanner z intelligent register detection.
    
    Naprawione problemy:
    - Exception code 2 (illegal data address) handling
    - Better register availability detection
    - Improved diagnostics and logging
    - pymodbus 3.5+ compatibility
    """
    
    def __init__(self, host: str, port: int, slave_id: int, timeout: int = DEFAULT_TIMEOUT, retry: int = DEFAULT_RETRY):
        """Initialize device scanner."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = max(timeout, 15)  # Minimum 15s timeout for scanning
        self.retry = max(retry, 3)       # Minimum 3 retries for scanning
        
        # Client connection
        self.client: Optional[AsyncModbusTcpClient] = None
        
        # Scan results
        self.available_registers: Dict[str, Dict[str, int]] = {
            "input": {},
            "holding": {},
            "coil": {},
            "discrete": {}
        }
        
        # Capabilities detection
        self.capabilities = DeviceCapabilities()
        
        # Statistics and diagnostics
        self.scan_stats = {
            "total_attempted": 0,
            "total_successful": 0,
            "successful_batches": 0,
            "failed_batches": 0,
            "scan_duration": 0.0,
            "connection_time": 0.0,
            "exception_count": 0,
            "timeout_count": 0,
        }
        
        # Error tracking
        self.error_log: List[Dict[str, Any]] = []
        
        # POPRAWKA: Exception tracking dla diagnostyki
        self.exception_codes = {
            1: "Illegal Function",
            2: "Illegal Data Address", 
            3: "Illegal Data Value",
            4: "Slave Device Failure",
            5: "Acknowledge",
            6: "Slave Device Busy",
            8: "Memory Parity Error",
            10: "Gateway Path Unavailable",
            11: "Gateway Target Device Failed to Respond"
        }
        
    def _log_error(self, error_type: str, message: str, details: Optional[Dict] = None):
        """Log error with timestamp and details."""
        error_entry = {
            "timestamp": datetime.now(),
            "type": error_type,
            "message": message,
            "details": details or {}
        }
        self.error_log.append(error_entry)
        
        # Keep only last 50 errors
        if len(self.error_log) > 50:
            self.error_log = self.error_log[-50:]
        
    async def connect(self) -> bool:
        """POPRAWIONE: Establish connection to device with retries."""
        connection_start = time.time()
        
        for attempt in range(self.retry):
            try:
                _LOGGER.debug("Connection attempt %d/%d to %s:%s", attempt + 1, self.retry, self.host, self.port)
                
                # Create fresh client for each attempt
                if self.client:
                    await self.disconnect()
                    
                # POPRAWKA: Nowe API pymodbus 3.5+
                self.client = AsyncModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout,
                    retries=1,  # Let scanner handle retries
                    retry_on_empty=True,
                    strict=False,
                )
                
                # POPRAWKA: Nowy sposób łączenia
                connected = await self.client.connect()
                
                if connected and self.client.connected:
                    self.scan_stats["connection_time"] = time.time() - connection_start
                    _LOGGER.info("Successfully connected to ThesslaGreen device at %s:%s", self.host, self.port)
                    return True
                    
                await asyncio.sleep(1)  # Brief delay between attempts
                
            except Exception as exc:
                self._log_error("connection_failed", f"Connection attempt {attempt + 1} failed: {exc}")
                _LOGGER.warning("Connection attempt %d failed: %s", attempt + 1, exc)
                await asyncio.sleep(2)  # Longer delay on error
                
        self._log_error("connection_failed", f"All {self.retry} connection attempts failed")
        return False
        
    async def disconnect(self):
        """POPRAWIONE: Safely disconnect from device."""
        try:
            if self.client and hasattr(self.client, 'close'):
                self.client.close()
        except Exception as exc:
            self._log_error("disconnect_error", f"Error during disconnect: {exc}")
            _LOGGER.debug("Error during disconnect: %s", exc)
        finally:
            self.client = None
    
    def _create_register_groups(self, register_map: Dict[str, int], max_gap: int = 5, max_batch: int = 16) -> List[Dict[str, Any]]:
        """Create optimized register groups for batch reading."""
        if not register_map:
            return []
            
        # Sort registers by address
        sorted_registers = sorted(register_map.items(), key=lambda x: x[1])
        groups = []
        current_group = {
            "start_address": sorted_registers[0][1],
            "registers": [sorted_registers[0][0]],
            "addresses": [sorted_registers[0][1]]
        }
        
        for name, address in sorted_registers[1:]:
            # Check if we can add this register to current group
            last_address = current_group["addresses"][-1]
            gap = address - last_address
            
            if gap <= max_gap and len(current_group["registers"]) < max_batch:
                # Add to current group
                current_group["registers"].append(name)
                current_group["addresses"].append(address)
            else:
                # Start new group
                groups.append(current_group)
                current_group = {
                    "start_address": address,
                    "registers": [name],
                    "addresses": [address]
                }
        
        # Add last group
        if current_group["registers"]:
            groups.append(current_group)
            
        # Calculate count and real register count for each group
        for group in groups:
            group["count"] = group["addresses"][-1] - group["start_address"] + 1
            group["real_count"] = len(group["registers"])
            
        return groups

    async def _scan_register_batch(self, register_type: str, start_address: int, count: int, register_names: List[str]) -> Dict[str, int]:
        """POPRAWIONE: Scan batch of registers with proper exception handling."""
        found_registers = {}
        
        try:
            self.scan_stats["total_attempted"] += 1
            
            # POPRAWKA: Wybór właściwej funkcji Modbus
            if register_type == "input":
                result = await self.client.read_input_registers(
                    address=start_address, count=count, slave=self.slave_id
                )
            elif register_type == "holding":
                result = await self.client.read_holding_registers(
                    address=start_address, count=count, slave=self.slave_id
                )
            elif register_type == "coil":
                result = await self.client.read_coils(
                    address=start_address, count=count, slave=self.slave_id
                )
            elif register_type == "discrete":
                result = await self.client.read_discrete_inputs(
                    address=start_address, count=count, slave=self.slave_id
                )
            else:
                raise ValueError(f"Unknown register type: {register_type}")
            
            # POPRAWKA: Obsługa exception responses
            if isinstance(result, ExceptionResponse):
                exception_code = result.exception_code
                exception_name = self.exception_codes.get(exception_code, f"Unknown ({exception_code})")
                
                if exception_code == 2:  # Illegal Data Address
                    _LOGGER.debug("Registers %s 0x%04X-0x%04X not available: %s", 
                                register_type, start_address, start_address + count - 1, exception_name)
                else:
                    _LOGGER.warning("Exception reading %s registers 0x%04X-0x%04X: %s", 
                                   register_type, start_address, start_address + count - 1, exception_name)
                
                self.scan_stats["exception_count"] += 1
                self._log_error("modbus_exception", f"Exception code {exception_code}: {exception_name}", {
                    "register_type": register_type,
                    "start_address": f"0x{start_address:04X}",
                    "count": count,
                    "exception_code": exception_code
                })
                return found_registers
            
            # POPRAWKA: Obsługa błędów
            if result.isError():
                error_msg = str(result)
                if "timeout" in error_msg.lower():
                    self.scan_stats["timeout_count"] += 1
                    
                _LOGGER.debug("Error reading %s batch 0x%04X-0x%04X: %s", 
                            register_type, start_address, start_address + count - 1, error_msg)
                self._log_error("read_error", f"Read error: {error_msg}", {
                    "register_type": register_type,
                    "start_address": f"0x{start_address:04X}",
                    "count": count
                })
                return found_registers
            
            # Success - mark all registers as found
            register_map = {}
            if register_type in ["input", "holding"]:
                register_map = {name: start_address + i for i, name in enumerate(register_names)}
            else:  # coil, discrete
                register_map = {name: start_address + i for i, name in enumerate(register_names)}
                
            found_registers.update(register_map)
            self.scan_stats["total_successful"] += 1
            self.scan_stats["successful_batches"] += 1
            
            _LOGGER.debug("Successfully read %d/%d registers from %s batch 0x%04X-0x%04X", 
                        len(register_names), count, register_type, start_address, start_address + count - 1)
            
        except asyncio.TimeoutError:
            self.scan_stats["timeout_count"] += 1
            self._log_error("timeout", f"Timeout reading {register_type} batch", {
                "start_address": f"0x{start_address:04X}",
                "count": count
            })
            _LOGGER.debug("Timeout reading %s batch 0x%04X-0x%04X", 
                        register_type, start_address, start_address + count - 1)
        except Exception as exc:
            self.scan_stats["failed_batches"] += 1
            self._log_error("scan_error", f"Unexpected error: {exc}", {
                "register_type": register_type,
                "start_address": f"0x{start_address:04X}",
                "count": count
            })
            _LOGGER.debug("Failed to read %s batch 0x%04X-0x%04X: %s", 
                        register_type, start_address, start_address + count - 1, exc)
            
        return found_registers

    async def _scan_registers(self, register_type: str, register_map: Dict[str, int]) -> Dict[str, int]:
        """POPRAWIONE: Scan registers of specific type with optimized batching."""
        _LOGGER.info("Scanning %s registers: %d total", register_type, len(register_map))
        
        # Create optimized register groups
        groups = self._create_register_groups(register_map)
        _LOGGER.debug("Created %d register groups for %s scanning", len(groups), register_type)
        
        found_registers = {}
        
        for i, group in enumerate(groups):
            # POPRAWKA: Lepsze logowanie
            _LOGGER.debug("Scanning %s batch 0x%04X-0x%04X (%d registers, %d real): %s", 
                        register_type, group["start_address"], 
                        group["start_address"] + group["count"] - 1,
                        group["count"], group["real_count"], group["registers"][:5])
            
            batch_result = await self._scan_register_batch(
                register_type, group["start_address"], group["count"], group["registers"]
            )
            found_registers.update(batch_result)
            
            # Small delay between batches to prevent overwhelming device
            if i < len(groups) - 1:
                await asyncio.sleep(0.2)
        
        _LOGGER.info("%s registers scan complete: %d/%d registers found", 
                   register_type.title(), len(found_registers), len(register_map))
        
        return found_registers

    def _analyze_capabilities(self):
        """POPRAWIONE: Analyze device capabilities from found registers."""
        all_registers = set()
        for reg_dict in self.available_registers.values():
            all_registers.update(reg_dict.keys())
        
        _LOGGER.debug("Analyzing capabilities from registers: input=%d, holding=%d, coil=%d, discrete=%d",
                    len(self.available_registers["input"]),
                    len(self.available_registers["holding"]),
                    len(self.available_registers["coil"]),
                    len(self.available_registers["discrete"]))
        
        # Temperature sensors
        temp_sensors = {"outside_temperature", "ambient_temperature", "exhaust_temperature", 
                       "supply_temperature", "gwc_temperature", "heating_temperature", "fpx_temperature"}
        found_temp = temp_sensors.intersection(all_registers)
        self.capabilities.has_temperature_sensors = len(found_temp) > 0
        _LOGGER.debug("Temperature sensors found: %s", found_temp)
        
        # Flow sensors
        flow_sensors = {"supply_flowrate", "exhaust_flowrate", "night_flow_rate"}
        found_flow = flow_sensors.intersection(all_registers)
        self.capabilities.has_flow_sensors = len(found_flow) > 0
        _LOGGER.debug("Flow sensors found: %s", found_flow)
        
        # GWC (Ground Water Cooler)
        gwc_indicators = {"gwc_temperature", "gwc"}
        found_gwc = gwc_indicators.intersection(all_registers)
        self.capabilities.has_gwc = len(found_gwc) > 0
        _LOGGER.debug("GWC indicators found: %s", found_gwc)
        
        # Bypass
        bypass_indicators = {"bypass"}
        found_bypass = bypass_indicators.intersection(all_registers)
        self.capabilities.has_bypass = len(found_bypass) > 0
        _LOGGER.debug("Bypass indicators found: %s", found_bypass)
        
        # Heating
        heating_indicators = {"heating_temperature", "duct_warter_heater_pump", "heating_cable"}
        found_heating = heating_indicators.intersection(all_registers)
        self.capabilities.has_heating = len(found_heating) > 0
        _LOGGER.debug("Heating indicators found: %s", found_heating)
        
        # Scheduling
        schedule_indicators = {reg for reg in all_registers if "schedule" in reg}
        self.capabilities.has_scheduling = len(schedule_indicators) > 0
        _LOGGER.debug("Schedule indicators found: %d registers", len(schedule_indicators))
        
        # Air quality sensors
        aq_sensors = {"humidity", "co2", "voc", "pressure"}
        found_aq = {reg for reg in all_registers if any(sensor in reg for sensor in aq_sensors)}
        self.capabilities.has_air_quality = len(found_aq) > 0
        _LOGGER.debug("Air quality sensors found: %s", found_aq)
        
        # Pressure sensors
        pressure_sensors = {reg for reg in all_registers if "pressure" in reg}
        self.capabilities.has_pressure_sensors = len(pressure_sensors) > 0
        _LOGGER.debug("Pressure sensors found: %s", pressure_sensors)
        
        # Filter monitoring
        filter_indicators = {"filter_change", "filter_monitoring"}
        found_filter = filter_indicators.intersection(all_registers)
        self.capabilities.has_filter_monitoring = len(found_filter) > 0
        _LOGGER.debug("Filter monitoring found: %s", found_filter)
        
        # Special functions
        special_functions = []
        if any("okap" in reg for reg in all_registers):
            special_functions.append("OKAP")
        if any("fireplace" in reg for reg in all_registers):
            special_functions.append("FIREPLACE")
        if any("vacation" in reg for reg in all_registers):
            special_functions.append("VACATION")
        self.capabilities.special_functions = special_functions
        _LOGGER.debug("Special functions found: %s", special_functions)
        
        # Operating modes
        operating_modes = []
        if any("auto" in reg for reg in all_registers):
            operating_modes.append("AUTO")
        if any("manual" in reg for reg in all_registers):
            operating_modes.append("MANUAL")  
        if any("boost" in reg for reg in all_registers):
            operating_modes.append("BOOST")
        self.capabilities.operating_modes = operating_modes
        _LOGGER.debug("Operating modes found: %s", operating_modes)

    async def scan_device(self) -> Optional[Dict[str, Any]]:
        """POPRAWIONE: Main device scanning function with comprehensive error handling."""
        scan_start = time.time()
        
        _LOGGER.info("Starting ThesslaGreen device scan at %s:%s (slave_id=%s)", 
                   self.host, self.port, self.slave_id)
        
        try:
            # Connect to device
            if not await self.connect():
                return None
            
            # Scan all register types
            register_types = [
                ("input", INPUT_REGISTERS),
                ("holding", HOLDING_REGISTERS), 
                ("coil", COIL_REGISTERS),
                ("discrete", DISCRETE_INPUTS)
            ]
            
            for reg_type, reg_map in register_types:
                if reg_map:  # Only scan if registers are defined
                    found_regs = await self._scan_registers(reg_type, reg_map)
                    self.available_registers[reg_type] = found_regs
            
            # Analyze capabilities
            self._analyze_capabilities()
            
            # Calculate scan statistics
            self.scan_stats["scan_duration"] = time.time() - scan_start
            total_registers = sum(len(regs) for regs in self.available_registers.values())
            total_defined = sum(len(reg_map) for _, reg_map in register_types if reg_map)
            
            _LOGGER.info("Device scan completed in %.2fs: %d/%d registers found across %d types", 
                       self.scan_stats["scan_duration"], total_registers, total_defined,
                       sum(1 for regs in self.available_registers.values() if regs))
            
            # Extract device info (may be limited if device doesn't fully respond)
            device_info = await self._extract_device_info()
            
            return {
                "available_registers": self.available_registers,
                "capabilities": self.capabilities.to_dict(),
                "device_info": device_info,
                "scan_stats": self.scan_stats,
                "error_log": self.error_log[-10:],  # Last 10 errors for diagnostics
            }
            
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            self._log_error("scan_failed", f"Device scan failed: {exc}")
            return None
        finally:
            await self.disconnect()

    async def _extract_device_info(self) -> Dict[str, Any]:
        """POPRAWIONE: Extract device information with fallbacks."""
        device_info = {
            "device_name": "ThesslaGreen AirPack",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "firmware_version": "Unknown",
            "serial_number": "Unknown",
        }
        
        try:
            # Try to read device identification if available
            if "device_name_1" in self.available_registers.get("holding", {}):
                # Try reading device name from registers
                result = await self.client.read_holding_registers(
                    address=0x1FD4, count=4, slave=self.slave_id
                )
                if not result.isError() and not isinstance(result, ExceptionResponse):
                    # Convert register values to string (if not zero)
                    name_parts = []
                    for val in result.registers:
                        if val != 0:
                            # Convert 16-bit value to 2 ASCII characters
                            char1 = (val >> 8) & 0xFF
                            char2 = val & 0xFF
                            if char1 > 0:
                                name_parts.append(chr(char1))
                            if char2 > 0:
                                name_parts.append(chr(char2))
                    if name_parts:
                        device_info["device_name"] = "".join(name_parts).strip()
            
            # Try to determine version from available features
            total_features = sum(len(regs) for regs in self.available_registers.values())
            if total_features > 50:
                device_info["firmware_version"] = "v3.x+ (Advanced)"
            elif total_features > 30:
                device_info["firmware_version"] = "v3.x (Standard)"
            else:
                device_info["firmware_version"] = "v2.x or Limited"
                
        except Exception as exc:
            _LOGGER.debug("Could not extract full device info: %s", exc)
            
        return device_info