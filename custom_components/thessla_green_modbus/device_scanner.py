"""Enhanced device scanner for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Set

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    COIL_REGISTERS,
    DISCRETE_INPUTS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
)

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenDeviceScanner:
    """Enhanced device scanner for capability detection - HA 2025.7+ Compatible."""

    def __init__(self, host: str, port: int, slave_id: int) -> None:
        """Initialize the enhanced device scanner."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        
        # Enhanced scanning statistics
        self._scan_stats = {
            "total_attempts": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "timeouts": 0,
            "errors": 0,
        }
        
        _LOGGER.debug("Initialized device scanner for %s:%s (slave_id=%s)", host, port, slave_id)

    async def scan_device(self) -> Dict[str, Any]:
        """Main device scanning function with enhanced capability detection."""
        return await asyncio.to_thread(self._scan_device_sync)
    
    def _scan_device_sync(self) -> Dict[str, Any]:
        """Synchronous device scanning with comprehensive capability detection."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=10, retries=3)
        
        result = {
            "available_registers": {
                "input_registers": set(),
                "holding_registers": set(), 
                "coil_registers": set(),
                "discrete_inputs": set()
            },
            "device_info": {},
            "capabilities": {},
            "scan_stats": {}
        }
        
        try:
            if not client.connect():
                raise Exception(f"Failed to connect to {self.host}:{self.port}")
            
            _LOGGER.info("Connected to %s:%s, starting enhanced capability scan...", self.host, self.port)
            
            # Enhanced parallel scanning of all register types
            result["available_registers"]["input_registers"] = self._scan_input_registers_batch(client)
            result["available_registers"]["holding_registers"] = self._scan_holding_registers_batch(client)
            result["available_registers"]["coil_registers"] = self._scan_coil_registers_batch(client)
            result["available_registers"]["discrete_inputs"] = self._scan_discrete_inputs_batch(client)
            
            # Extract enhanced device information
            result["device_info"] = self._extract_device_info_enhanced(client)
            
            # Analyze capabilities based on available registers
            result["capabilities"] = self._analyze_capabilities_enhanced(result["available_registers"])
            
            # Calculate comprehensive scan statistics
            total_found = sum(len(regs) for regs in result["available_registers"].values())
            total_attempts = max(self._scan_stats["total_attempts"], 1)
            success_rate = (self._scan_stats["successful_reads"] / total_attempts) * 100
            
            result["scan_stats"] = {
                **self._scan_stats,
                "total_registers_found": total_found,
                "success_rate": success_rate,
                "scan_duration": "optimized_batch_scanning"
            }
            
            capability_count = len([k for k, v in result["capabilities"].items() if v and isinstance(v, bool)])
            
            _LOGGER.info(
                "Enhanced scan completed: %d registers found (%.1f%% success rate), %d capabilities detected",
                total_found, success_rate, capability_count
            )
            
        except Exception as exc:
            _LOGGER.error("Enhanced device scan failed: %s", exc)
            self._scan_stats["errors"] += 1
            raise
        finally:
            client.close()
        
        return result

    def _scan_input_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of input registers with intelligent grouping."""
        available_registers = set()
        
        # Group registers by address ranges for efficient batch reading
        register_groups = self._create_register_groups(INPUT_REGISTERS)
        
        for start_addr, count, register_keys in register_groups:
            try:
                self._scan_stats["total_attempts"] += 1
                response = client.read_input_registers(start_addr, count, slave=self.slave_id)
                
                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    # All registers in this batch are available
                    available_registers.update(register_keys)
                    _LOGGER.debug("Input register batch %s-%s: %d registers found", 
                                start_addr, start_addr + count - 1, len(register_keys))
                else:
                    self._scan_stats["failed_reads"] += 1
                    _LOGGER.debug("Input register batch %s-%s failed: %s", 
                                start_addr, start_addr + count - 1, response)
                    
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug("Input register batch %s failed: %s", start_addr, exc)
                continue
        
        _LOGGER.info("Input registers scan: %d registers found", len(available_registers))
        return available_registers

    def _scan_holding_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of holding registers."""
        available_registers = set()
        
        register_groups = self._create_register_groups(HOLDING_REGISTERS)
        
        for start_addr, count, register_keys in register_groups:
            try:
                self._scan_stats["total_attempts"] += 1
                response = client.read_holding_registers(start_addr, count, slave=self.slave_id)
                
                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    available_registers.update(register_keys)
                    _LOGGER.debug("Holding register batch %s-%s: %d registers found", 
                                start_addr, start_addr + count - 1, len(register_keys))
                else:
                    self._scan_stats["failed_reads"] += 1
                    
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug("Holding register batch %s failed: %s", start_addr, exc)
                continue
        
        _LOGGER.info("Holding registers scan: %d registers found", len(available_registers))
        return available_registers

    def _scan_coil_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of coil registers."""
        available_registers = set()
        
        register_groups = self._create_register_groups(COIL_REGISTERS)
        
        for start_addr, count, register_keys in register_groups:
            try:
                self._scan_stats["total_attempts"] += 1
                response = client.read_coils(start_addr, count, slave=self.slave_id)
                
                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    available_registers.update(register_keys)
                    _LOGGER.debug("Coil register batch %s-%s: %d registers found", 
                                start_addr, start_addr + count - 1, len(register_keys))
                else:
                    self._scan_stats["failed_reads"] += 1
                    
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug("Coil register batch %s failed: %s", start_addr, exc)
                continue
        
        _LOGGER.info("Coil registers scan: %d registers found", len(available_registers))
        return available_registers

    def _scan_discrete_inputs_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of discrete inputs."""
        available_registers = set()
        
        register_groups = self._create_register_groups(DISCRETE_INPUTS)
        
        for start_addr, count, register_keys in register_groups:
            try:
                self._scan_stats["total_attempts"] += 1
                response = client.read_discrete_inputs(start_addr, count, slave=self.slave_id)
                
                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    available_registers.update(register_keys)
                    _LOGGER.debug("Discrete input batch %s-%s: %d registers found", 
                                start_addr, start_addr + count - 1, len(register_keys))
                else:
                    self._scan_stats["failed_reads"] += 1
                    
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug("Discrete input batch %s failed: %s", start_addr, exc)
                continue
        
        _LOGGER.info("Discrete inputs scan: %d registers found", len(available_registers))
        return available_registers

    def _create_register_groups(self, register_map: Dict[str, int]) -> list:
        """Create optimized register groups for batch reading."""
        if not register_map:
            return []
            
        # Sort registers by address
        sorted_registers = sorted(register_map.items(), key=lambda x: x[1])
        groups = []
        
        current_group_start = None
        current_group_keys = []
        current_group_start_addr = None
        max_gap = 10  # Maximum gap between registers to include in same batch
        max_batch_size = 125  # Modbus maximum batch size
        
        for key, addr in sorted_registers:
            if current_group_start is None:
                # Start new group
                current_group_start = key
                current_group_start_addr = addr
                current_group_keys = [key]
            elif (addr <= current_group_start_addr + len(current_group_keys) + max_gap and 
                  len(current_group_keys) < max_batch_size):
                # Continue current group
                current_group_keys.append(key)
            else:
                # Finish current group and start new one
                if current_group_keys:
                    addresses = [register_map[k] for k in current_group_keys]
                    count = max(addresses) - current_group_start_addr + 1
                    groups.append((current_group_start_addr, count, current_group_keys))
                
                current_group_start = key
                current_group_start_addr = addr
                current_group_keys = [key]
        
        # Add the last group
        if current_group_keys:
            addresses = [register_map[k] for k in current_group_keys]
            count = max(addresses) - current_group_start_addr + 1
            groups.append((current_group_start_addr, count, current_group_keys))
            
        return groups

    def _extract_device_info_enhanced(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Extract enhanced device information with better error handling."""
        device_info = {
            "device_name": "ThesslaGreen AirPack",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "firmware": "Unknown",
            "serial_number": None,
        }
        
        # Enhanced firmware version reading
        try:
            response = client.read_input_registers(0x0050, 1, slave=self.slave_id)
            if not response.isError() and response.registers:
                raw_fw = response.registers[0]
                if raw_fw != 0x8000 and raw_fw != 0xFFFF:  # Valid firmware value
                    major = (raw_fw >> 8) & 0xFF
                    minor = raw_fw & 0xFF
                    device_info["firmware"] = f"{major}.{minor}"
                    
                    # Enhanced model detection based on firmware
                    if major >= 5:
                        device_info["model"] = "AirPack Home Energy+ v2"
                    elif major >= 4:
                        device_info["model"] = "AirPack Home Energy+"
                    else:
                        device_info["model"] = "AirPack Home"
                        
        except Exception as exc:
            _LOGGER.debug("Failed to read firmware: %s", exc)
        
        # Enhanced serial number reading
        try:
            response = client.read_input_registers(0x0051, 2, slave=self.slave_id)
            if not response.isError() and len(response.registers) >= 2:
                serial_high = response.registers[0]
                serial_low = response.registers[1]
                if serial_high != 0x8000 and serial_low != 0x8000:
                    serial_number = (serial_high << 16) + serial_low
                    device_info["serial_number"] = str(serial_number)
                    
        except Exception as exc:
            _LOGGER.debug("Failed to read serial number: %s", exc)
        
        # Enhanced device name based on available capabilities
        device_info["device_name"] = f"ThesslaGreen AirPack ({self.host})"
        
        _LOGGER.debug("Device info extracted: %s", device_info)
        return device_info

    def _analyze_capabilities_enhanced(self, available_registers: Dict[str, Set[str]]) -> Dict[str, Any]:
        """Enhanced capability analysis based on available registers."""
        input_regs = available_registers.get("input_registers", set())
        holding_regs = available_registers.get("holding_registers", set())
        coil_regs = available_registers.get("coil_registers", set())
        discrete_regs = available_registers.get("discrete_inputs", set())
        
        capabilities = {}
        
        # Enhanced basic control detection
        capabilities["basic_control"] = bool(
            "mode" in holding_regs and 
            ("system_on_off" in coil_regs or "on_off_panel_mode" in holding_regs)
        )
        
        # Enhanced temperature control capabilities
        temp_sensors = ["outside_temperature", "supply_temperature", "exhaust_temperature", 
                       "fpx_temperature", "duct_supply_temperature", "gwc_temperature", "ambient_temperature"]
        detected_temp_sensors = [sensor for sensor in temp_sensors if sensor in input_regs]
        capabilities["temperature_sensors_count"] = len(detected_temp_sensors)
        
        for sensor in detected_temp_sensors:
            capabilities[f"sensor_{sensor}"] = True
        
        # Enhanced flow control capabilities
        capabilities["flow_measurement"] = bool(
            "supply_flowrate" in input_regs or "exhaust_flowrate" in input_regs
        )
        
        capabilities["intensity_control"] = bool(
            "air_flow_rate_manual" in holding_regs or 
            "supply_percentage" in input_regs
        )
        
        # Enhanced advanced system capabilities
        capabilities["constant_flow"] = bool(
            "constant_flow_active" in coil_regs and
            "constant_flow_supply" in input_regs
        )
        
        capabilities["gwc_system"] = bool(
            "gwc_active" in coil_regs and
            "gwc_temperature" in input_regs
        )
        
        capabilities["bypass_system"] = bool(
            "bypass_active" in coil_regs and
            ("bypass_position" in input_regs or "bypass_mode" in holding_regs)
        )
        
        capabilities["comfort_mode"] = bool(
            "comfort_active" in coil_regs and
            "comfort_mode" in holding_regs
        )
        
        # Enhanced special functions detection
        capabilities["special_functions"] = bool("special_mode" in holding_regs)
        
        # Enhanced diagnostics capabilities
        capabilities["error_reporting"] = bool(
            "error_code" in input_regs or "warning_code" in input_regs
        )
        
        capabilities["filter_monitoring"] = bool(
            "filter_time_remaining" in input_regs or "filter_warning" in coil_regs
        )
        
        capabilities["operating_hours"] = bool("operating_hours" in input_regs)
        
        # Enhanced system status detection
        system_status_sensors = ["supply_fan_ok", "exhaust_fan_ok", "heat_exchanger_ok", 
                               "outside_temp_sensor_ok", "supply_temp_sensor_ok"]
        has_status_monitoring = False
        for sensor in system_status_sensors:
            if sensor in discrete_regs:
                has_status_monitoring = True
                break
        capabilities["system_status_monitoring"] = has_status_monitoring
        
        # Enhanced power monitoring (HA 2025.7+)
        capabilities["power_monitoring"] = bool(
            "actual_power_consumption" in input_regs or "cumulative_power_consumption" in input_regs
        )
        
        # Enhanced expansion module detection
        expansion_indicators = ["expansion", "humidity_sensor_ok", "external_heater_active"]
        has_expansion = False
        for indicator in expansion_indicators:
            if indicator in discrete_regs:
                has_expansion = True
                break
        capabilities["expansion_module"] = has_expansion
        
        # Enhanced recovery system capabilities
        capabilities["heat_recovery"] = bool(
            "heat_recovery_efficiency" in input_regs and
            "supply_temperature" in input_regs and
            "exhaust_temperature" in input_regs
        )
        
        # Enhanced maintenance capabilities
        capabilities["maintenance_mode"] = bool("maintenance_mode" in coil_regs)
        
        capabilities["advanced_configuration"] = bool(
            len(holding_regs) > 10 and  # Many configuration options
            "filter_change_interval" in holding_regs
        )
        
        # Enhanced seasonal adaptation
        capabilities["seasonal_modes"] = bool(
            "season_mode" in holding_regs and
            ("summer_mode" in coil_regs or "antifreeze_mode" in coil_regs)
        )
        
        # Count total capabilities (only boolean True values)
        boolean_capabilities = [k for k, v in capabilities.items() 
                              if isinstance(v, bool) and v and k != "total_capabilities"]
        active_capabilities = len(boolean_capabilities)
        capabilities["total_capabilities"] = active_capabilities
        
        _LOGGER.info("Capability analysis: %d capabilities detected", active_capabilities)
        _LOGGER.debug("Detected capabilities: %s", boolean_capabilities)
        
        return capabilities