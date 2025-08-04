"""Enhanced device capability scanner for ThesslaGreen Modbus - OPTIMIZED VERSION."""
from __future__ import annotations

import asyncio
import logging
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
        self.available_registers: Dict[str, Set[str]] = {}
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
        """Optimized synchronous device scanning."""
        import time
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
        """Enhanced device information scanning with error handling."""
        try:
            # Priority 1: Firmware version (always present)
            result = client.read_input_registers(0x0000, 5, slave=self.slave_id)
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

        # Priority 2: Serial number
        try:
            result = client.read_input_registers(0x0018, 6, slave=self.slave_id)
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

        # Priority 3: Device name
        try:
            result = client.read_holding_registers(0x1FD0, 8, slave=self.slave_id)
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
        """Optimized input register scanning with intelligent batching."""
        available = set()
        
        # Define scan priorities based on register importance and grouping
        scan_groups = [
            # Critical system registers
            ("critical", {
                "firmware_major": 0x0000, "firmware_minor": 0x0001, "firmware_patch": 0x0004,
                "day_of_week": 0x0002, "period": 0x0003,
            }),
            # Temperature sensors (critical for HVAC)
            ("temperatures", {
                "outside_temperature": 0x0010, "supply_temperature": 0x0011,
                "exhaust_temperature": 0x0012, "fpx_temperature": 0x0013,
                "duct_supply_temperature": 0x0014, "gwc_temperature": 0x0015,
                "ambient_temperature": 0x0016,
            }),
            # Serial number
            ("serial", {
                f"serial_number_{i}": 0x0018 + i - 1 for i in range(1, 7)
            }),
            # Constant Flow system
            ("constant_flow", {
                "constant_flow_active": 0x010F, "supply_percentage": 0x0110,
                "exhaust_percentage": 0x0111, "supply_flowrate": 0x0112,
                "exhaust_flowrate": 0x0113, "min_percentage": 0x0114,
                "max_percentage": 0x0115, "water_removal_active": 0x012A,
            }),
            # Air flow values
            ("airflow", {
                "supply_air_flow": 0x0100, "exhaust_air_flow": 0x0101,
            }),
            # DAC outputs
            ("dac", {
                "dac_supply": 0x0500, "dac_exhaust": 0x0501,
                "dac_heater": 0x0502, "dac_cooler": 0x0503,
            }),
        ]
        
        for group_name, registers in scan_groups:
            _LOGGER.debug("Scanning input register group: %s", group_name)
            group_available = self._scan_register_group_batch(client, registers, "input")
            available.update(group_available)
            
            # Log group results
            if group_available:
                _LOGGER.debug("Group %s: found %d/%d registers", 
                            group_name, len(group_available), len(registers))
        
        return available

    def _scan_holding_registers_optimized(self, client: ModbusTcpClient) -> Set[str]:
        """Optimized holding register scanning with smart grouping."""
        available = set()
        
        # Define scan priorities - start with most critical registers
        scan_groups = [
            # Critical control registers (MUST be present)
            ("critical_control", {
                "on_off_panel_mode": 0x1123, "mode": 0x1070, "season_mode": 0x1071,
                "air_flow_rate_manual": 0x1072, "air_flow_rate_temporary": 0x1073,
                "stop_ahu_code": 0x1120,
            }),
            # Basic operation parameters
            ("basic_operation", {
                "supply_air_temperature_manual": 0x1074, "supply_air_temperature_temporary": 0x1075,
                "special_mode": 0x1080, "antifreeze_mode": 0x1060, "antifreeze_stage": 0x1066,
            }),
            # AirS panel settings
            ("airs_panel", {
                "fan_speed_1_coef": 0x1078, "fan_speed_2_coef": 0x1079, "fan_speed_3_coef": 0x107A,
            }),
            # Special function coefficients
            ("special_functions", {
                "hood_supply_coef": 0x1082, "hood_exhaust_coef": 0x1083,
                "fireplace_supply_coef": 0x1084, "airing_coef": 0x1086,
                "contamination_coef": 0x1087, "empty_house_coef": 0x1088,
            }),
            # GWC system
            ("gwc_system", {
                "gwc_off": 0x10A0, "min_gwc_air_temperature": 0x10A1,
                "max_gwc_air_temperature": 0x10A2, "gwc_regen": 0x10A6,
                "gwc_mode": 0x10A7, "gwc_regen_period": 0x10A8,
            }),
            # Bypass system  
            ("bypass_system", {
                "bypass_off": 0x10E0, "min_bypass_temperature": 0x10E1,
                "air_temperature_summer_free_heating": 0x10E2,
                "air_temperature_summer_free_cooling": 0x10E3,
                "bypass_mode": 0x10EA, "bypass_user_mode": 0x10EB,
            }),
            # Comfort mode
            ("comfort_mode", {
                "comfort_mode_panel": 0x10D0, "comfort_mode": 0x10D1, "required_temp": 0x1FFE,
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
        """Scan a group of registers efficiently using batch reads where possible."""
        available = set()
        
        if not registers:
            return available
        
        # Try batch read first if registers are close together
        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        batches = self._group_registers_for_batch_read(dict(sorted_regs))
        
        for batch_start, batch_registers in batches.items():
            max_addr = max(addr for addr in batch_registers.values())
            count = max_addr - batch_start + 1
            
            if count > 125:  # Modbus limit
                # Fall back to individual reads
                for name, addr in batch_registers.items():
                    if self._scan_single_register(client, name, addr, reg_type):
                        available.add(name)
                continue
            
            try:
                if reg_type == "input":
                    result = client.read_input_registers(batch_start, count, slave=self.slave_id)
                elif reg_type == "holding":
                    result = client.read_holding_registers(batch_start, count, slave=self.slave_id)
                else:
                    continue
                
                self._scan_stats["total_attempts"] += 1
                
                if not result.isError():
                    self._scan_stats["successful_reads"] += 1
                    
                    for name, address in batch_registers.items():
                        idx = address - batch_start
                        if idx < len(result.registers):
                            value = result.registers[idx]
                            if self._is_valid_register_value(name, value):
                                available.add(name)
                                _LOGGER.debug("Found %s register %s (0x%04X) = %s", 
                                            reg_type, name, address, value)
                else:
                    self._scan_stats["failed_reads"] += 1
                    # Fall back to individual reads
                    for name, addr in batch_registers.items():
                        if self._scan_single_register(client, name, addr, reg_type):
                            available.add(name)
                            
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug("Batch read failed at 0x%04X: %s", batch_start, exc)
                # Fall back to individual reads
                for name, addr in batch_registers.items():
                    if self._scan_single_register(client, name, addr, reg_type):
                        available.add(name)
        
        return available

    def _scan_single_register(self, client: ModbusTcpClient, name: str, 
                             address: int, reg_type: str) -> bool:
        """Scan a single register with error handling."""
        try:
            if reg_type == "input":
                result = client.read_input_registers(address, 1, slave=self.slave_id)
            elif reg_type == "holding":
                result = client.read_holding_registers(address, 1, slave=self.slave_id)
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
        """Efficiently scan all coil registers in minimal number of reads."""
        available = set()
        
        if not COIL_REGISTERS:
            return available
        
        min_addr = min(COIL_REGISTERS.values())
        max_addr = max(COIL_REGISTERS.values())
        count = max_addr - min_addr + 1
        
        try:
            result = client.read_coils(min_addr, count, slave=self.slave_id)
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
        """Efficiently scan all discrete input registers."""
        available = set()
        
        if not DISCRETE_INPUT_REGISTERS:
            return available
        
        min_addr = min(DISCRETE_INPUT_REGISTERS.values())
        max_addr = max(DISCRETE_INPUT_REGISTERS.values())
        count = max_addr - min_addr + 1
        
        try:
            result = client.read_discrete_inputs(min_addr, count, slave=self.slave_id)
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

        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        batches = {}
        current_batch = {}
        current_start = None

        for name, addr in sorted_regs:
            if current_start is None:
                current_start = addr
                current_batch[name] = addr
            elif addr - current_start <= max_gap and len(current_batch) < 100:
                current_batch[name] = addr
            else:
                if current_batch:
                    batches[current_start] = current_batch
                current_start = addr
                current_batch = {name: addr}

        if current_batch:
            batches[current_start] = current_batch

        return batches

    def _analyze_capabilities_enhanced(self) -> Dict[str, bool]:
        """Enhanced capability analysis with better model detection."""
        capabilities = {}
        
        input_regs = self.available_registers.get("input_registers", set())
        holding_regs = self.available_registers.get("holding_registers", set())
        coil_regs = self.available_registers.get("coil_registers", set())
        discrete_regs = self.available_registers.get("discrete_inputs", set())
        
        # Core system capabilities
        capabilities["basic_control"] = "mode" in holding_regs and "on_off_panel_mode" in holding_regs
        capabilities["temperature_control"] = "supply_air_temperature_manual" in holding_regs
        capabilities["intensity_control"] = "air_flow_rate_manual" in holding_regs
        
        # Advanced system capabilities
        capabilities["constant_flow"] = "constant_flow_active" in input_regs
        capabilities["gwc_system"] = "gwc_mode" in holding_regs or "gwc" in coil_regs
        capabilities["bypass_system"] = "bypass_mode" in holding_regs or "bypass" in coil_regs
        capabilities["comfort_mode"] = "comfort_mode" in holding_regs
        capabilities["expansion_module"] = "expansion" in discrete_regs
        
        # Module capabilities
        capabilities["cf_module"] = capabilities["constant_flow"]
        capabilities["fpx_system"] = "antifreeze_mode" in holding_regs or "fpx_temperature" in input_regs
        
        # Sensor capabilities
        temp_sensors = ["outside_temperature", "supply_temperature", "exhaust_temperature", 
                       "fpx_temperature", "duct_supply_temperature", "gwc_temperature", "ambient_temperature"]
        for sensor in temp_sensors:
            capabilities[f"sensor_{sensor}"] = sensor in input_regs
        
        # Count available temperature sensors
        temp_sensor_count = sum(1 for sensor in temp_sensors if sensor in input_regs)
        capabilities["temperature_sensors_count"] = temp_sensor_count
        
        # Special function capabilities
        special_functions = ["hood_supply_coef", "fireplace_supply_coef", "airing_coef", 
                           "contamination_coef", "empty_house_coef"]
        for func in special_functions:
            capabilities[f"function_{func.replace('_coef', '')}"] = func in holding_regs
        
        # Control output capabilities
        outputs = ["power_supply_fans", "heating_cable", "gwc", "hood", "bypass"]
        for output in outputs:
            capabilities[f"output_{output}"] = output in coil_regs
        
        # Input capabilities
        inputs = ["contamination_sensor", "airing_sensor", "fireplace", "empty_house", 
                 "hood_input", "fire_alarm"]
        for input_reg in inputs:
            capabilities[f"input_{input_reg}"] = input_reg in discrete_regs
        
        # Model determination based on capabilities
        capabilities["model_type"] = self._determine_model_type(capabilities)
        
        return capabilities

    def _determine_model_type(self, capabilities: Dict[str, bool]) -> str:
        """Determine AirPack model type based on detected capabilities."""
        if capabilities.get("constant_flow") and capabilities.get("gwc_system"):
            return "AirPack Home Energy+ with CF and GWC"
        elif capabilities.get("constant_flow"):
            return "AirPack Home Energy+ with CF"
        elif capabilities.get("gwc_system"):
            return "AirPack Home with GWC"
        elif capabilities.get("expansion_module"):
            return "AirPack Home with Expansion"
        elif capabilities.get("basic_control"):
            return "AirPack Home Basic"
        else:
            return "AirPack Unknown"

    def _validate_model_capabilities(self, capabilities: Dict[str, bool]) -> None:
        """Validate detected capabilities against known model constraints."""
        # Check for impossible combinations
        if capabilities.get("constant_flow") and not capabilities.get("sensor_supply_temperature"):
            _LOGGER.warning("Constant Flow detected but supply temperature sensor missing - unusual configuration")
        
        if capabilities.get("gwc_system") and not capabilities.get("sensor_gwc_temperature"):
            _LOGGER.warning("GWC system detected but GWC temperature sensor missing")
        
        if capabilities.get("bypass_system") and not capabilities.get("output_bypass"):
            _LOGGER.warning("Bypass system detected but bypass output coil missing")
        
        # Log model-specific optimizations
        model_type = capabilities.get("model_type", "Unknown")
        _LOGGER.info("Detected device model: %s", model_type)
        
        if "Energy+" in model_type:
            _LOGGER.debug("Energy+ model detected - enhanced features available")
        
        if "CF" in model_type:
            _LOGGER.debug("Constant Flow module detected - precision air flow control available")