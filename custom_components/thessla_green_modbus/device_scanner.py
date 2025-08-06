"""Enhanced device scanner for ThesslaGreen Modbus integration - HA 2025.7+ & pymodbus 3.5+ Compatible."""
from __future__ import annotations

import asyncio
import logging
import time
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
    """Enhanced device scanner for ThesslaGreen devices - HA 2025.7+ & pymodbus 3.5+ Compatible."""

    def __init__(self, host: str, port: int, slave_id: int, timeout: int = 10) -> None:
        """Initialize the enhanced device scanner."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        
        # Enhanced scanning statistics
        self._scan_stats = {
            "total_attempts": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "scan_duration": 0.0,
            "failed_groups": [],
        }
        
        _LOGGER.debug("Initialized device scanner for %s:%s (slave_id=%s)", host, port, slave_id)

    async def scan_device(self) -> Dict[str, Any]:
        """Perform enhanced device capability scan - pymodbus 3.5+ Compatible."""
        _LOGGER.info("Connected to %s:%s, starting enhanced capability scan...", self.host, self.port)
        
        # Reset scan statistics
        self._scan_stats = {
            "total_attempts": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "scan_duration": 0.0,
            "failed_groups": [],
        }
        
        asyncio.get_running_loop()
        scan_start_time = time.monotonic()
        
        try:
            # Perform scanning in a background thread to avoid blocking
            result = await asyncio.to_thread(self._perform_device_scan)

            scan_duration = time.monotonic() - scan_start_time
            self._scan_stats["scan_duration"] = scan_duration

            success_rate = (
                (self._scan_stats["successful_reads"] / max(1, self._scan_stats["total_attempts"])) * 100
            )
            self._scan_stats["success_rate"] = success_rate
            
            _LOGGER.info(
                "Enhanced scan completed: %d registers found (%.1f%% success rate), %d capabilities detected",
                sum(len(regs) for regs in result["available_registers"].values()),
                success_rate,
                len([k for k, v in result["capabilities"].items() if v])
            )
            
            return result
            
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise

    def _perform_device_scan(self) -> Dict[str, Any]:
        """Perform the actual device scan synchronously - pymodbus 3.5+ Compatible."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            if not client.connect():
                raise Exception("Failed to connect to device")
            
            _LOGGER.debug("Connected to Modbus device, scanning registers...")
            
            # Scan different register types
            available_registers = {
                "input_registers": self._scan_input_registers_batch(client),
                "holding_registers": self._scan_holding_registers_batch(client),
                "coil_registers": self._scan_coil_registers_batch(client),
                "discrete_inputs": self._scan_discrete_inputs_batch(client),
            }
            
            # Extract device information
            device_info = self._extract_device_info(client, available_registers)
            
            # Analyze capabilities
            capabilities = self._analyze_capabilities(available_registers)
            
            return {
                "available_registers": available_registers,
                "device_info": device_info,
                "capabilities": capabilities,
                "scan_statistics": self._scan_stats,
            }
            
        finally:
            client.close()

    def _scan_input_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of input registers - pymodbus 3.5+ Compatible."""
        available_registers = set()

        register_groups = self._create_register_groups(INPUT_REGISTERS)

        for start_addr, count, register_keys in register_groups:
            end_addr = start_addr + count - 1
            _LOGGER.debug(
                "Scanning input register batch %s-%s containing %s",
                start_addr,
                end_addr,
                register_keys,
            )

            self._scan_stats["total_attempts"] += 1
            try:
                response = client.read_input_registers(
                    address=start_addr,
                    count=count,
                    slave=self.slave_id,
                )

                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    available_registers.update(register_keys)
                    _LOGGER.debug(
                        "Input register batch %s-%s succeeded: %d registers",
                        start_addr,
                        end_addr,
                        len(register_keys),
                    )
                else:
                    self._scan_stats["failed_reads"] += 1
                    reason = f"Modbus error: {response}"
                    self._scan_stats["failed_groups"].append(
                        {
                            "type": "input_registers",
                            "start": start_addr,
                            "end": end_addr,
                            "registers": list(register_keys),
                            "reason": reason,
                        }
                    )
                    _LOGGER.debug(
                        "Input register batch %s-%s failed: %s; discarded %s",
                        start_addr,
                        end_addr,
                        reason,
                        register_keys,
                    )
                    available_registers.update(
                        self._fallback_read_registers(
                            client,
                            register_keys,
                            INPUT_REGISTERS,
                            "read_input_registers",
                            "Input",
                        )
                    )
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                reason = (
                    "timeout"
                    if isinstance(exc, (asyncio.TimeoutError, TimeoutError))
                    else str(exc)
                )
                self._scan_stats["failed_groups"].append(
                    {
                        "type": "input_registers",
                        "start": start_addr,
                        "end": end_addr,
                        "registers": list(register_keys),
                        "reason": reason,
                    }
                )
                _LOGGER.debug(
                    "Input register batch %s-%s failed: %s; discarded %s",
                    start_addr,
                    end_addr,
                    reason,
                    register_keys,
                )
                available_registers.update(
                    self._fallback_read_registers(
                        client,
                        register_keys,
                        INPUT_REGISTERS,
                        "read_input_registers",
                        "Input",
                    )
                )

        _LOGGER.info(
            "Input registers scan: %d registers found", len(available_registers)
        )
        return available_registers
    def _scan_holding_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of holding registers - pymodbus 3.5+ Compatible."""
        available_registers = set()

        register_groups = self._create_register_groups(HOLDING_REGISTERS)

        for start_addr, count, register_keys in register_groups:
            end_addr = start_addr + count - 1
            _LOGGER.debug(
                "Scanning holding register batch %s-%s containing %s",
                start_addr,
                end_addr,
                register_keys,
            )

            self._scan_stats["total_attempts"] += 1
            try:
                response = client.read_holding_registers(
                    address=start_addr,
                    count=count,
                    slave=self.slave_id,
                )

                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    available_registers.update(register_keys)
                    _LOGGER.debug(
                        "Holding register batch %s-%s succeeded: %d registers",
                        start_addr,
                        end_addr,
                        len(register_keys),
                    )
                else:
                    self._scan_stats["failed_reads"] += 1
                    reason = f"Modbus error: {response}"
                    self._scan_stats["failed_groups"].append(
                        {
                            "type": "holding_registers",
                            "start": start_addr,
                            "end": end_addr,
                            "registers": list(register_keys),
                            "reason": reason,
                        }
                    )
                    _LOGGER.debug(
                        "Holding register batch %s-%s failed: %s; discarded %s",
                        start_addr,
                        end_addr,
                        reason,
                        register_keys,
                    )
                    available_registers.update(
                        self._fallback_read_registers(
                            client,
                            register_keys,
                            HOLDING_REGISTERS,
                            "read_holding_registers",
                            "Holding",
                        )
                    )
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                reason = (
                    "timeout"
                    if isinstance(exc, (asyncio.TimeoutError, TimeoutError))
                    else str(exc)
                )
                self._scan_stats["failed_groups"].append(
                    {
                        "type": "holding_registers",
                        "start": start_addr,
                        "end": end_addr,
                        "registers": list(register_keys),
                        "reason": reason,
                    }
                )
                _LOGGER.debug(
                    "Holding register batch %s-%s failed: %s; discarded %s",
                    start_addr,
                    end_addr,
                    reason,
                    register_keys,
                )
                available_registers.update(
                    self._fallback_read_registers(
                        client,
                        register_keys,
                        HOLDING_REGISTERS,
                        "read_holding_registers",
                        "Holding",
                    )
                )

        _LOGGER.info(
            "Holding registers scan: %d registers found", len(available_registers)
        )
        return available_registers
    def _scan_coil_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of coil registers - pymodbus 3.5+ Compatible."""
        available_registers = set()

        register_groups = self._create_register_groups(COIL_REGISTERS)

        for start_addr, count, register_keys in register_groups:
            end_addr = start_addr + count - 1
            _LOGGER.debug(
                "Scanning coil register batch %s-%s containing %s",
                start_addr,
                end_addr,
                register_keys,
            )

            self._scan_stats["total_attempts"] += 1
            try:
                response = client.read_coils(
                    address=start_addr,
                    count=count,
                    slave=self.slave_id,
                )

                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    available_registers.update(register_keys)
                    _LOGGER.debug(
                        "Coil register batch %s-%s succeeded: %d registers",
                        start_addr,
                        end_addr,
                        len(register_keys),
                    )
                else:
                    self._scan_stats["failed_reads"] += 1
                    reason = f"Modbus error: {response}"
                    self._scan_stats["failed_groups"].append(
                        {
                            "type": "coil_registers",
                            "start": start_addr,
                            "end": end_addr,
                            "registers": list(register_keys),
                            "reason": reason,
                        }
                    )
                    _LOGGER.debug(
                        "Coil register batch %s-%s failed: %s; discarded %s",
                        start_addr,
                        end_addr,
                        reason,
                        register_keys,
                    )
                    available_registers.update(
                        self._fallback_read_registers(
                            client,
                            register_keys,
                            COIL_REGISTERS,
                            "read_coils",
                            "Coil",
                        )
                    )
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                reason = (
                    "timeout"
                    if isinstance(exc, (asyncio.TimeoutError, TimeoutError))
                    else str(exc)
                )
                self._scan_stats["failed_groups"].append(
                    {
                        "type": "coil_registers",
                        "start": start_addr,
                        "end": end_addr,
                        "registers": list(register_keys),
                        "reason": reason,
                    }
                )
                _LOGGER.debug(
                    "Coil register batch %s-%s failed: %s; discarded %s",
                    start_addr,
                    end_addr,
                    reason,
                    register_keys,
                )
                available_registers.update(
                    self._fallback_read_registers(
                        client,
                        register_keys,
                        COIL_REGISTERS,
                        "read_coils",
                        "Coil",
                    )
                )

        _LOGGER.info(
            "Coil registers scan: %d registers found", len(available_registers)
        )
        return available_registers
    def _scan_discrete_inputs_batch(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced batch scanning of discrete inputs - pymodbus 3.5+ Compatible."""
        available_registers = set()

        register_groups = self._create_register_groups(DISCRETE_INPUTS)

        for start_addr, count, register_keys in register_groups:
            end_addr = start_addr + count - 1
            _LOGGER.debug(
                "Scanning discrete input batch %s-%s containing %s",
                start_addr,
                end_addr,
                register_keys,
            )

            self._scan_stats["total_attempts"] += 1
            try:
                response = client.read_discrete_inputs(
                    address=start_addr,
                    count=count,
                    slave=self.slave_id,
                )

                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    available_registers.update(register_keys)
                    _LOGGER.debug(
                        "Discrete input batch %s-%s succeeded: %d registers",
                        start_addr,
                        end_addr,
                        len(register_keys),
                    )
                else:
                    self._scan_stats["failed_reads"] += 1
                    reason = f"Modbus error: {response}"
                    self._scan_stats["failed_groups"].append(
                        {
                            "type": "discrete_inputs",
                            "start": start_addr,
                            "end": end_addr,
                            "registers": list(register_keys),
                            "reason": reason,
                        }
                    )
                    _LOGGER.debug(
                        "Discrete input batch %s-%s failed: %s; discarded %s",
                        start_addr,
                        end_addr,
                        reason,
                        register_keys,
                    )
                    available_registers.update(
                        self._fallback_read_registers(
                            client,
                            register_keys,
                            DISCRETE_INPUTS,
                            "read_discrete_inputs",
                            "Discrete input",
                        )
                    )
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                reason = (
                    "timeout"
                    if isinstance(exc, (asyncio.TimeoutError, TimeoutError))
                    else str(exc)
                )
                self._scan_stats["failed_groups"].append(
                    {
                        "type": "discrete_inputs",
                        "start": start_addr,
                        "end": end_addr,
                        "registers": list(register_keys),
                        "reason": reason,
                    }
                )
                _LOGGER.debug(
                    "Discrete input batch %s-%s failed: %s; discarded %s",
                    start_addr,
                    end_addr,
                    reason,
                    register_keys,
                )
                available_registers.update(
                    self._fallback_read_registers(
                        client,
                        register_keys,
                        DISCRETE_INPUTS,
                        "read_discrete_inputs",
                        "Discrete input",
                    )
                )

        _LOGGER.info(
            "Discrete inputs scan: %d registers found", len(available_registers)
        )
        return available_registers
    def _fallback_read_registers(
        self,
        client: ModbusTcpClient,
        register_keys: list,
        register_map: Dict[str, int],
        method: str,
        reg_type: str,
    ) -> Set[str]:
        """Attempt to read each register individually when a batch read fails."""
        successful = set()
        for reg in register_keys:
            address = register_map.get(reg)
            if address is None:
                continue
            try:
                self._scan_stats["total_attempts"] += 1
                response = getattr(client, method)(
                    address=address,
                    count=1,
                    slave=self.slave_id,
                )
                if not response.isError():
                    self._scan_stats["successful_reads"] += 1
                    successful.add(reg)
                    _LOGGER.debug(
                        "%s register %s (%s) fallback succeeded",
                        reg_type,
                        reg,
                        address,
                    )
                else:
                    self._scan_stats["failed_reads"] += 1
                    _LOGGER.debug(
                        "%s register %s (%s) fallback failed: %s",
                        reg_type,
                        reg,
                        address,
                        response,
                    )
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug(
                    "%s register %s (%s) fallback failed: %s",
                    reg_type,
                    reg,
                    address,
                    exc,
                )
        return successful

    def _create_register_groups(self, register_dict: Dict[str, int]) -> list:
        """Create groups of consecutive registers for batch reading."""
        if not register_dict:
            return []
        
        # Sort registers by address
        sorted_regs = sorted(register_dict.items(), key=lambda x: x[1])
        groups = []
        
        if not sorted_regs:
            return groups
        
        # Group consecutive registers for batch reading (max 10 per batch for reliability)
        current_group = [sorted_regs[0]]
        
        for reg_name, reg_addr in sorted_regs[1:]:
            last_addr = current_group[-1][1]
            
            if reg_addr == last_addr + 1 and len(current_group) < 10:
                # Consecutive address, add to current group
                current_group.append((reg_name, reg_addr))
            else:
                # Non-consecutive or group too large, finalize current group
                if current_group:
                    groups.append(self._finalize_register_group(current_group))
                current_group = [(reg_name, reg_addr)]
        
        # Don't forget the last group
        if current_group:
            groups.append(self._finalize_register_group(current_group))
        
        return groups

    def _finalize_register_group(self, group: list) -> tuple:
        """Convert register group to (start_addr, count, register_keys) format."""
        start_addr = group[0][1]
        end_addr = group[-1][1]
        count = end_addr - start_addr + 1
        register_keys = [reg_name for reg_name, _ in group]
        
        return (start_addr, count, register_keys)

    def _extract_device_info(self, client: ModbusTcpClient, available_registers: Dict[str, Set[str]]) -> Dict[str, Any]:
        """Extract device information from Modbus registers - pymodbus 3.5+ Compatible."""
        device_info = {
            "device_name": f"ThesslaGreen AirPack ({self.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "firmware": "Unknown",
            "serial_number": None,
        }
        
        holding_regs = available_registers.get("holding_registers", set())
        
        # Try to read firmware version if available
        if "firmware_version" in holding_regs and "firmware_version" in HOLDING_REGISTERS:
            try:
                fw_addr = HOLDING_REGISTERS["firmware_version"]
                # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                response = client.read_holding_registers(
                    address=fw_addr, 
                    count=2, 
                    slave=self.slave_id
                )
                
                if not response.isError() and len(response.registers) >= 2:
                    major = response.registers[0]
                    minor = response.registers[1]
                    device_info["firmware"] = f"{major}.{minor}"
                    _LOGGER.debug("Detected firmware version: %s", device_info["firmware"])
                    
            except Exception as exc:
                _LOGGER.debug("Could not read firmware version: %s", exc)
        
        # Try to read serial number if available  
        if "device_serial" in holding_regs and "device_serial" in HOLDING_REGISTERS:
            try:
                serial_addr = HOLDING_REGISTERS["device_serial"]
                # ✅ FIXED: pymodbus 3.5+ requires keyword arguments
                response = client.read_holding_registers(
                    address=serial_addr, 
                    count=4, 
                    slave=self.slave_id
                )
                
                if not response.isError() and len(response.registers) >= 4:
                    # Convert registers to serial number string
                    serial_parts = []
                    for reg in response.registers:
                        if reg != 0:
                            serial_parts.append(f"{reg:04d}")
                    
                    if serial_parts:
                        device_info["serial_number"] = "".join(serial_parts)
                        _LOGGER.debug("Detected serial number: %s", device_info["serial_number"])
                        
            except Exception as exc:
                _LOGGER.debug("Could not read serial number: %s", exc)
        
        _LOGGER.debug("Device info extracted: %s", device_info)
        return device_info

    def _analyze_capabilities(self, available_registers: Dict[str, Set[str]]) -> Dict[str, bool]:
        """Analyze device capabilities based on available registers."""
        capabilities = {
            "basic_control": False,
            "intensity_control": False,
            "temperature_control": False,
            "special_functions": False,
            "gwc_support": False,
            "bypass_support": False,
            "constant_flow": False,
            "comfort_mode": False,
            "advanced_configuration": False,
        }
        
        holding_regs = available_registers.get("holding_registers", set())
        input_regs = available_registers.get("input_registers", set())
        coil_regs = available_registers.get("coil_registers", set())
        
        # Basic control capability
        if "mode" in holding_regs:
            capabilities["basic_control"] = True
        
        # Intensity control capability
        intensity_regs = [
            "air_flow_rate_manual", "air_flow_rate_auto", "air_flow_rate_temporary"
        ]
        if any(reg in holding_regs for reg in intensity_regs):
            capabilities["intensity_control"] = True
        
        # Temperature control capability
        temp_control_regs = [
            "supply_temperature_manual", "comfort_temperature_heating", "comfort_temperature_cooling"
        ]
        if any(reg in holding_regs for reg in temp_control_regs):
            capabilities["temperature_control"] = True
        
        # Special functions capability
        if "special_mode" in holding_regs:
            capabilities["special_functions"] = True
        
        # GWC (Ground Heat Exchanger) support
        gwc_regs = [
            "gwc_active", "gwc_mode", "gwc_delta_temp_summer", "gwc_delta_temp_winter"
        ]
        if any(reg in holding_regs or reg in coil_regs for reg in gwc_regs):
            capabilities["gwc_support"] = True
        
        # Bypass support
        bypass_regs = ["bypass_active", "bypass_mode"]
        if any(reg in holding_regs or reg in coil_regs for reg in bypass_regs):
            capabilities["bypass_support"] = True
        
        # Constant flow support
        cf_regs = [
            "constant_flow_active", "constant_flow_supply_target", "constant_flow_exhaust_target"
        ]
        if any(reg in holding_regs or reg in coil_regs for reg in cf_regs):
            capabilities["constant_flow"] = True
        
        # Comfort mode support
        comfort_regs = ["comfort_active", "comfort_mode"]
        if any(reg in holding_regs or reg in coil_regs for reg in comfort_regs):
            capabilities["comfort_mode"] = True
        
        # Advanced configuration capability
        advanced_regs = [
            "filter_change_interval", "filter_warning_threshold", "gwc_regeneration_mode"
        ]
        if any(reg in holding_regs for reg in advanced_regs):
            capabilities["advanced_configuration"] = True
        
        detected_caps = [cap for cap, available in capabilities.items() if available]
        _LOGGER.info("Capability analysis: %d capabilities detected", len(detected_caps))
        _LOGGER.debug("Detected capabilities: %s", detected_caps)
        
        return capabilities

    def _is_valid_register_value(self, register_key: str, value: int) -> bool:
        """Validate if a register value is reasonable."""
        try:
            # Temperature sensors (typically -500 to 1000, representing -50.0°C to 100.0°C)
            if "temperature" in register_key:
                return -500 <= value <= 1000
            
            # Flow values (0 to 1000 m³/h)
            elif "flow" in register_key and "rate" in register_key:
                return 0 <= value <= 1000
            
            # Percentage values (0 to 100%)
            elif "percentage" in register_key or "efficiency" in register_key:
                return 0 <= value <= 100
            
            # Mode values (reasonable range)
            elif register_key in ["mode", "special_mode", "comfort_mode", "gwc_mode"]:
                return 0 <= value <= 20
            
            # Error and warning codes
            elif "error" in register_key or "warning" in register_key:
                return 0 <= value <= 50
            
            # Time values in minutes
            elif "time" in register_key:
                return 0 <= value <= 10080  # Up to 1 week
            
            # General integer values
            else:
                return 0 <= value <= 65535  # Valid 16-bit unsigned range
                
        except (ValueError, TypeError):
            return False
