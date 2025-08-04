"""Enhanced device capability scanner for ThesslaGreen Modbus - OPTIMIZED VERSION with FIXED pymodbus API."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Set

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    INVALID_TEMPERATURE,
    INVALID_FLOW,
)

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenDeviceScanner:
    """Enhanced scanner to detect available capabilities of ThesslaGreen device."""

    def __init__(self, host: str, port: int, slave_id: int) -> None:
        """Initialize the scanner."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.available_registers: Dict[str, Set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }
        self.device_info: Dict[str, Any] = {}
        self._scan_stats = {
            "total_attempts": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "scan_duration": 0.0,
        }

    async def scan_device(self) -> Dict[str, Any]:
        """Scan device and return available capabilities - OPTIMIZED."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._scan_device_sync
        )

    def _scan_device_sync(self) -> Dict[str, Any]:
        """Optimized synchronous device scanning with FIXED pymodbus API."""
        start_time = time.time()
        
        _LOGGER.info("Starting OPTIMIZED device capability scan for %s:%s (slave_id=%s)", 
                    self.host, self.port, self.slave_id)
        
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=10)
        
        try:
            if not client.connect():
                raise Exception("Failed to connect to device")
            
            # Phase 1: Read critical device identification
            self._scan_device_info(client)
            
            # Phase 2: Smart register scanning with optimized batching
            self.available_registers["input_registers"] = self._scan_input_registers_optimized(client)
            self.available_registers["holding_registers"] = self._scan_holding_registers_optimized(client)
            self.available_registers["coil_registers"] = self._scan_coil_registers_batch(client)
            self.available_registers["discrete_inputs"] = self._scan_discrete_inputs_batch(client)
            
            # Phase 3: Analyze capabilities based on found registers
            capabilities = self._analyze_capabilities_enhanced()
            
            # Phase 4: Model-specific validation
            self._validate_model_capabilities(capabilities)
            
            # Performance statistics
            self._scan_stats["scan_duration"] = time.time() - start_time
            success_rate = (self._scan_stats["successful_reads"] / 
                          max(self._scan_stats["total_attempts"], 1) * 100)
            
            _LOGGER.info(
                "OPTIMIZED scan complete: %d input, %d holding, %d coils, %d discrete (%.1f%% success, %.2fs)",
                len(self.available_registers["input_registers"]),
                len(self.available_registers["holding_registers"]),
                len(self.available_registers["coil_registers"]),
                len(self.available_registers["discrete_inputs"]),
                success_rate,
                self._scan_stats["scan_duration"]
            )
            
            return {
                "available_registers": self.available_registers,
                "device_info": self.device_info,
                "capabilities": capabilities,
                "scan_stats": self._scan_stats,
            }
            
        except Exception as exc:
            _LOGGER.error("Optimized device scan failed: %s", exc)
            raise
        finally:
            client.close()

    def _scan_device_info(self, client: ModbusTcpClient) -> None:
        """Enhanced device information scanning with error handling - FIXED API."""
        # Initialize with defaults
        self.device_info = {
            "device_name": "ThesslaGreen AirPack",
            "firmware": "Unknown",
            "serial_number": "Unknown",
            "processor": "ATmega2561",
            "firmware_major": 0,
            "firmware_minor": 0,
            "firmware_patch": 0,
        }

        try:
            # Priority 1: Firmware version (always present) - FIXED API
            result = client.read_input_registers(address=0x0000, count=5, slave=self.slave_id)
            self._scan_stats["total_attempts"] += 1
            
            if not result.isError():
                self._scan_stats["successful_reads"] += 1
                major = result.registers[0]
                minor = result.registers[1]
                patch = result.registers[4] if len(result.registers) > 4 else 0
                
                self.device_info["firmware"] = f"{major}.{minor}.{patch}"
                self.device_info["firmware_major"] = major
                self.device_info["firmware_minor"] = minor
                self.device_info["firmware_patch"] = patch
                
                # Determine processor type and capabilities based on firmware
                if major == 3:
                    self.device_info["processor"] = "ATmega128"
                    self.device_info["max_capabilities"] = "basic"
                elif major == 4:
                    self.device_info["processor"] = "ATmega2561"
                    self.device_info["max_capabilities"] = "advanced"
                else:
                    self.device_info["processor"] = "Unknown"
                    self.device_info["max_capabilities"] = "unknown"
                
                _LOGGER.debug("Detected firmware: %s, processor: %s", 
                            self.device_info["firmware"], self.device_info["processor"])
            else:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.warning("Failed to read firmware version")
            
        except Exception as exc:
            self._scan_stats["failed_reads"] += 1
            _LOGGER.warning("Exception reading device info: %s", exc)

        # Priority 2: Serial number - FIXED API
        try:
            result = client.read_input_registers(address=0x0018, count=6, slave=self.slave_id)
            self._scan_stats["total_attempts"] += 1
            
            if not result.isError():
                self._scan_stats["successful_reads"] += 1
                serial_parts = [f"{reg:04x}" for reg in result.registers]
                self.device_info["serial_number"] = f"S/N: {serial_parts[0]}{serial_parts[1]} {serial_parts[2]}{serial_parts[3]} {serial_parts[4]}{serial_parts[5]}"
            else:
                self._scan_stats["failed_reads"] += 1
                
        except Exception as exc:
            self._scan_stats["failed_reads"] += 1
            _LOGGER.debug("Could not read serial number: %s", exc)

        # Priority 3: Device name - FIXED API
        try:
            result = client.read_holding_registers(address=0x1FD0, count=8, slave=self.slave_id)
            self._scan_stats["total_attempts"] += 1
            
            if not result.isError():
                self._scan_stats["successful_reads"] += 1
                name_chars = []
                for reg in result.registers:
                    if reg != 0:
                        char1 = (reg >> 8) & 0xFF
                        char2 = reg & 0xFF
                        if char1 != 0 and 32 <= char1 <= 126:
                            name_chars.append(chr(char1))
                        if char2 != 0 and 32 <= char2 <= 126:
                            name_chars.append(chr(char2))
                
                if name_chars:
                    device_name = ''.join(name_chars).strip()
                    if device_name:
                        self.device_info["device_name"] = device_name
                    else:
                        self.device_info["device_name"] = "ThesslaGreen AirPack"
                else:
                    self.device_info["device_name"] = "ThesslaGreen AirPack"
            else:
                self._scan_stats["failed_reads"] += 1
                self.device_info["device_name"] = "ThesslaGreen AirPack"
                
        except Exception as exc:
            self._scan_stats["failed_reads"] += 1
            self.device_info["device_name"] = "ThesslaGreen AirPack"
            _LOGGER.debug("Could not read device name: %s", exc)

    def _scan_input_registers_optimized(self, client: ModbusTcpClient) -> Set[str]:
        """Optimized input register scanning with intelligent batching - FIXED API."""
        available = set()
        
        # Define register groups to scan efficiently
        scan_groups = [
            # Critical sensors
            ("critical", {
                "outside_temperature": 0x0000, "supply_temperature": 0x0001,
                "exhaust_temperature": 0x0002, "fpx_temperature": 0x0003,
                "firmware_major": 0x0005, "firmware_minor": 0x0006, "firmware_patch": 0x0007,
            }),
            # Additional temperatures
            ("temperatures", {
                "duct_supply_temperature": 0x0010, "gwc_temperature": 0x0011,
                "ambient_temperature": 0x0012,
            }),
            # Air flow data
            ("airflow", {
                "supply_flowrate": 0x0100, "exhaust_flowrate": 0x0101,
                "supply_percentage": 0x0102, "exhaust_percentage": 0x0103,
                "supply_air_flow": 0x0104, "exhaust_air_flow": 0x0105,
            }),
            # Constant Flow system
            ("constant_flow", {
                "constant_flow_active": 0x010F, "supply_dac_voltage": 0x012A,
                "exhaust_dac_voltage": 0x012B, "cf_supply_air_flow": 0x012C,
                "cf_exhaust_air_flow": 0x012D,
            }),
            # Extended sensors
            ("extended", {
                "expansion_temperature_1": 0x0500, "expansion_temperature_2": 0x0501,
                "expansion_humidity": 0x0502, "expansion_co2": 0x0503,
            }),
        ]
        
        for group_name, registers in scan_groups:
            _LOGGER.debug("Scanning input register group: %s", group_name)
            group_available = self._scan_register_group_batch(client, registers, "input")
            available.update(group_available)
        
        return available

    def _scan_holding_registers_optimized(self, client: ModbusTcpClient) -> Set[str]:
        """Optimized holding register scanning with intelligent batching - FIXED API."""
        available = set()
        
        # Define register groups to scan efficiently  
        scan_groups = [
            # Critical control registers
            ("critical_control", {
                "mode": 0x1070, "on_off_panel_mode": 0x1071,
                "air_flow_rate_manual": 0x1072, "season_mode": 0x1120,
            }),
            # Manual control
            ("manual_control", {
                "supply_intensity_manual": 0x1075, "exhaust_intensity_manual": 0x1076,
                "target_temperature": 0x10D0,
            }),
            # Special functions
            ("special_functions", {
                "special_mode": 0x1082, "special_function_timer": 0x1083,
                "okap_timer": 0x1084, "fireplace_timer": 0x1085,
            }),
            # GWC system
            ("gwc_system", {
                "gwc_mode": 0x10A0, "gwc_season_mode": 0x10A1,
                "gwc_temperature_threshold": 0x10A2,
            }),
            # Bypass system
            ("bypass_system", {
                "bypass_mode": 0x10E0, "bypass_temperature_threshold": 0x10E1,
            }),
            # System flags
            ("system_flags", {
                "alarm_flag": 0x2000, "error_flag": 0x2001,
            }),
        ]
        
        for group_name, registers in scan_groups:
            _LOGGER.debug("Scanning holding register group: %s", group_name)
            group_available = self._scan_register_group_batch(client, registers, "holding")
            available.update(group_available)
            
            # Special handling: if critical control registers are missing, this might not be a compatible device
            if group_name == "critical_control" and len(group_available) < 3:
                _LOGGER.warning("Critical control registers missing - device may not be compatible")
        
        return available

    def _scan_register_group_batch(self, client: ModbusTcpClient, registers: Dict[str, int], 
                                  reg_type: str) -> Set[str]:
        """Scan a group of registers efficiently using batch reads where possible - FIXED API."""
        available = set()
        
        # Group registers by proximity for batch reading
        grouped = self._group_registers_for_batch_read(registers)
        
        for start_addr, reg_group in grouped.items():
            try:
                # Calculate range
                addresses = list(reg_group.values())
                min_addr = min(addresses)
                max_addr = max(addresses)
                count = max_addr - min_addr + 1
                
                if count <= 16:  # Batch read for small ranges
                    # FIXED API calls
                    if reg_type == "input":
                        result = client.read_input_registers(address=min_addr, count=count, slave=self.slave_id)
                    elif reg_type == "holding":
                        result = client.read_holding_registers(address=min_addr, count=count, slave=self.slave_id)
                    else:
                        continue
                        
                    self._scan_stats["total_attempts"] += 1
                    
                    if not result.isError():
                        self._scan_stats["successful_reads"] += 1
                        for name, address in reg_group.items():
                            idx = address - min_addr
                            if idx < len(result.registers):
                                value = result.registers[idx]
                                if self._is_valid_register_value(name, value):
                                    available.add(name)
                                    _LOGGER.debug("Found %s register %s (0x%04X) = %s", 
                                                reg_type, name, address, value)
                    else:
                        self._scan_stats["failed_reads"] += 1
                        # Fallback to individual reads
                        for name, address in reg_group.items():
                            if self._scan_single_register(client, name, address, reg_type):
                                available.add(name)
                else:
                    # Individual reads for large ranges
                    for name, address in reg_group.items():
                        if self._scan_single_register(client, name, address, reg_type):
                            available.add(name)
                            
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug("Batch read failed for %s group at 0x%04X: %s", reg_type, start_addr, exc)
                
                # Fallback to individual reads
                for name, address in reg_group.items():
                    if self._scan_single_register(client, name, address, reg_type):
                        available.add(name)
        
        return available

    def _scan_single_register(self, client: ModbusTcpClient, name: str, address: int, reg_type: str) -> bool:
        """Scan a single register with validation - FIXED API."""
        try:
            # FIXED API calls
            if reg_type == "input":
                result = client.read_input_registers(address=address, count=1, slave=self.slave_id)
            elif reg_type == "holding":
                result = client.read_holding_registers(address=address, count=1, slave=self.slave_id)
            else:
                return False
            
            self._scan_stats["total_attempts"] += 1
            
            if not result.isError():
                value = result.registers[0]
                if self._is_valid_register_value(name, value):
                    self._scan_stats["successful_reads"] += 1
                    return True
                    
            self._scan_stats["failed_reads"] += 1
            return False
            
        except Exception:
            self._scan_stats["failed_reads"] += 1
            return False

    def _scan_coil_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Efficiently scan all coil registers in minimal number of reads - FIXED API."""
        available = set()
        
        if not COIL_REGISTERS:
            return available
        
        min_addr = min(COIL_REGISTERS.values())
        max_addr = max(COIL_REGISTERS.values())
        count = max_addr - min_addr + 1
        
        try:
            # FIXED API call
            result = client.read_coils(address=min_addr, count=count, slave=self.slave_id)
            self._scan_stats["total_attempts"] += 1
            
            if not result.isError():
                self._scan_stats["successful_reads"] += 1
                for name, address in COIL_REGISTERS.items():
                    idx = address - min_addr
                    if idx < len(result.bits):
                        available.add(name)
                        _LOGGER.debug("Found coil %s (0x%04X) = %s", name, address, result.bits[idx])
            else:
                self._scan_stats["failed_reads"] += 1
                
        except Exception as exc:
            self._scan_stats["failed_reads"] += 1
            _LOGGER.debug("Failed to read coils: %s", exc)
        
        return available

    def _scan_discrete_inputs_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Efficiently scan all discrete input registers - FIXED API."""
        available = set()
        
        if not DISCRETE_INPUT_REGISTERS:
            return available
        
        min_addr = min(DISCRETE_INPUT_REGISTERS.values())
        max_addr = max(DISCRETE_INPUT_REGISTERS.values())
        count = max_addr - min_addr + 1
        
        try:
            # FIXED API call
            result = client.read_discrete_inputs(address=min_addr, count=count, slave=self.slave_id)
            self._scan_stats["total_attempts"] += 1
            
            if not result.isError():
                self._scan_stats["successful_reads"] += 1
                for name, address in DISCRETE_INPUT_REGISTERS.items():
                    idx = address - min_addr
                    if idx < len(result.bits):
                        available.add(name)
                        _LOGGER.debug("Found discrete input %s (0x%04X) = %s", 
                                    name, address, result.bits[idx])
            else:
                self._scan_stats["failed_reads"] += 1
                
        except Exception as exc:
            self._scan_stats["failed_reads"] += 1
            _LOGGER.debug("Failed to read discrete inputs: %s", exc)
        
        return available

    def _is_valid_register_value(self, register_name: str, value: int) -> bool:
        """Enhanced register value validation with model-specific logic."""
        # Universal invalid values
        if value == 0xFFFF or value == 65535:
            return False
        
        # Temperature sensors return 0x8000 (32768) when not connected
        if "temperature" in register_name and value == INVALID_TEMPERATURE:
            return False
        
        # Air flow sensors return 65535 when CF is not active
        if ("air_flow" in register_name or "flowrate" in register_name) and value == INVALID_FLOW:
            return False
        
        # Mode registers should have valid ranges
        if register_name == "mode" and value not in [0, 1, 2]:
            return False
        
        if register_name == "season_mode" and value not in [0, 1]:
            return False
        
        if register_name == "special_mode" and not (0 <= value <= 11):
            return False
        
        # DAC values should not exceed 10V equivalent (4095)
        if "dac_" in register_name and value > 4095:
            return False
        
        return True

    def _group_registers_for_batch_read(self, registers: Dict[str, int], 
                                       max_gap: int = 20) -> Dict[int, Dict[str, int]]:
        """Group registers for efficient batch reading."""
        if not registers:
            return {}
        
        # Sort registers by address
        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        
        groups = {}
        current_group_start = sorted_regs[0][1]
        current_group = {}
        
        for name, addr in sorted_regs:
            if addr - current_group_start <= max_gap and len(current_group) < 16:
                current_group[name] = addr
            else:
                # Start new group
                if current_group:
                    groups[current_group_start] = current_group
                current_group_start = addr
                current_group = {name: addr}
        
        # Add the last group
        if current_group:
            groups[current_group_start] = current_group
        
        return groups

    def _analyze_capabilities_enhanced(self) -> Dict[str, Any]:
        """Analyze device capabilities based on available registers."""
        capabilities = {
            "basic_control": False,
            "constant_flow": False,
            "gwc_system": False,
            "bypass_system": False,
            "comfort_mode": False,
            "expansion_module": False,
            "special_functions": False,
            "temperature_sensors_count": 0,
            "sensor_outside_temperature": False,
            "sensor_supply_temperature": False,
            "sensor_exhaust_temperature": False,
            "sensor_fpx_temperature": False,
            "sensor_gwc_temperature": False,
            "sensor_ambient_temperature": False,
            "air_flow_control": False,
            "model_type": "Unknown"
        }
        
        input_regs = self.available_registers.get("input_registers", set())
        holding_regs = self.available_registers.get("holding_registers", set())
        coil_regs = self.available_registers.get("coil_registers", set())
        discrete_regs = self.available_registers.get("discrete_inputs", set())
        
        # Check for basic control capabilities
        if "mode" in holding_regs or "on_off_panel_mode" in holding_regs:
            capabilities["basic_control"] = True
            
        # Check for constant flow
        if "constant_flow_active" in input_regs:
            capabilities["constant_flow"] = True
            
        # Check air flow control
        if any(reg in input_regs for reg in ["supply_flowrate", "exhaust_flowrate", "supply_percentage"]):
            capabilities["air_flow_control"] = True
            
        # Check for GWC system
        if "gwc_mode" in holding_regs or "gwc_temperature" in input_regs or "gwc" in coil_regs:
            capabilities["gwc_system"] = True
            
        # Check for bypass system
        if "bypass_mode" in holding_regs or "bypass" in coil_regs:
            capabilities["bypass_system"] = True
            
        # Check for comfort mode
        if "target_temperature" in holding_regs:
            capabilities["comfort_mode"] = True
            
        # Check for special functions
        if "special_mode" in holding_regs:
            capabilities["special_functions"] = True
            
        # Check for expansion module
        if "expansion" in discrete_regs:
            capabilities["expansion_module"] = True
            
        # Count temperature sensors and check individual sensors
        temp_sensors = [
            "outside_temperature", "supply_temperature", "exhaust_temperature",
            "fpx_temperature", "gwc_temperature", "ambient_temperature"
        ]
        
        for sensor in temp_sensors:
            if sensor in input_regs:
                capabilities["temperature_sensors_count"] += 1
                capabilities[f"sensor_{sensor}"] = True
                
        return capabilities

    def _validate_model_capabilities(self, capabilities: Dict[str, Any]) -> None:
        """Model-specific validation and capability enhancement."""
        # Determine model type based on capabilities
        if capabilities["gwc_system"] and capabilities["constant_flow"]:
            capabilities["model_type"] = "AirPack Home Energy+ with CF and GWC"
        elif capabilities["constant_flow"]:
            capabilities["model_type"] = "AirPack Home Energy+ with CF"
        elif capabilities["gwc_system"]:
            capabilities["model_type"] = "AirPack Home with GWC"
        elif capabilities["basic_control"]:
            capabilities["model_type"] = "AirPack Home"
        else:
            capabilities["model_type"] = "AirPack Unknown"
            
        # Update device info with model
        self.device_info["model_type"] = capabilities["model_type"]
        
        # Model-specific capability validation
        firmware_major = self.device_info.get("firmware_major", 0)
        
        if firmware_major >= 4:
            # Advanced features available in firmware 4.x+
            if not capabilities["constant_flow"]:
                _LOGGER.debug("Firmware 4.x detected but Constant Flow not found - may be disabled")
        elif firmware_major == 3:
            # Basic features only in firmware 3.x
            if capabilities["gwc_system"]:
                _LOGGER.warning("GWC system detected with firmware 3.x - unusual configuration")
                
        _LOGGER.info("Detected device model: %s", capabilities["model_type"])