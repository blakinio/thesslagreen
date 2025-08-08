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
            "connection_time": 0.0
        }
        
        # Error tracking
        self.error_log: List[Dict[str, Any]] = []
        
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
        """Establish connection to device with retries."""
        connection_start = time.time()
        
        for attempt in range(self.retry):
            try:
                _LOGGER.debug("Connection attempt %d/%d to %s:%s", attempt + 1, self.retry, self.host, self.port)
                
                # Create fresh client for each attempt
                if self.client:
                    await self.disconnect()
                    
                self.client = AsyncModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout
                )
                
                # Connect - pymodbus 3.5+ compatible
                await self.client.connect()
                
                if self.client.connected:
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
        """Safely disconnect from device."""
        try:
            if self.client and hasattr(self.client, 'close') and self.client.connected:
                self.client.close()
        except Exception as exc:
            self._log_error("disconnect_error", f"Error during disconnect: {exc}")
            _LOGGER.warning("Error during disconnect: %s", exc)
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
            gap = address - current_group["addresses"][-1]
            
            # Start new group if gap too large or batch too big
            if gap > max_gap or len(current_group["addresses"]) >= max_batch:
                current_group["count"] = current_group["addresses"][-1] - current_group["start_address"] + 1
                current_group["real_count"] = len(current_group["registers"])
                groups.append(current_group)
                
                current_group = {
                    "start_address": address,
                    "registers": [name],
                    "addresses": [address]
                }
            else:
                current_group["registers"].append(name)
                current_group["addresses"].append(address)
        
        # Add final group
        if current_group["registers"]:
            current_group["count"] = current_group["addresses"][-1] - current_group["start_address"] + 1
            current_group["real_count"] = len(current_group["registers"])
            groups.append(current_group)
            
        return groups
    
    async def _read_register_batch(self, register_type: str, group: Dict[str, Any]) -> Dict[str, int]:
        """Read a batch of registers with pymodbus 3.5+ compatible API."""
        found_registers = {}
        
        if not self.client or not self.client.connected:
            return found_registers
            
        try:
            start_addr = group["start_address"]
            count = group["count"]
            
            _LOGGER.debug(
                "Scanning %s batch 0x%04X-0x%04X (%d registers, %d real): %s",
                register_type, start_addr, start_addr + count - 1, count, 
                group["real_count"], group["registers"][:5]
            )
            
            # pymodbus 3.5+ compatible API calls with timeout
            response = None
            self.scan_stats["total_attempted"] += group["real_count"]
            
            try:
                if register_type == "input":
                    response = await asyncio.wait_for(
                        self.client.read_input_registers(address=start_addr, count=count, slave=self.slave_id),
                        timeout=self.timeout
                    )
                elif register_type == "holding":
                    response = await asyncio.wait_for(
                        self.client.read_holding_registers(address=start_addr, count=count, slave=self.slave_id),
                        timeout=self.timeout
                    )
                elif register_type == "coil":
                    response = await asyncio.wait_for(
                        self.client.read_coils(address=start_addr, count=count, slave=self.slave_id),
                        timeout=self.timeout
                    )
                elif register_type == "discrete":
                    response = await asyncio.wait_for(
                        self.client.read_discrete_inputs(address=start_addr, count=count, slave=self.slave_id),
                        timeout=self.timeout
                    )
            except asyncio.TimeoutError:
                _LOGGER.debug("Timeout reading %s batch 0x%04X-0x%04X", register_type, start_addr, start_addr + count - 1)
                self.scan_stats["failed_batches"] += 1
                return found_registers
            
            if response and not response.isError():
                self.scan_stats["successful_batches"] += 1
                
                # Extract values for each register in group
                for i, reg_name in enumerate(group["registers"]):
                    reg_address = group["addresses"][i]
                    value_index = reg_address - start_addr
                    
                    try:
                        if hasattr(response, 'registers') and response.registers:
                            if value_index < len(response.registers):
                                value = response.registers[value_index]
                                found_registers[reg_name] = reg_address
                                self.scan_stats["total_successful"] += 1
                        elif hasattr(response, 'bits') and response.bits:
                            if value_index < len(response.bits):
                                value = response.bits[value_index]
                                found_registers[reg_name] = reg_address
                                self.scan_stats["total_successful"] += 1
                    except (IndexError, AttributeError) as exc:
                        _LOGGER.debug("Error extracting register %s at index %d: %s", reg_name, value_index, exc)
                        continue
                        
                _LOGGER.debug("Successfully read %d/%d registers from batch", 
                             len(found_registers), group["real_count"])
            else:
                self.scan_stats["failed_batches"] += 1
                error_msg = str(response) if response else "No response"
                _LOGGER.debug("Failed to read %s batch 0x%04X-0x%04X: %s", register_type, start_addr, start_addr + count - 1, error_msg)
                
        except Exception as exc:
            self.scan_stats["failed_batches"] += 1
            self._log_error(f"{register_type}_read_error", f"Unexpected error reading {register_type} {start_addr:04X}-{start_addr + count - 1:04X}: {exc}")
            _LOGGER.warning("Unexpected error reading %s 0x%04X-0x%04X: %s", 
                           register_type, start_addr, start_addr + count - 1, exc)
            
        return found_registers
    
    async def _scan_register_type(self, register_type: str, register_map: Dict[str, int]) -> Dict[str, int]:
        """Scan all registers of specific type."""
        if not register_map:
            _LOGGER.debug("No %s registers to scan", register_type)
            return {}
            
        _LOGGER.info("Scanning %s registers: %d total", register_type, len(register_map))
        
        # Try batch reading first
        groups = self._create_register_groups(register_map, max_gap=5, max_batch=8)  # Smaller batches
        _LOGGER.debug("Created %d register groups for %s scanning", len(groups), register_type)
        
        found_registers = {}
        
        # Scan each group
        for group in groups:
            batch_result = await self._read_register_batch(register_type, group)
            found_registers.update(batch_result)
            
            # Small delay between batches to avoid overwhelming device
            await asyncio.sleep(0.2)
        
        # If batch reading found few registers, try individual reading for important ones
        if len(found_registers) < len(register_map) * 0.3:  # Less than 30% success
            _LOGGER.info("Batch reading had low success rate, trying individual register reads for key registers")
            
            # Key registers to try individually
            key_registers = [
                "firmware_major", "firmware_minor", "firmware_patch",
                "outside_temperature", "supply_temperature", "exhaust_temperature",
                "air_flow_rate", "supply_flowrate", "exhaust_flowrate",
                "mode", "supply_temperature_manual", "comfort_temperature",
                "on_off_panel_mode", "season_mode"
            ]
            
            for reg_name in key_registers:
                if reg_name in register_map and reg_name not in found_registers:
                    single_result = await self._read_single_register(register_type, reg_name, register_map[reg_name])
                    if single_result:
                        found_registers.update(single_result)
                    await asyncio.sleep(0.1)
            
        _LOGGER.info("%s registers scan complete: %d/%d registers found", 
                    register_type.capitalize(), len(found_registers), len(register_map))
        
        return found_registers
    
    async def _read_single_register(self, register_type: str, register_name: str, address: int) -> Dict[str, int]:
        """Read a single register individually."""
        if not self.client or not self.client.connected:
            return {}
        
        try:
            _LOGGER.debug("Reading single %s register %s at 0x%04X", register_type, register_name, address)
            
            response = None
            if register_type == "input":
                response = await asyncio.wait_for(
                    self.client.read_input_registers(address=address, count=1, slave=self.slave_id),
                    timeout=self.timeout
                )
            elif register_type == "holding":
                response = await asyncio.wait_for(
                    self.client.read_holding_registers(address=address, count=1, slave=self.slave_id),
                    timeout=self.timeout
                )
            elif register_type == "coil":
                response = await asyncio.wait_for(
                    self.client.read_coils(address=address, count=1, slave=self.slave_id),
                    timeout=self.timeout
                )
            elif register_type == "discrete":
                response = await asyncio.wait_for(
                    self.client.read_discrete_inputs(address=address, count=1, slave=self.slave_id),
                    timeout=self.timeout
                )
            
            if response and not response.isError():
                _LOGGER.debug("Successfully read %s register %s", register_type, register_name)
                self.scan_stats["total_successful"] += 1
                return {register_name: address}
            else:
                _LOGGER.debug("Failed to read %s register %s: %s", register_type, register_name, response)
                
        except Exception as exc:
            _LOGGER.debug("Error reading single %s register %s: %s", register_type, register_name, exc)
        
        return {}
    
    def _analyze_capabilities(self):
        """Analyze available registers to determine device capabilities."""
        input_regs = set(self.available_registers["input"].keys())
        holding_regs = set(self.available_registers["holding"].keys())
        coil_regs = set(self.available_registers["coil"].keys())
        discrete_regs = set(self.available_registers["discrete"].keys())
        
        _LOGGER.debug("Analyzing capabilities from registers: input=%d, holding=%d, coil=%d, discrete=%d",
                     len(input_regs), len(holding_regs), len(coil_regs), len(discrete_regs))
        
        # Temperature sensors
        temp_sensors = {"outside_temperature", "supply_temperature", "exhaust_temperature", 
                       "fpx_temperature", "duct_supply_temperature", "gwc_temperature", "ambient_temperature"}
        found_temp_sensors = temp_sensors & input_regs
        self.capabilities.has_temperature_sensors = len(found_temp_sensors) > 0
        _LOGGER.debug("Temperature sensors found: %s", found_temp_sensors)
        
        # Flow sensors
        flow_sensors = {"supply_flowrate", "exhaust_flowrate", "air_flow_rate", "supply_percentage", "exhaust_percentage"}
        found_flow_sensors = flow_sensors & input_regs
        self.capabilities.has_flow_sensors = len(found_flow_sensors) > 0
        _LOGGER.debug("Flow sensors found: %s", found_flow_sensors)
        
        # GWC system
        gwc_indicators = {"gwc_temperature", "gwc_mode", "gwc", "gwc_status"}
        found_gwc = gwc_indicators & (input_regs | holding_regs | coil_regs)
        self.capabilities.has_gwc = len(found_gwc) > 0
        _LOGGER.debug("GWC indicators found: %s", found_gwc)
        
        # Bypass system
        bypass_indicators = {"bypass", "bypass_mode", "bypass_status"}
        found_bypass = bypass_indicators & (holding_regs | coil_regs | discrete_regs)
        self.capabilities.has_bypass = len(found_bypass) > 0
        _LOGGER.debug("Bypass indicators found: %s", found_bypass)
        
        # Heating system
        heating_indicators = {"heating_temperature", "heating_cable", "duct_warter_heater_pump", "heating_active"}
        found_heating = heating_indicators & (holding_regs | coil_regs)
        self.capabilities.has_heating = len(found_heating) > 0
        _LOGGER.debug("Heating indicators found: %s", found_heating)
        
        # Scheduling - check for any schedule registers
        schedule_indicators = {key for key in holding_regs if "schedule" in key}
        self.capabilities.has_scheduling = len(schedule_indicators) > 0
        _LOGGER.debug("Schedule indicators found: %d registers", len(schedule_indicators))
        
        # Air quality sensors
        air_quality_sensors = {"co2_concentration", "voc_level", "humidity_level"}
        found_air_quality = air_quality_sensors & input_regs
        self.capabilities.has_air_quality = len(found_air_quality) > 0
        _LOGGER.debug("Air quality sensors found: %s", found_air_quality)
        
        # Pressure sensors
        pressure_sensors = {"pressure_difference", "filter_pressure_drop"}
        found_pressure = pressure_sensors & input_regs
        self.capabilities.has_pressure_sensors = len(found_pressure) > 0
        _LOGGER.debug("Pressure sensors found: %s", found_pressure)
        
        # Filter monitoring
        filter_indicators = {"filter_change", "filter_operating_hours", "filter_pressure_drop", "filter_warning"}
        found_filter = filter_indicators & (input_regs | holding_regs | coil_regs)
        self.capabilities.has_filter_monitoring = len(found_filter) > 0
        _LOGGER.debug("Filter monitoring found: %s", found_filter)
        
        # Special functions detection
        special_functions = []
        if {"okap_mode"} & holding_regs or {"hood"} & coil_regs:
            special_functions.append("OKAP")
        if {"special_mode", "fireplace_mode"} & holding_regs:
            special_functions.append("KOMINEK")
        if {"season_mode"} & holding_regs:
            special_functions.append("SEASONAL")
        if {"boost_mode"} & holding_regs:
            special_functions.append("BOOST")
        if {"party_mode"} & holding_regs:
            special_functions.append("PARTY")
        if {"vacation_mode"} & holding_regs:
            special_functions.append("VACATION")
        if {"eco_mode"} & holding_regs:
            special_functions.append("ECO")
        if {"night_mode"} & holding_regs:
            special_functions.append("NIGHT")
        
        self.capabilities.special_functions = special_functions
        _LOGGER.debug("Special functions found: %s", special_functions)
        
        # Operating modes
        modes = []
        if {"mode"} & holding_regs:
            modes.extend(["AUTO", "MANUAL", "TEMPORARY"])
        if {"on_off_panel_mode"} & holding_regs:
            modes.append("ON_OFF")
        if {"cfgMode2"} & holding_regs:
            modes.append("CONFIG")
            
        self.capabilities.operating_modes = modes
        _LOGGER.debug("Operating modes found: %s", modes)
        
        # Log capabilities summary
        capabilities_summary = []
        if self.capabilities.has_temperature_sensors:
            capabilities_summary.append(f"Temperature({len(found_temp_sensors)})")
        if self.capabilities.has_flow_sensors:
            capabilities_summary.append(f"Flow({len(found_flow_sensors)})")
        if self.capabilities.has_gwc:
            capabilities_summary.append("GWC")
        if self.capabilities.has_bypass:
            capabilities_summary.append("Bypass")
        if self.capabilities.has_heating:
            capabilities_summary.append("Heating")
        if self.capabilities.has_air_quality:
            capabilities_summary.append(f"AirQuality({len(found_air_quality)})")
        if self.capabilities.has_scheduling:
            capabilities_summary.append("Scheduling")
        if len(self.capabilities.special_functions) > 0:
            capabilities_summary.append(f"Special({len(self.capabilities.special_functions)})")
        
        _LOGGER.info("Device capabilities detected: %s", ", ".join(capabilities_summary) if capabilities_summary else "Basic functions only")
        
    async def scan_device(self) -> Optional[Dict[str, Any]]:
        """Perform comprehensive device scan with enhanced diagnostics."""
        scan_start = time.time()
        
        try:
            _LOGGER.info("Starting comprehensive device scan for %s:%s (slave_id=%s)", 
                        self.host, self.port, self.slave_id)
            
            # Connect to device
            if not await self.connect():
                return None
                
            # Test basic connectivity with a simple read
            try:
                test_response = await self.client.read_input_registers(address=0x0000, count=1, slave=self.slave_id)
                if test_response.isError():
                    _LOGGER.warning("Device connectivity test failed: %s", test_response)
                else:
                    _LOGGER.debug("Device connectivity test successful")
            except Exception as exc:
                _LOGGER.warning("Device connectivity test exception: %s", exc)
            
            # Scan all register types
            self.available_registers["input"] = await self._scan_register_type("input", INPUT_REGISTERS)
            self.available_registers["holding"] = await self._scan_register_type("holding", HOLDING_REGISTERS)  
            self.available_registers["coil"] = await self._scan_register_type("coil", COIL_REGISTERS)
            self.available_registers["discrete"] = await self._scan_register_type("discrete", DISCRETE_INPUTS)
            
            # Calculate total found registers
            total_found = sum(len(regs) for regs in self.available_registers.values())
            total_possible = len(INPUT_REGISTERS) + len(HOLDING_REGISTERS) + len(COIL_REGISTERS) + len(DISCRETE_INPUTS)
            
            _LOGGER.info("Initial scan results: %d/%d registers found (%.1f%% success rate)", 
                        total_found, total_possible, (total_found / total_possible * 100) if total_possible > 0 else 0)
            
            # If scan found very few registers, it might be due to device-specific register mapping
            # Try reading some common registers individually to verify connectivity
            if total_found < 20:  # Less than 20 registers found
                _LOGGER.warning("Low register count detected (%d), trying targeted register reads", total_found)
                
                # Try some very common registers that should exist
                test_registers = {
                    "input": ["firmware_major", "firmware_minor", "outside_temperature", "supply_temperature", "exhaust_temperature", "air_flow_rate"],
                    "holding": ["mode", "comfort_temperature", "supply_temperature_manual", "supply_temperature_auto", "air_flow_rate_manual", "on_off_panel_mode"],
                    "coil": ["power_supply_fans", "bypass", "heating_cable"],
                }
                
                additional_found = 0
                for reg_type, reg_names in test_registers.items():
                    reg_map = {"input": INPUT_REGISTERS, "holding": HOLDING_REGISTERS, "coil": COIL_REGISTERS}[reg_type]
                    for reg_name in reg_names:
                        if reg_name in reg_map and reg_name not in self.available_registers[reg_type]:
                            single_result = await self._read_single_register(reg_type, reg_name, reg_map[reg_name])
                            if single_result:
                                self.available_registers[reg_type].update(single_result)
                                additional_found += 1
                            await asyncio.sleep(0.1)
                
                if additional_found > 0:
                    total_found += additional_found
                    _LOGGER.info("Found %d additional registers through targeted reads", additional_found)
            
            # Analyze capabilities
            self._analyze_capabilities()
            
            # Record scan duration
            self.scan_stats["scan_duration"] = time.time() - scan_start
            
            _LOGGER.info(
                "Device scan completed in %.2fs: %d/%d registers found across %d types",
                self.scan_stats["scan_duration"], total_found, total_possible,
                sum(1 for regs in self.available_registers.values() if regs)
            )
            
            # Validate scan results - if still very few registers, recommend force_full_register_list
            if total_found < 10:
                _LOGGER.warning(
                    "Very few registers found (%d). Device may use non-standard register mapping. "
                    "Consider enabling 'Force Full Register List' in integration options.",
                    total_found
                )
                # Still create a result but flag it
                validation_note = "⚠️ Limited device response detected - consider enabling 'Force Full Register List' option"
            else:
                validation_note = "✅ Auto-detected device capabilities - only available functions will be created"
            
            # Validate scan results
            if total_found == 0:
                self._log_error("no_registers_found", "No valid registers found - device may not be ThesslaGreen AirPack or connection issue")
                _LOGGER.error("No valid registers found - device may not be ThesslaGreen AirPack or connection issue")
                return None
            
            # Extract device information
            device_info = await self._extract_device_info()
            
            # Add recommendation for force_full_register_list if needed
            if total_found < 30:  # Less than 30 registers found
                device_info["scan_recommendation"] = (
                    f"Found only {total_found} registers. If you experience missing functionality, "
                    "enable 'Force Full Register List' in integration options to bypass auto-detection."
                )
            
            # Prepare scan result
            scan_result = {
                "available_registers": self.available_registers.copy(),
                "capabilities": self.capabilities.to_dict(),
                "device_info": device_info,
                "scan_statistics": self.scan_stats.copy(),
                "diagnostics": {
                    "error_log": self.error_log.copy(),
                    "success_rate": self.scan_stats["total_successful"] / max(1, self.scan_stats["total_attempted"]) * 100,
                    "batch_success_rate": self.scan_stats["successful_batches"] / max(1, self.scan_stats["successful_batches"] + self.scan_stats["failed_batches"]) * 100,
                    "register_count": total_found,
                    "register_success_rate": (total_found / total_possible * 100) if total_possible > 0 else 0,
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
                    major_response = await self.client.read_input_registers(address=INPUT_REGISTERS["firmware_major"], count=1, slave=self.slave_id)
                    minor_response = await self.client.read_input_registers(address=INPUT_REGISTERS["firmware_minor"], count=1, slave=self.slave_id)
                    
                    if not major_response.isError() and not minor_response.isError():
                        major = major_response.registers[0]
                        minor = minor_response.registers[0]
                        
                        # Try to read patch version if available
                        patch = 0
                        if "firmware_patch" in self.available_registers["input"]:
                            patch_response = await self.client.read_input_registers(address=INPUT_REGISTERS["firmware_patch"], count=1, slave=self.slave_id)
                            if not patch_response.isError():
                                patch = patch_response.registers[0]
                                
                        device_info["firmware"] = f"{major}.{minor}.{patch}"
                        device_info["device_name"] = f"ThesslaGreen AirPack (v{major}.{minor})"
                        
                except Exception as exc:
                    _LOGGER.debug("Could not read firmware version: %s", exc)
                    
            # Try to read serial number
            serial_parts = []
            for i in range(1, 7):
                reg_name = f"serial_number_{i}"
                if reg_name in self.available_registers["input"]:
                    try:
                        response = await self.client.read_input_registers(address=INPUT_REGISTERS[reg_name], count=1, slave=self.slave_id)
                        if not response.isError():
                            serial_parts.append(f"{response.registers[0]:04X}")
                    except Exception as exc:
                        _LOGGER.debug("Could not read serial number part %d: %s", i, exc)
                        
            if serial_parts:
                device_info["serial_number"] = "".join(serial_parts)
                
        except Exception as exc:
            _LOGGER.debug("Error extracting device info: %s", exc)
            
        return device_info