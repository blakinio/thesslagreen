"""Device scanner for the ThesslaGreen Modbus integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Any, Tuple

import pymodbus.client.tcp as ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

from .const import (
    INPUT_REGISTERS,
    HOLDING_REGISTERS,
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
)

_LOGGER = logging.getLogger(__name__)

@dataclass
class DeviceCapabilities:
    """Device capabilities detected by scanning."""
    basic_control: bool = False
    temperature_sensors: Set[str] = field(default_factory=set)
    flow_sensors: Set[str] = field(default_factory=set)
    special_functions: Set[str] = field(default_factory=set)
    expansion_module: bool = False
    constant_flow: bool = False
    gwc_system: bool = False
    bypass_system: bool = False
    heating_system: bool = False
    cooling_system: bool = False
    air_quality: bool = False
    weekly_schedule: bool = False
    sensor_outside_temperature: bool = False
    sensor_supply_temperature: bool = False
    sensor_exhaust_temperature: bool = False
    sensor_fpx_temperature: bool = False
    sensor_duct_supply_temperature: bool = False
    sensor_gwc_temperature: bool = False
    sensor_ambient_temperature: bool = False
    sensor_heating_temperature: bool = False
    temperature_sensors_count: int = 0


class ThesslaGreenDeviceScanner:
    """Scan a ThesslaGreen device to detect available features."""
    
    def __init__(self, host: str, port: int, slave_id: int, timeout: int = 10):
        """Initialize device scanner."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.client = None
        self.available_registers: Dict[str, Set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }
        self._register_groups: Dict[str, List[Tuple[int, int]]] = {}
        self._precompute_register_groups()
    
    def _precompute_register_groups(self) -> None:
        """Pre-compute register groups for efficient batch reading."""
        # Group Input Registers
        input_addrs = sorted(INPUT_REGISTERS.values())
        self._register_groups["input"] = self._group_registers_for_batch_read(input_addrs)
        
        # Group Holding Registers  
        holding_addrs = sorted(HOLDING_REGISTERS.values())
        self._register_groups["holding"] = self._group_registers_for_batch_read(holding_addrs)
        
        # Group Coil Registers
        coil_addrs = sorted(COIL_REGISTERS.values())
        self._register_groups["coil"] = self._group_registers_for_batch_read(coil_addrs)
        
        # Group Discrete Input Registers
        discrete_addrs = sorted(DISCRETE_INPUT_REGISTERS.values())
        self._register_groups["discrete"] = self._group_registers_for_batch_read(discrete_addrs)
    
    def _group_registers_for_batch_read(self, addresses: List[int], max_gap: int = 10, max_batch: int = 16) -> List[Tuple[int, int]]:
        """Group consecutive registers for efficient batch reading."""
        if not addresses:
            return []
        
        groups = []
        current_start = addresses[0]
        current_end = addresses[0]
        
        for addr in addresses[1:]:
            # If gap is too large or batch too big, start new group
            if (addr - current_end > max_gap) or (current_end - current_start + 1 >= max_batch):
                groups.append((current_start, current_end - current_start + 1))
                current_start = addr
                current_end = addr
            else:
                current_end = addr
        
        # Add last group
        groups.append((current_start, current_end - current_start + 1))
        return groups
    
    async def connect(self) -> bool:
        """Connect to Modbus device."""
        try:
            self.client = ModbusTcpClient.AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            connected = await self.client.connect()
            if connected:
                _LOGGER.info("Connected to ThesslaGreen device at %s:%s", self.host, self.port)
                return True
            else:
                _LOGGER.error("Failed to connect to ThesslaGreen device at %s:%s", self.host, self.port)
                return False
        except Exception as e:
            _LOGGER.error("Connection error: %s", e)
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Modbus device."""
        if self.client:
            self.client.close()
            _LOGGER.debug("Disconnected from ThesslaGreen device")
    
    async def scan_device(self) -> Dict[str, Any]:
        """Comprehensive device scanning with enhanced capabilities detection."""
        _LOGGER.info("Starting comprehensive device scan for %s:%s", self.host, self.port)
        
        if not await self.connect():
            raise ConnectionException(f"Could not connect to device at {self.host}:{self.port}")
        
        try:
            # Scan all register types
            await self._scan_input_registers()
            await self._scan_holding_registers()
            await self._scan_coil_registers()
            await self._scan_discrete_inputs()
            
            # Get device information
            device_info = await self._get_device_info()
            
            # Analyze capabilities
            capabilities = self._analyze_capabilities_enhanced()
            
            scan_result = {
                "device_info": device_info,
                "capabilities": capabilities,
                "available_registers": dict(self.available_registers),
                "register_count": sum(len(regs) for regs in self.available_registers.values()),
                "scan_success": True,
            }
            
            _LOGGER.info(
                "Device scan completed: %d registers found, %d capabilities detected",
                scan_result["register_count"],
                len([k for k, v in capabilities.__dict__.items() if v is True])
            )
            
            return scan_result
            
        except Exception as e:
            _LOGGER.error("Device scan failed: %s", e)
            raise
        finally:
            await self.disconnect()
    
    async def _scan_input_registers(self) -> None:
        """Scan input registers efficiently using batch reading."""
        _LOGGER.debug("Scanning input registers...")
        
        for start_addr, count in self._register_groups["input"]:
            try:
                response = await self.client.read_input_registers(start_addr, count, slave=self.slave_id)
                if not response.isError():
                    # Check which specific registers are available
                    for i, value in enumerate(response.registers):
                        addr = start_addr + i
                        register_name = self._find_register_name(INPUT_REGISTERS, addr)
                        if register_name and self._is_valid_value(value, "input", register_name):
                            self.available_registers["input_registers"].add(register_name)
                            _LOGGER.debug("Found input register: %s (0x%04X) = %s", register_name, addr, value)
                else:
                    _LOGGER.debug("Failed to read input registers at 0x%04X: %s", start_addr, response)
            except Exception as e:
                _LOGGER.debug("Error reading input registers at 0x%04X: %s", start_addr, e)
    
    async def _scan_holding_registers(self) -> None:
        """Scan holding registers efficiently."""
        _LOGGER.debug("Scanning holding registers...")
        
        for start_addr, count in self._register_groups["holding"]:
            try:
                response = await self.client.read_holding_registers(start_addr, count, slave=self.slave_id)
                if not response.isError():
                    for i, value in enumerate(response.registers):
                        addr = start_addr + i
                        register_name = self._find_register_name(HOLDING_REGISTERS, addr)
                        if register_name and self._is_valid_value(value, "holding", register_name):
                            self.available_registers["holding_registers"].add(register_name)
                            _LOGGER.debug("Found holding register: %s (0x%04X) = %s", register_name, addr, value)
                else:
                    _LOGGER.debug("Failed to read holding registers at 0x%04X: %s", start_addr, response)
            except Exception as e:
                _LOGGER.debug("Error reading holding registers at 0x%04X: %s", start_addr, e)
    
    async def _scan_coil_registers(self) -> None:
        """Scan coil registers."""
        _LOGGER.debug("Scanning coil registers...")
        
        for start_addr, count in self._register_groups["coil"]:
            try:
                response = await self.client.read_coils(start_addr, count, slave=self.slave_id)
                if not response.isError():
                    for i, value in enumerate(response.bits):
                        addr = start_addr + i
                        register_name = self._find_register_name(COIL_REGISTERS, addr)
                        if register_name:
                            self.available_registers["coil_registers"].add(register_name)
                            _LOGGER.debug("Found coil register: %s (0x%04X) = %s", register_name, addr, value)
                else:
                    _LOGGER.debug("Failed to read coil registers at 0x%04X: %s", start_addr, response)
            except Exception as e:
                _LOGGER.debug("Error reading coil registers at 0x%04X: %s", start_addr, e)
    
    async def _scan_discrete_inputs(self) -> None:
        """Scan discrete input registers."""
        _LOGGER.debug("Scanning discrete input registers...")
        
        for start_addr, count in self._register_groups["discrete"]:
            try:
                response = await self.client.read_discrete_inputs(start_addr, count, slave=self.slave_id)
                if not response.isError():
                    for i, value in enumerate(response.bits):
                        addr = start_addr + i
                        register_name = self._find_register_name(DISCRETE_INPUT_REGISTERS, addr)
                        if register_name:
                            self.available_registers["discrete_inputs"].add(register_name)
                            _LOGGER.debug("Found discrete input: %s (0x%04X) = %s", register_name, addr, value)
                else:
                    _LOGGER.debug("Failed to read discrete inputs at 0x%04X: %s", start_addr, response)
            except Exception as e:
                _LOGGER.debug("Error reading discrete inputs at 0x%04X: %s", start_addr, e)
    
    def _find_register_name(self, register_dict: Dict[str, int], address: int) -> Optional[str]:
        """Find register name by address."""
        for name, addr in register_dict.items():
            if addr == address:
                return name
        return None
    
    def _is_valid_value(self, value: int, register_type: str, register_name: str) -> bool:
        """Check if register value indicates the sensor/function is available."""
        # Special handling for temperature sensors (0x8000 = no sensor)
        if "temperature" in register_name:
            return value != 0x8000
        
        # Special handling for flow sensors (0x8000 = no sensor)
        if "flow" in register_name:
            return value != 0x8000
        
        # Most other registers are valid if they're not 0xFFFF (typical error value)
        return value != 0xFFFF
    
    async def _get_device_info(self) -> Dict[str, Any]:
        """Get basic device information."""
        device_info = {
            "device_name": "Unknown AirPack",
            "firmware": "Unknown",
            "serial_number": "Unknown",
            "model": "AirPack Home Serie 4",
        }
        
        try:
            # Try to read firmware version (addresses from manual)
            firmware_response = await self.client.read_input_registers(0x0000, 2, slave=self.slave_id)
            if not firmware_response.isError():
                major = firmware_response.registers[0]
                minor = firmware_response.registers[1]
                device_info["firmware"] = f"{major}.{minor}.0"
            
            # Try to read device name (addresses from manual)
            name_response = await self.client.read_holding_registers(0x1FD0, 8, slave=self.slave_id)
            if not name_response.isError():
                # Convert register values to ASCII string
                name_chars = []
                for reg in name_response.registers:
                    if reg == 0:
                        break
                    name_chars.append(chr((reg >> 8) & 0xFF))
                    name_chars.append(chr(reg & 0xFF))
                device_name = ''.join(name_chars).strip('\x00')
                if device_name:
                    device_info["device_name"] = device_name
                    
        except Exception as e:
            _LOGGER.debug("Could not read device info: %s", e)
        
        return device_info
    
    def _analyze_capabilities_enhanced(self) -> DeviceCapabilities:
        """Enhanced capability analysis with complete function detection."""
        capabilities = DeviceCapabilities()
        
        # Basic control capabilities
        if ("on_off_panel_mode" in self.available_registers["holding_registers"] and
            "mode" in self.available_registers["holding_registers"]):
            capabilities.basic_control = True
        
        # Temperature sensors
        temp_sensors = [
            "outside_temperature", "supply_temperature", "exhaust_temperature",
            "fpx_temperature", "duct_supply_temperature", "gwc_temperature", 
            "ambient_temperature", "heating_temperature"
        ]
        
        for sensor in temp_sensors:
            if sensor in self.available_registers["input_registers"]:
                capabilities.temperature_sensors.add(sensor)
                setattr(capabilities, f"sensor_{sensor}", True)
                capabilities.temperature_sensors_count += 1
        
        # Flow sensors
        flow_sensors = ["supply_flowrate", "exhaust_flowrate"]
        for sensor in flow_sensors:
            if sensor in self.available_registers["input_registers"]:
                capabilities.flow_sensors.add(sensor)
        
        # Special functions detection
        special_functions = [
            "gwc_mode", "bypass_mode", "okap_mode", "kominek_mode", 
            "wietrzenie_mode", "pusty_dom_mode"
        ]
        for func in special_functions:
            if func in self.available_registers["holding_registers"]:
                capabilities.special_functions.add(func)
        
        # System capabilities
        if "constant_flow_active" in self.available_registers["input_registers"]:
            capabilities.constant_flow = True
        
        if ("gwc" in self.available_registers["coil_registers"] or 
            "gwc_mode" in self.available_registers["holding_registers"]):
            capabilities.gwc_system = True
        
        if ("bypass" in self.available_registers["coil_registers"] or 
            "bypass_mode" in self.available_registers["holding_registers"]):
            capabilities.bypass_system = True
        
        if "expansion" in self.available_registers["discrete_inputs"]:
            capabilities.expansion_module = True
        
        if ("heating_cable" in self.available_registers["coil_registers"] or
            "heating_temperature" in self.available_registers["input_registers"]):
            capabilities.heating_system = True
        
        if "cooler_temperature" in self.available_registers["input_registers"]:
            capabilities.cooling_system = True
        
        if ("co2_level" in self.available_registers["input_registers"] or
            "humidity_level" in self.available_registers["input_registers"]):
            capabilities.air_quality = True
        
        if "weekly_schedule_mode" in self.available_registers["holding_registers"]:
            capabilities.weekly_schedule = True
        
        _LOGGER.info("Detected capabilities: %s", capabilities)
        return capabilities


async def scan_thessla_green_device(host: str, port: int, slave_id: int, timeout: int = 10) -> Dict[str, Any]:
    """Convenience function to scan ThesslaGreen device."""
    scanner = ThesslaGreenDeviceScanner(host, port, slave_id, timeout)
    return await scanner.scan_device()