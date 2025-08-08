"""Enhanced device scanner for ThesslaGreen Modbus Integration."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ModbusException
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


class EnhancedDeviceScanner:
    """Enhanced device scanner with intelligent register detection."""
    
    def __init__(self, host: str, port: int, slave_id: int, timeout: int = DEFAULT_TIMEOUT, retry_count: int = DEFAULT_RETRY):
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry_count = retry_count
        self.client: Optional[AsyncModbusTcpClient] = None
        
        # Scanning configuration
        self.max_batch_size = 16  # Max registers per batch read
        self.max_gap_size = 10    # Max gap between registers to include in batch
        
        # Results storage
        self.available_registers: Dict[str, List[str]] = {
            "input": [],
            "holding": [],
            "coil": [],
            "discrete": []
        }
        self.scan_stats = {
            "total_attempted": 0,
            "total_successful": 0,
            "register_types_found": 0,
            "scan_duration": 0,
        }
        
    async def connect(self) -> bool:
        """Establish Modbus connection with retry logic."""
        for attempt in range(1, self.retry_count + 1):
            try:
                self.client = AsyncModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout
                )
                
                if await self.client.connect():
                    _LOGGER.debug("Connected to device on attempt %d", attempt)
                    return True
                else:
                    _LOGGER.warning("Connection attempt %d failed", attempt)
                    
            except Exception as exc:
                _LOGGER.warning("Connection attempt %d failed: %s", attempt, exc)
                
            if attempt < self.retry_count:
                await asyncio.sleep(1)  # Wait before retry
                
        return False
        
    async def disconnect(self):
        """Close Modbus connection."""
        if self.client:
            self.client.close()
            self.client = None
            
    def _group_registers(self, registers: Dict[str, int]) -> List[Dict[str, Any]]:
        """Group registers for efficient batch reading."""
        if not registers:
            return []
            
        # Sort registers by address
        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        groups = []
        current_group = {"start": sorted_regs[0][1], "registers": [sorted_regs[0][0]]}
        
        for name, addr in sorted_regs[1:]:
            # Check if this register can be added to current group
            gap = addr - (current_group["start"] + len(current_group["registers"]))
            group_size = len(current_group["registers"])
            
            if gap <= self.max_gap_size and group_size < self.max_batch_size:
                # Fill gaps with placeholder entries
                while gap > 0:
                    current_group["registers"].append(f"_gap_{current_group['start'] + len(current_group['registers'])}")
                    gap -= 1
                current_group["registers"].append(name)
            else:
                # Start new group
                groups.append(current_group)
                current_group = {"start": addr, "registers": [name]}
                
        groups.append(current_group)
        
        _LOGGER.debug("Created %d register groups from %d registers (max_batch=%d, max_gap=%d)", 
                     len(groups), len(registers), self.max_batch_size, self.max_gap_size)
        
        return groups
        
    async def _read_register_batch(self, register_type: str, start_addr: int, count: int, register_names: List[str]) -> Dict[str, bool]:
        """Read a batch of registers and return availability status."""
        if not self.client:
            return {}
            
        try:
            if register_type == "input":
                response = await self.client.read_input_registers(start_addr, count, slave=self.slave_id)
            elif register_type == "holding":
                response = await self.client.read_holding_registers(start_addr, count, slave=self.slave_id)
            elif register_type == "coil":
                response = await self.client.read_coils(start_addr, count, slave=self.slave_id)
            elif register_type == "discrete":
                response = await self.client.read_discrete_inputs(start_addr, count, slave=self.slave_id)
            else:
                return {}
                
            if response.isError():
                _LOGGER.debug("%s Registers batch 0x%04X-0x%04X failed: Modbus error: %s; attempting individual reads for %d registers", 
                             register_type.title(), start_addr, start_addr + count - 1, response, len(register_names))
                # Try individual reads for failed batch
                return await self._read_registers_individually(register_type, start_addr, register_names)
            else:
                _LOGGER.debug("%s register batch 0x%04X-0x%04X succeeded: %d/%d valid registers", 
                             register_type.title(), start_addr, start_addr + count - 1, len(register_names), len(register_names))
                # All registers in this batch are available
                return {name: True for name in register_names if not name.startswith("_gap_")}
                
        except Exception as exc:
            _LOGGER.debug("%s register batch 0x%04X-0x%04X exception: %s", 
                         register_type.title(), start_addr, start_addr + count - 1, exc)
            return await self._read_registers_individually(register_type, start_addr, register_names)
            
    async def _read_registers_individually(self, register_type: str, base_addr: int, register_names: List[str]) -> Dict[str, bool]:
        """Read registers individually when batch read fails."""
        results = {}
        
        for i, name in enumerate(register_names):
            if name.startswith("_gap_"):
                continue
                
            addr = base_addr + i
            try:
                if register_type == "input":
                    response = await self.client.read_input_registers(addr, 1, slave=self.slave_id)
                elif register_type == "holding":
                    response = await self.client.read_holding_registers(addr, 1, slave=self.slave_id)
                elif register_type == "coil":
                    response = await self.client.read_coils(addr, 1, slave=self.slave_id)
                elif register_type == "discrete":
                    response = await self.client.read_discrete_inputs(addr, 1, slave=self.slave_id)
                else:
                    continue
                    
                if not response.isError():
                    results[name] = True
                    _LOGGER.debug("Individual read %s@0x%04X succeeded", name, addr)
                else:
                    _LOGGER.debug("Individual read %s@0x%04X failed: %s", name, addr, response)
                    
            except Exception as exc:
                _LOGGER.debug("Individual read %s@0x%04X failed: %s", name, addr, exc)
                
        return results
        
    async def _scan_register_type(self, register_type: str, registers: Dict[str, int]) -> List[str]:
        """Scan a specific type of registers."""
        if not registers:
            return []
            
        _LOGGER.debug("Scanning %s registers (%d total)", register_type, len(registers))
        
        # Group registers for efficient reading
        groups = self._group_registers(registers)
        
        available = []
        successful_batches = 0
        total_batches = len(groups)
        
        for group in groups:
            start_addr = group["start"]
            register_names = group["registers"]
            count = len(register_names)
            
            # Filter out gap placeholders for logging
            real_registers = [name for name in register_names if not name.startswith("_gap_")]
            
            _LOGGER.debug("Scanning %s batch 0x%04X-0x%04X (%d registers): %s", 
                         register_type, start_addr, start_addr + count - 1, count, real_registers)
            
            batch_results = await self._read_register_batch(register_type, start_addr, count, register_names)
            
            if batch_results:
                successful_batches += 1
                available.extend([name for name, is_available in batch_results.items() if is_available])
                
        _LOGGER.info("%s registers scan: %d/%d registers found", register_type.title(), len(available), len(registers))
        
        # Update scan statistics
        self.scan_stats["total_attempted"] += len(registers)
        self.scan_stats["total_successful"] += len(available)
        if available:
            self.scan_stats["register_types_found"] += 1
            
        return available
        
    async def scan_device(self) -> Dict[str, Any]:
        """Perform comprehensive device scan."""
        start_time = datetime.now()
        
        _LOGGER.info("Starting enhanced device scan for %s:%d (slave_id=%d)", self.host, self.port, self.slave_id)
        
        # Connect to device
        if not await self.connect():
            raise HomeAssistantError(f"Cannot connect to Modbus device at {self.host}:{self.port}")
            
        try:
            _LOGGER.debug("Connected to Modbus device, performing comprehensive scan...")
            
            # Scan each register type
            self.available_registers["input"] = await self._scan_register_type("input", INPUT_REGISTERS)
            self.available_registers["holding"] = await self._scan_register_type("holding", HOLDING_REGISTERS)
            self.available_registers["coil"] = await self._scan_register_type("coil", COIL_REGISTERS)
            self.available_registers["discrete"] = await self._scan_register_type("discrete", DISCRETE_INPUTS)
            
            # Extract device information
            device_info = await self._extract_device_info()
            
            # Analyze capabilities
            capabilities = self._analyze_capabilities()
            
            # Calculate scan statistics
            end_time = datetime.now()
            self.scan_stats["scan_duration"] = (end_time - start_time).total_seconds()
            
            total_found = sum(len(regs) for regs in self.available_registers.values())
            success_rate = (self.scan_stats["total_successful"] / self.scan_stats["total_attempted"] * 100) if self.scan_stats["total_attempted"] > 0 else 0
            
            _LOGGER.info("Device capabilities: %d/%d features detected (%.1f%%)", 
                        len([f for f, v in capabilities.to_dict().items() if v]), 
                        len(capabilities.to_dict()), 
                        len([f for f, v in capabilities.to_dict().items() if v]) / len(capabilities.to_dict()) * 100)
            
            _LOGGER.info("Device scan completed: %.1fs, %.1f%% success (%d/%d), %d register types found", 
                        self.scan_stats["scan_duration"], success_rate, 
                        self.scan_stats["total_successful"], self.scan_stats["total_attempted"],
                        self.scan_stats["register_types_found"])
            
            return {
                "available_registers": self.available_registers,
                "device_info": device_info,
                "device_capabilities": capabilities.to_dict(),
                "scan_stats": self.scan_stats,
                "scan_success_rate": success_rate,
                "total_registers_found": total_found,
            }
            
        finally:
            await self.disconnect()
            
    async def _extract_device_info(self) -> Dict[str, Any]:
        """Extract device information from available registers."""
        device_info = {
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "name": f"ThesslaGreen AirPack ({self.host})",
        }
        
        if not self.client:
            return device_info
            
        try:
            # Try to read firmware version if available
            if "firmware_major" in self.available_registers["input"] and "firmware_minor" in self.available_registers["input"]:
                try:
                    major_response = await self.client.read_input_registers(INPUT_REGISTERS["firmware_major"], 1, slave=self.slave_id)
                    minor_response = await self.client.read_input_registers(INPUT_REGISTERS["firmware_minor"], 1, slave=self.slave_id)
                    
                    if not major_response.isError() and not minor_response.isError():
                        major = major_response.registers[0]
                        minor = minor_response.registers[0]
                        device_info["sw_version"] = f"{major}.{minor}"
                        
                except Exception as exc:
                    _LOGGER.debug("Failed to read firmware version: %s", exc)
                    
            # Try to read serial number if available
            if any(f"serial_number_{i}" in self.available_registers["input"] for i in range(1, 7)):
                try:
                    serial_parts = []
                    for i in range(1, 7):
                        reg_name = f"serial_number_{i}"
                        if reg_name in self.available_registers["input"]:
                            response = await self.client.read_input_registers(INPUT_REGISTERS[reg_name], 1, slave=self.slave_id)
                            if not response.isError() and response.registers[0] != 0:
                                serial_parts.append(f"{response.registers[0]:04X}")
                                
                    if serial_parts:
                        device_info["serial_number"] = "".join(serial_parts)
                        
                except Exception as exc:
                    _LOGGER.debug("Failed to read serial number: %s", exc)
                    
            # Try to read compilation info for unique identifier
            if "compilation_days" in self.available_registers["input"]:
                try:
                    response = await self.client.read_input_registers(INPUT_REGISTERS["compilation_days"], 1, slave=self.slave_id)
                    if not response.isError():
                        # Convert days since 2000-01-01 to date
                        base_date = datetime(2000, 1, 1)
                        compilation_date = base_date + timedelta(days=response.registers[0])
                        device_info["compilation_date"] = compilation_date.strftime("%Y-%m-%d")
                        
                except Exception as exc:
                    _LOGGER.debug("Failed to read compilation date: %s", exc)
                    
        except Exception as exc:
            _LOGGER.error("Error extracting device info: %s", exc)
            
        return device_info
        
    def _analyze_capabilities(self) -> DeviceCapabilities:
        """Analyze available registers to determine device capabilities."""
        capabilities = DeviceCapabilities()
        
        # Check for temperature sensors
        temp_registers = ["outside_temperature", "supply_temperature", "exhaust_temperature", "fpx_temperature", "gwc_temperature", "ambient_temperature"]
        capabilities.has_temperature_sensors = any(reg in self.available_registers["input"] for reg in temp_registers)
        
        # Check for flow sensors  
        flow_registers = ["supply_flowrate", "exhaust_flowrate", "supply_percentage", "exhaust_percentage"]
        capabilities.has_flow_sensors = any(reg in self.available_registers["input"] for reg in flow_registers)
        
        # Check for GWC system
        gwc_registers = ["gwc_temperature", "gwc_activation_temp", "gwc_bypass_active"]
        capabilities.has_gwc = any(reg in self.available_registers["input"] + self.available_registers["holding"] for reg in gwc_registers)
        
        # Check for bypass system
        bypass_registers = ["bypass_activation_temp", "bypassing_factor", "bypass_active"]
        capabilities.has_bypass = any(reg in self.available_registers["input"] + self.available_registers["holding"] for reg in bypass_registers)
        
        # Check for heating system
        heating_registers = ["duct_supply_temperature", "heating_season", "frost_protection_temp"]
        capabilities.has_heating = any(reg in self.available_registers["input"] + self.available_registers["holding"] for reg in heating_registers)
        
        # Check for scheduling
        schedule_registers = [reg for reg in self.available_registers["holding"] if "schedule_" in reg]
        capabilities.has_scheduling = len(schedule_registers) > 0
        
        # Check for air quality sensors
        air_quality_registers = ["co2_concentration", "voc_level", "air_quality_index", "outside_humidity", "inside_humidity"]
        capabilities.has_air_quality = any(reg in self.available_registers["input"] for reg in air_quality_registers)
        
        # Check for pressure sensors
        pressure_registers = ["supply_pressure", "exhaust_pressure", "supply_pressure_pa", "exhaust_pressure_pa"]
        capabilities.has_pressure_sensors = any(reg in self.available_registers["input"] for reg in pressure_registers)
        
        # Check for filter monitoring
        filter_registers = ["filter_time_remaining", "filter_operating_hours", "filter_alarm"]
        capabilities.has_filter_monitoring = any(reg in self.available_registers["input"] + self.available_registers["holding"] for reg in filter_registers)
        
        # Check for constant flow
        cf_registers = ["constant_flow_active", "constant_pressure_setpoint", "constant_flow_control"]
        capabilities.has_constant_flow = any(reg in self.available_registers["input"] + self.available_registers["holding"] + self.available_registers["coil"] for reg in cf_registers)
        
        # Detect special functions based on available registers
        if "pusty_dom_intensity" in self.available_registers["holding"]:
            capabilities.special_functions.append("PUSTY_DOM")
        if "boost_intensity" in self.available_registers["holding"]:
            capabilities.special_functions.append("BOOST")
        if any("okap" in reg.lower() for reg in self.available_registers["holding"]):
            capabilities.special_functions.append("OKAP")
        if any("kominek" in reg.lower() for reg in self.available_registers["holding"]):
            capabilities.special_functions.append("KOMINEK")
        if any("wietrzenie" in reg.lower() for reg in self.available_registers["holding"]):
            capabilities.special_functions.append("WIETRZENIE")
            
        # Detect operating modes
        if "mode" in self.available_registers["holding"]:
            capabilities.operating_modes.extend(["AUTOMATYCZNY", "MANUALNY", "CHWILOWY"])
            
        return capabilities