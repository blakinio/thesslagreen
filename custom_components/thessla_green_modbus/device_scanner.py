"""Enhanced device scanner for ThesslaGreen Modbus integration.
Autoscan z kompletną diagnostyką i logowaniem błędów.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    COIL_REGISTERS,
    DISCRETE_INPUTS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    REGISTER_PROCESSING,
)

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenDeviceScanner:
    """Enhanced device scanner with comprehensive diagnostics and error logging."""

    def __init__(
        self,
        host: str,
        port: int,
        slave_id: int,
        timeout: int = 10,
        max_batch_size: int = 16,
        max_gap: int = 10,
    ) -> None:
        """Initialize the enhanced device scanner."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.max_batch_size = max_batch_size
        self.max_gap = max_gap
        
        # Enhanced scanning statistics
        self._scan_stats = {
            "start_time": None,
            "end_time": None,
            "duration": 0,
            "total_attempts": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "success_rate": 0.0,
            "failed_groups": [],
            "register_counts": {},
            "capabilities_detected": {},
            "device_info": {},
            "error_details": [],
            "performance_metrics": {},
        }

    async def scan_device(self) -> Dict[str, Any]:
        """Perform comprehensive device scan with enhanced diagnostics."""
        _LOGGER.info("Starting enhanced device scan for %s:%s (slave_id=%s)", 
                    self.host, self.port, self.slave_id)
        
        self._scan_stats["start_time"] = datetime.now()
        
        # Enhanced connection with retry logic
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            # Connection with multiple attempts
            connection_attempts = 3
            connected = False
            
            for attempt in range(connection_attempts):
                try:
                    if client.connect():
                        connected = True
                        _LOGGER.debug("Connected to device on attempt %d", attempt + 1)
                        break
                    else:
                        _LOGGER.warning("Connection attempt %d failed", attempt + 1)
                        if attempt < connection_attempts - 1:
                            await asyncio.sleep(2)  # Wait before retry
                except Exception as exc:
                    _LOGGER.warning("Connection attempt %d error: %s", attempt + 1, exc)
                    if attempt < connection_attempts - 1:
                        await asyncio.sleep(2)
            
            if not connected:
                raise Exception(f"Failed to connect after {connection_attempts} attempts")
            
            _LOGGER.debug("Connected to Modbus device, performing comprehensive scan...")
            
            # Scan all register types with enhanced error handling
            available_registers = {
                "input_registers": await self._scan_input_registers_enhanced(client),
                "holding_registers": await self._scan_holding_registers_enhanced(client),
                "coil_registers": await self._scan_coil_registers_enhanced(client),
                "discrete_inputs": await self._scan_discrete_inputs_enhanced(client),
            }
            
            # Store register counts
            for reg_type, registers in available_registers.items():
                self._scan_stats["register_counts"][reg_type] = len(registers)
            
            # Extract enhanced device information
            device_info = await self._extract_device_info_enhanced(client, available_registers)
            
            # Analyze comprehensive capabilities
            capabilities = self._analyze_capabilities_enhanced(available_registers)
            
            # Calculate performance metrics
            self._calculate_performance_metrics()
            
            return {
                "available_registers": available_registers,
                "device_info": device_info,
                "capabilities": capabilities,
                "scan_statistics": self._scan_stats,
            }
            
        finally:
            try:
                client.close()
            except Exception as exc:
                _LOGGER.debug("Error closing connection: %s", exc)
            
            self._scan_stats["end_time"] = datetime.now()
            if self._scan_stats["start_time"]:
                self._scan_stats["duration"] = (
                    self._scan_stats["end_time"] - self._scan_stats["start_time"]
                ).total_seconds()
            
            # Calculate final success rate
            if self._scan_stats["total_attempts"] > 0:
                self._scan_stats["success_rate"] = (
                    self._scan_stats["successful_reads"] / self._scan_stats["total_attempts"] * 100
                )
            
            _LOGGER.info(
                "Device scan completed: %.1fs, %.1f%% success (%d/%d), %d register types found",
                self._scan_stats["duration"],
                self._scan_stats["success_rate"],
                self._scan_stats["successful_reads"],
                self._scan_stats["total_attempts"],
                len([k for k, v in self._scan_stats["register_counts"].items() if v > 0])
            )

    async def _scan_input_registers_enhanced(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of input registers with detailed error tracking."""
        _LOGGER.debug("Scanning input registers (%d total)", len(INPUT_REGISTERS))
        available_registers = set()

        register_groups = self._create_register_groups_enhanced(INPUT_REGISTERS)
        
        for group_info in register_groups:
            start_addr = group_info["start_addr"]
            count = group_info["count"]
            register_keys = group_info["register_keys"]
            end_addr = start_addr + count - 1
            
            _LOGGER.debug(
                "Scanning input register batch 0x%04X-0x%04X (%d registers): %s",
                start_addr, end_addr, len(register_keys), list(register_keys)
            )

            self._scan_stats["total_attempts"] += 1
            
            try:
                # pymodbus 3.5+ compatible call
                response = client.read_input_registers(
                    address=start_addr,
                    count=count,
                    slave=self.slave_id,
                )

                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    # Validate register values before adding
                    valid_registers = self._validate_register_batch(
                        register_keys, response.registers, "input"
                    )
                    available_registers.update(valid_registers)
                    
                    _LOGGER.debug(
                        "Input register batch 0x%04X-0x%04X succeeded: %d/%d valid registers",
                        start_addr, end_addr, len(valid_registers), len(register_keys)
                    )
                else:
                    self._handle_batch_error(
                        "input_registers", start_addr, end_addr, register_keys, 
                        f"Modbus error: {response}", client
                    )
                    
            except asyncio.TimeoutError:
                self._handle_batch_error(
                    "input_registers", start_addr, end_addr, register_keys, 
                    "timeout", client
                )
            except Exception as exc:
                self._handle_batch_error(
                    "input_registers", start_addr, end_addr, register_keys, 
                    str(exc), client
                )

        _LOGGER.info("Input registers scan: %d/%d registers found", 
                    len(available_registers), len(INPUT_REGISTERS))
        return available_registers

    async def _scan_holding_registers_enhanced(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of holding registers with detailed error tracking."""
        _LOGGER.debug("Scanning holding registers (%d total)", len(HOLDING_REGISTERS))
        available_registers = set()

        register_groups = self._create_register_groups_enhanced(HOLDING_REGISTERS)
        
        for group_info in register_groups:
            start_addr = group_info["start_addr"]
            count = group_info["count"]
            register_keys = group_info["register_keys"]
            end_addr = start_addr + count - 1
            
            _LOGGER.debug(
                "Scanning holding register batch 0x%04X-0x%04X (%d registers): %s",
                start_addr, end_addr, len(register_keys), list(register_keys)[:5]  # Limit log output
            )

            self._scan_stats["total_attempts"] += 1
            
            try:
                # pymodbus 3.5+ compatible call
                response = client.read_holding_registers(
                    address=start_addr,
                    count=count,
                    slave=self.slave_id,
                )

                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    # Validate register values before adding
                    valid_registers = self._validate_register_batch(
                        register_keys, response.registers, "holding"
                    )
                    available_registers.update(valid_registers)
                    
                    _LOGGER.debug(
                        "Holding register batch 0x%04X-0x%04X succeeded: %d/%d valid registers",
                        start_addr, end_addr, len(valid_registers), len(register_keys)
                    )
                else:
                    self._handle_batch_error(
                        "holding_registers", start_addr, end_addr, register_keys, 
                        f"Modbus error: {response}", client
                    )
                    
            except asyncio.TimeoutError:
                self._handle_batch_error(
                    "holding_registers", start_addr, end_addr, register_keys, 
                    "timeout", client
                )
            except Exception as exc:
                self._handle_batch_error(
                    "holding_registers", start_addr, end_addr, register_keys, 
                    str(exc), client
                )

        _LOGGER.info("Holding registers scan: %d/%d registers found", 
                    len(available_registers), len(HOLDING_REGISTERS))
        return available_registers

    async def _scan_coil_registers_enhanced(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of coil registers with detailed error tracking."""
        _LOGGER.debug("Scanning coil registers (%d total)", len(COIL_REGISTERS))
        available_registers = set()

        register_groups = self._create_register_groups_enhanced(COIL_REGISTERS)
        
        for group_info in register_groups:
            start_addr = group_info["start_addr"]
            count = group_info["count"]
            register_keys = group_info["register_keys"]
            end_addr = start_addr + count - 1
            
            _LOGGER.debug(
                "Scanning coil batch 0x%04X-0x%04X (%d registers): %s",
                start_addr, end_addr, len(register_keys), list(register_keys)
            )

            self._scan_stats["total_attempts"] += 1
            
            try:
                # pymodbus 3.5+ compatible call
                response = client.read_coils(
                    address=start_addr,
                    count=count,
                    slave=self.slave_id,
                )

                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    available_registers.update(register_keys)
                    
                    _LOGGER.debug(
                        "Coil batch 0x%04X-0x%04X succeeded: %d registers",
                        start_addr, end_addr, len(register_keys)
                    )
                else:
                    self._handle_batch_error(
                        "coil_registers", start_addr, end_addr, register_keys, 
                        f"Modbus error: {response}", client
                    )
                    
            except asyncio.TimeoutError:
                self._handle_batch_error(
                    "coil_registers", start_addr, end_addr, register_keys, 
                    "timeout", client
                )
            except Exception as exc:
                self._handle_batch_error(
                    "coil_registers", start_addr, end_addr, register_keys, 
                    str(exc), client
                )

        _LOGGER.info("Coil registers scan: %d/%d registers found", 
                    len(available_registers), len(COIL_REGISTERS))
        return available_registers

    async def _scan_discrete_inputs_enhanced(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of discrete inputs with detailed error tracking."""
        _LOGGER.debug("Scanning discrete inputs (%d total)", len(DISCRETE_INPUTS))
        available_registers = set()

        register_groups = self._create_register_groups_enhanced(DISCRETE_INPUTS)
        
        for group_info in register_groups:
            start_addr = group_info["start_addr"]
            count = group_info["count"]
            register_keys = group_info["register_keys"]
            end_addr = start_addr + count - 1
            
            _LOGGER.debug(
                "Scanning discrete input batch 0x%04X-0x%04X (%d registers): %s",
                start_addr, end_addr, len(register_keys), list(register_keys)
            )

            self._scan_stats["total_attempts"] += 1
            
            try:
                # pymodbus 3.5+ compatible call
                response = client.read_discrete_inputs(
                    address=start_addr,
                    count=count,
                    slave=self.slave_id,
                )

                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    available_registers.update(register_keys)
                    
                    _LOGGER.debug(
                        "Discrete input batch 0x%04X-0x%04X succeeded: %d registers",
                        start_addr, end_addr, len(register_keys)
                    )
                else:
                    self._handle_batch_error(
                        "discrete_inputs", start_addr, end_addr, register_keys, 
                        f"Modbus error: {response}", client
                    )
                    
            except asyncio.TimeoutError:
                self._handle_batch_error(
                    "discrete_inputs", start_addr, end_addr, register_keys, 
                    "timeout", client
                )
            except Exception as exc:
                self._handle_batch_error(
                    "discrete_inputs", start_addr, end_addr, register_keys, 
                    str(exc), client
                )

        _LOGGER.info("Discrete inputs scan: %d/%d registers found", 
                    len(available_registers), len(DISCRETE_INPUTS))
        return available_registers

    def _handle_batch_error(
        self, 
        reg_type: str, 
        start_addr: int, 
        end_addr: int, 
        register_keys: List[str], 
        reason: str,
        client: ModbusTcpClient
    ) -> None:
        """Handle batch read errors with fallback individual reads."""
        self._scan_stats["failed_reads"] += 1
        
        error_info = {
            "type": reg_type,
            "start": f"0x{start_addr:04X}",
            "end": f"0x{end_addr:04X}",
            "registers": list(register_keys),
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        
        self._scan_stats["failed_groups"].append(error_info)
        self._scan_stats["error_details"].append(error_info)
        
        _LOGGER.debug(
            "%s batch 0x%04X-0x%04X failed: %s; attempting individual reads for %d registers",
            reg_type.replace('_', ' ').title(), start_addr, end_addr, reason, len(register_keys)
        )
        
        # Attempt fallback individual reads for critical registers
        if len(register_keys) <= 5:  # Only for small batches to avoid spam
            successful_individual = self._fallback_individual_reads(
                client, register_keys, reg_type
            )
            if successful_individual:
                _LOGGER.debug(
                    "Individual fallback successful for %d registers: %s",
                    len(successful_individual), list(successful_individual)
                )

    def _fallback_individual_reads(
        self, 
        client: ModbusTcpClient, 
        register_keys: List[str], 
        reg_type: str
    ) -> Set[str]:
        """Attempt individual register reads as fallback."""
        successful = set()
        
        # Map register type to address dict and read method
        type_mapping = {
            "input_registers": (INPUT_REGISTERS, "read_input_registers"),
            "holding_registers": (HOLDING_REGISTERS, "read_holding_registers"),
            "coil_registers": (COIL_REGISTERS, "read_coils"),
            "discrete_inputs": (DISCRETE_INPUTS, "read_discrete_inputs"),
        }
        
        if reg_type not in type_mapping:
            return successful
            
        register_map, method_name = type_mapping[reg_type]
        
        for reg_key in register_keys:
            if reg_key not in register_map:
                continue
                
            address = register_map[reg_key]
            
            try:
                self._scan_stats["total_attempts"] += 1
                method = getattr(client, method_name)
                
                response = method(
                    address=address,
                    count=1,
                    slave=self.slave_id,
                )
                
                if not response.isError():
                    # Validate individual register value
                    if reg_type in ["input_registers", "holding_registers"]:
                        if self._is_valid_register_value(reg_key, response.registers[0]):
                            successful.add(reg_key)
                            self._scan_stats["successful_reads"] += 1
                    else:
                        successful.add(reg_key)
                        self._scan_stats["successful_reads"] += 1
                        
                    _LOGGER.debug("Individual read %s@0x%04X succeeded", reg_key, address)
                else:
                    self._scan_stats["failed_reads"] += 1
                    _LOGGER.debug("Individual read %s@0x%04X failed: %s", reg_key, address, response)
                    
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug("Individual read %s@0x%04X exception: %s", reg_key, address, exc)
                
        return successful

    def _validate_register_batch(
        self, 
        register_keys: List[str], 
        values: List[int], 
        reg_type: str
    ) -> Set[str]:
        """Validate register values in a batch response."""
        valid_registers = set()
        
        for i, reg_key in enumerate(register_keys):
            if i < len(values):
                value = values[i]
                if self._is_valid_register_value(reg_key, value):
                    valid_registers.add(reg_key)
                else:
                    _LOGGER.debug(
                        "Invalid value for %s register %s: 0x%04X (%d)",
                        reg_type, reg_key, value, value
                    )
                    
        return valid_registers

    def _is_valid_register_value(self, register_key: str, value: int) -> bool:
        """Enhanced validation of register values based on register type and expected ranges."""
        # Temperature sensors - check for 0x8000 (no sensor)
        if register_key in REGISTER_PROCESSING["temperature_registers"]:
            return value != REGISTER_PROCESSING["sensor_unavailable_value"]
        
        # Flow registers - check for 0xFFFF (invalid)
        if register_key in REGISTER_PROCESSING["flow_registers"]:
            return value != REGISTER_PROCESSING["invalid_flow_value"]
        
        # Percentage registers - reasonable range check
        if register_key in REGISTER_PROCESSING["percentage_registers"]:
            return 0 <= value <= 200  # Allow extended range for some parameters
        
        # Pressure registers - reasonable range check
        if register_key in REGISTER_PROCESSING["pressure_registers"]:
            return 0 <= value <= 10000  # Up to 10kPa seems reasonable
        
        # Serial number parts - should not be all zeros or all ones
        if "serial_number" in register_key:
            return value not in [0, 0xFFFF]
        
        # Firmware version - should be reasonable
        if "firmware" in register_key:
            return 0 < value < 1000
        
        # Default: accept most values except obvious invalid ones
        return value not in [0xFFFF, 0xFFFE]  # Common invalid values

    def _create_register_groups_enhanced(self, register_dict: Dict[str, int]) -> List[Dict[str, Any]]:
        """Create optimized groups of consecutive registers with enhanced metadata."""
        if not register_dict:
            return []
        
        # Sort registers by address
        sorted_registers = sorted(register_dict.items(), key=lambda x: x[1])
        groups = []
        
        current_group = {
            "start_addr": sorted_registers[0][1],
            "register_keys": [sorted_registers[0][0]],
            "addresses": [sorted_registers[0][1]],
        }
        
        for reg_name, address in sorted_registers[1:]:
            last_addr = current_group["addresses"][-1]
            gap = address - last_addr
            
            # Start new group if gap too large or group too big
            if gap > self.max_gap or len(current_group["register_keys"]) >= self.max_batch_size:
                # Finalize current group
                current_group["count"] = len(current_group["register_keys"])
                current_group["end_addr"] = current_group["addresses"][-1]
                current_group["address_range"] = (
                    current_group["start_addr"], 
                    current_group["end_addr"]
                )
                groups.append(current_group)
                
                # Start new group
                current_group = {
                    "start_addr": address,
                    "register_keys": [reg_name],
                    "addresses": [address],
                }
            else:
                # Add to current group
                current_group["register_keys"].append(reg_name)
                current_group["addresses"].append(address)
        
        # Don't forget the last group
        if current_group["register_keys"]:
            current_group["count"] = len(current_group["register_keys"])
            current_group["end_addr"] = current_group["addresses"][-1]
            current_group["address_range"] = (
                current_group["start_addr"], 
                current_group["end_addr"]
            )
            groups.append(current_group)
        
        _LOGGER.debug(
            "Created %d register groups from %d registers (max_batch=%d, max_gap=%d)",
            len(groups), len(register_dict), self.max_batch_size, self.max_gap
        )
        
        return groups

    async def _extract_device_info_enhanced(
        self, 
        client: ModbusTcpClient, 
        available_registers: Dict[str, Set[str]]
    ) -> Dict[str, Any]:
        """Extract comprehensive device information with enhanced diagnostics."""
        device_info = {
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home Serie 4",
            "firmware_version": "Unknown",
            "serial_number": "Unknown",
            "device_name": "Unknown",
            "compilation_date": "Unknown",
            "hw_version": "Unknown",
            "sw_features": [],
            "communication_info": {},
        }
        
        input_regs = available_registers.get("input_registers", set())
        holding_regs = available_registers.get("holding_registers", set())
        
        try:
            # Read firmware version
            if {"firmware_major", "firmware_minor", "firmware_patch"}.issubset(input_regs):
                try:
                    response = client.read_input_registers(
                        address=INPUT_REGISTERS["firmware_major"], 
                        count=3, 
                        slave=self.slave_id
                    )
                    if not response.isError():
                        major, minor = response.registers[0], response.registers[1]
                        # Patch is at different address, read separately
                        patch_response = client.read_input_registers(
                            address=INPUT_REGISTERS["firmware_patch"], 
                            count=1, 
                            slave=self.slave_id
                        )
                        if not patch_response.isError():
                            patch = patch_response.registers[0]
                            device_info["firmware_version"] = f"{major}.{minor}.{patch}"
                        else:
                            device_info["firmware_version"] = f"{major}.{minor}.x"
                except Exception as exc:
                    _LOGGER.debug("Failed to read firmware version: %s", exc)
            
            # Read serial number
            if {"serial_number_1", "serial_number_2", "serial_number_3"}.issubset(input_regs):
                try:
                    response = client.read_input_registers(
                        address=INPUT_REGISTERS["serial_number_1"], 
                        count=6, 
                        slave=self.slave_id
                    )
                    if not response.isError():
                        # Convert hex values to serial number string
                        serial_parts = [f"{val:04X}" for val in response.registers]
                        device_info["serial_number"] = "".join(serial_parts)
                except Exception as exc:
                    _LOGGER.debug("Failed to read serial number: %s", exc)
            
            # Read device name if available
            if {"device_name_1", "device_name_2"}.issubset(holding_regs):
                try:
                    response = client.read_holding_registers(
                        address=HOLDING_REGISTERS["device_name_1"], 
                        count=8, 
                        slave=self.slave_id
                    )
                    if not response.isError():
                        # Convert 16-bit words to ASCII string
                        name_chars = []
                        for word in response.registers:
                            if word == 0:
                                break
                            name_chars.append(chr((word >> 8) & 0xFF))
                            if (word & 0xFF) != 0:
                                name_chars.append(chr(word & 0xFF))
                        device_info["device_name"] = "".join(name_chars).strip()
                except Exception as exc:
                    _LOGGER.debug("Failed to read device name: %s", exc)
            
            # Read compilation info
            if {"compilation_days", "compilation_seconds"}.issubset(input_regs):
                try:
                    response = client.read_input_registers(
                        address=INPUT_REGISTERS["compilation_days"], 
                        count=2, 
                        slave=self.slave_id
                    )
                    if not response.isError():
                        days_since_2000 = response.registers[0]
                        seconds_since_midnight = response.registers[1]
                        
                        # Convert to actual date
                        import datetime
                        base_date = datetime.date(2000, 1, 1)
                        compile_date = base_date + datetime.timedelta(days=days_since_2000)
                        compile_time = datetime.time(
                            hour=seconds_since_midnight // 3600,
                            minute=(seconds_since_midnight % 3600) // 60,
                            second=seconds_since_midnight % 60
                        )
                        device_info["compilation_date"] = f"{compile_date} {compile_time}"
                except Exception as exc:
                    _LOGGER.debug("Failed to read compilation info: %s", exc)
            
            # Detect software features based on available registers
            sw_features = []
            if "gwc_temperature" in input_regs:
                sw_features.append("GWC System")
            if "bypass" in available_registers.get("coil_registers", set()):
                sw_features.append("Bypass Control")
            if "special_mode" in holding_regs:
                sw_features.append("Special Modes")
            if "co2_concentration" in input_regs:
                sw_features.append("CO2 Monitoring")
            if "humidity_control" in available_registers.get("coil_registers", set()):
                sw_features.append("Humidity Control")
            if "constant_flow_active" in input_regs:
                sw_features.append("Constant Flow")
            
            device_info["sw_features"] = sw_features
            
            # Communication info
            device_info["communication_info"] = {
                "modbus_tcp_port": self.port,
                "slave_id": self.slave_id,
                "host": self.host,
                "timeout": self.timeout,
                "scan_timestamp": datetime.now().isoformat(),
            }
            
        except Exception as exc:
            _LOGGER.error("Error extracting device info: %s", exc)
        
        self._scan_stats["device_info"] = device_info
        return device_info

    def _analyze_capabilities_enhanced(self, available_registers: Dict[str, Set[str]]) -> Dict[str, bool]:
        """Analyze device capabilities based on available registers with enhanced detection."""
        capabilities = {}
        
        input_regs = available_registers.get("input_registers", set())
        holding_regs = available_registers.get("holding_registers", set())
        coil_regs = available_registers.get("coil_registers", set())
        discrete_regs = available_registers.get("discrete_inputs", set())
        
        # Temperature sensors
        capabilities["sensor_outside_temperature"] = "outside_temperature" in input_regs
        capabilities["sensor_supply_temperature"] = "supply_temperature" in input_regs
        capabilities["sensor_exhaust_temperature"] = "exhaust_temperature" in input_regs
        capabilities["sensor_fpx_temperature"] = "fpx_temperature" in input_regs
        capabilities["sensor_duct_temperature"] = "duct_supply_temperature" in input_regs
        capabilities["sensor_gwc_temperature"] = "gwc_temperature" in input_regs
        capabilities["sensor_ambient_temperature"] = "ambient_temperature" in input_regs
        
        # Flow measurement
        capabilities["flow_measurement"] = any(reg in input_regs for reg in [
            "supply_flowrate", "exhaust_flowrate", "actual_flowrate"
        ])
        
        # Pressure measurement
        capabilities["pressure_measurement"] = any(reg in input_regs for reg in [
            "supply_pressure", "exhaust_pressure", "supply_pressure_pa", "exhaust_pressure_pa"
        ])
        
        # Advanced sensors
        capabilities["humidity_sensors"] = any(reg in input_regs for reg in [
            "outside_humidity", "inside_humidity"
        ])
        capabilities["air_quality_sensors"] = any(reg in input_regs for reg in [
            "co2_concentration", "voc_level", "air_quality_index"
        ])
        
        # Control systems
        capabilities["bypass_system"] = "bypass" in coil_regs or "bypass_mode" in holding_regs
        capabilities["gwc_system"] = "gwc" in coil_regs or "gwc_mode" in holding_regs
        capabilities["heating_system"] = any(reg in holding_regs for reg in [
            "heating_temperature", "heating_control"
        ])
        capabilities["cooling_system"] = any(reg in holding_regs for reg in [
            "cooling_temperature", "cooling_control"
        ])
        
        # Special functions
        capabilities["special_modes"] = "special_mode" in holding_regs
        capabilities["okap_mode"] = "okap_intensity" in holding_regs
        capabilities["kominek_mode"] = "kominek_intensity" in holding_regs
        capabilities["wietrzenie_mode"] = "wietrzenie_intensity" in holding_regs
        capabilities["pusty_dom_mode"] = "pusty_dom_intensity" in holding_regs
        
        # Flow control modes
        capabilities["constant_flow"] = "constant_flow_active" in input_regs
        capabilities["pressure_control"] = "pressure_control_mode" in holding_regs
        capabilities["variable_flow"] = any(reg in holding_regs for reg in [
            "supply_flow_min", "supply_flow_max", "flow_balance"
        ])
        
        # Schedule and automation
        capabilities["weekly_schedule"] = any(reg in holding_regs for reg in [
            "schedule_mon_period1_start", "schedule_tue_period1_start"
        ])
        capabilities["adaptive_control"] = "adaptive_control" in holding_regs
        capabilities["learning_mode"] = "learning_mode" in holding_regs
        
        # External interfaces
        capabilities["expansion_module"] = "expansion" in discrete_regs
        capabilities["fire_alarm_input"] = "fire_alarm" in discrete_regs
        capabilities["external_stop"] = "external_stop" in discrete_regs
        capabilities["window_contacts"] = "window_contact" in discrete_regs
        capabilities["presence_sensors"] = "presence_sensor" in discrete_regs
        
        # Communication and diagnostics
        capabilities["modbus_communication"] = len(available_registers) > 0  # We're here, so it works!
        capabilities["ethernet_communication"] = any(reg in holding_regs for reg in [
            "ethernet_dhcp", "ethernet_ip_1"
        ])
        capabilities["error_logging"] = any(reg in holding_regs for reg in [
            "error_status", "alarm_status"
        ])
        
        # Energy monitoring
        capabilities["energy_monitoring"] = any(reg in input_regs for reg in [
            "energy_consumption", "energy_recovery", "power_consumption"
        ])
        capabilities["efficiency_monitoring"] = any(reg in input_regs for reg in [
            "heat_recovery_efficiency", "efficiency_rating"
        ])
        
        # Maintenance features
        capabilities["filter_monitoring"] = any(reg in input_regs for reg in [
            "filter_time_remaining", "presostat_status"
        ])
        capabilities["maintenance_scheduling"] = any(reg in holding_regs for reg in [
            "maintenance_interval", "service_interval"
        ])
        
        # Store capabilities in scan stats
        self._scan_stats["capabilities_detected"] = capabilities
        
        # Count enabled capabilities
        enabled_count = sum(1 for v in capabilities.values() if v)
        total_count = len(capabilities)
        
        _LOGGER.info(
            "Device capabilities: %d/%d features detected (%.1f%%)",
            enabled_count, total_count, (enabled_count / total_count * 100)
        )
        
        return capabilities

    def _calculate_performance_metrics(self) -> None:
        """Calculate performance and efficiency metrics."""
        metrics = {}
        
        if self._scan_stats["total_attempts"] > 0:
            metrics["success_rate"] = (
                self._scan_stats["successful_reads"] / self._scan_stats["total_attempts"]
            )
            metrics["failure_rate"] = 1 - metrics["success_rate"]
            metrics["total_attempts"] = self._scan_stats["total_attempts"]
            metrics["successful_reads"] = self._scan_stats["successful_reads"]
            metrics["failed_reads"] = self._scan_stats["failed_reads"]
        
        if self._scan_stats["duration"] > 0:
            metrics["scan_duration"] = self._scan_stats["duration"]
            metrics["registers_per_second"] = (
                self._scan_stats["successful_reads"] / self._scan_stats["duration"]
            )
        
        # Calculate register type distribution
        total_registers = sum(self._scan_stats["register_counts"].values())
        if total_registers > 0:
            for reg_type, count in self._scan_stats["register_counts"].items():
                metrics[f"{reg_type}_percentage"] = (count / total_registers) * 100
        
        # Failed group analysis
        metrics["failed_groups_count"] = len(self._scan_stats["failed_groups"])
        if metrics["failed_groups_count"] > 0:
            failure_reasons = {}
            for group in self._scan_stats["failed_groups"]:
                reason = group["reason"]
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            metrics["failure_reasons"] = failure_reasons
        
        self._scan_stats["performance_metrics"] = metrics