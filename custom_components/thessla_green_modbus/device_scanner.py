"""Enhanced device capability scanner for ThesslaGreen Modbus - FIXED VERSION."""
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
        start_time = time.time()
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=10)

        try:
            if not client.connect():
                raise ConnectionError(f"Cannot connect to {self.host}:{self.port}")

            _LOGGER.info("Connected to %s:%d, scanning capabilities...", self.host, self.port)

            # Enhanced scanning strategy
            self.available_registers = {
                "input_registers": self._scan_input_registers_enhanced(client),
                "holding_registers": self._scan_holding_registers_enhanced(client),
                "coil_registers": self._scan_coil_registers_batch(client),
                "discrete_inputs": self._scan_discrete_inputs_batch(client),
            }

            # Extract device information from firmware registers
            self.device_info = self._extract_device_info(client)

            # Analyze capabilities based on available registers
            capabilities = self._analyze_capabilities_enhanced()

            self._scan_stats["scan_duration"] = time.time() - start_time
            
            _LOGGER.info(
                "Device scan completed in %.2fs: %d/%d successful reads (%.1f%% success rate)",
                self._scan_stats["scan_duration"],
                self._scan_stats["successful_reads"],
                self._scan_stats["total_attempts"],
                (self._scan_stats["successful_reads"] / self._scan_stats["total_attempts"] * 100) 
                if self._scan_stats["total_attempts"] > 0 else 0
            )

            return {
                "available_registers": self.available_registers,
                "device_info": self.device_info,
                "capabilities": capabilities,
                "scan_stats": self._scan_stats,
            }

        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise
        finally:
            client.close()

    def _scan_holding_registers_enhanced(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced holding register scanning with priority groups."""
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
            # Alternative control registers (new from documentation)
            ("alternative_control", {
                "cfg_mode1": 0x1130, "cfg_mode2": 0x1133,
                "air_flow_rate_temporary_alt": 0x1131, "supply_air_temperature_temporary_alt": 0x1134,
                "airflow_rate_change_flag": 0x1132, "temperature_change_flag": 0x1135,
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
                "airing_bathroom_coef": 0x1085, "airing_switch_coef": 0x108E,
                "open_window_coef": 0x108F,
            }),
            # Time controls
            ("time_controls", {
                "airing_panel_mode_time": 0x1089, "airing_switch_mode_time": 0x108A,
                "fireplace_mode_time": 0x108D, "airing_switch_mode_on_delay": 0x108B,
                "airing_switch_mode_off_delay": 0x108C,
            }),
            # GWC system
            ("gwc_system", {
                "gwc_off": 0x10A0, "min_gwc_air_temperature": 0x10A1,
                "max_gwc_air_temperature": 0x10A2, "gwc_regen": 0x10A6,
                "gwc_mode": 0x10A7, "gwc_regen_period": 0x10A8,
                "delta_t_gwc": 0x10AA,
            }),
            # Bypass system  
            ("bypass_system", {
                "bypass_off": 0x10E0, "min_bypass_temperature": 0x10E1,
                "air_temperature_summer_free_heating": 0x10E2,
                "air_temperature_summer_free_cooling": 0x10E3,
                "bypass_mode": 0x10EA, "bypass_user_mode": 0x10EB,
                "bypass_coef1": 0x10EC, "bypass_coef2": 0x10ED,
            }),
            # Comfort mode
            ("comfort_mode", {
                "comfort_mode_panel": 0x10D0, "comfort_mode": 0x10D1,
            }),
            # System resets
            ("system_reset", {
                "hard_reset_settings": 0x113D, "hard_reset_schedule": 0x113E,
            })
        ]
        
        # Test each group
        for group_name, registers in scan_groups:
            group_found = 0
            for name, address in registers.items():
                if self._test_register_access("holding", address, name):
                    available.add(name)
                    group_found += 1
            
            if group_found > 0:
                _LOGGER.debug("Found %d/%d registers in group %s", group_found, len(registers), group_name)
            
            # If we found critical control registers, continue with all groups
            # If not, the device might be off or misconfigured
            if group_name == "critical_control" and group_found == 0:
                _LOGGER.warning("No critical control registers found - device may be off or misconfigured")
                # Continue scanning but log warning

        return available

    def _scan_input_registers_enhanced(self, client: ModbusTcpClient) -> Set[str]:
        """Enhanced input register scanning with batched reads."""
        available = set()
        
        # Critical input registers to test first
        critical_inputs = [
            ("outside_temperature", 0x0010),
            ("supply_temperature", 0x0011),
            ("exhaust_temperature", 0x0012),
            ("firmware_major", 0x0000),
            ("firmware_minor", 0x0001),
        ]
        
        # Test critical registers individually
        for name, address in critical_inputs:
            if self._test_register_access("input", address, name):
                available.add(name)
        
        # Batch test temperature sensors (0x0010-0x0016)
        try:
            result = client.read_input_registers(0x0010, 7, slave=self.slave_id)
            self._scan_stats["total_attempts"] += 1
            
            if not result.isError():
                self._scan_stats["successful_reads"] += 1
                temp_registers = [
                    "outside_temperature", "supply_temperature", "exhaust_temperature",
                    "fpx_temperature", "duct_supply_temperature", "gwc_temperature", 
                    "ambient_temperature"
                ]
                for i, name in enumerate(temp_registers):
                    if i < len(result.registers):
                        # Check if temperature value is valid
                        raw_value = result.registers[i]
                        if raw_value != INVALID_TEMPERATURE:
                            available.add(name)
                            _LOGGER.debug("Found temperature sensor %s = %d", name, raw_value)
            else:
                self._scan_stats["failed_reads"] += 1
        except Exception as exc:
            self._scan_stats["failed_reads"] += 1
            _LOGGER.debug("Failed to batch read temperature sensors: %s", exc)
        
        # Test Constant Flow registers individually
        cf_registers = [
            ("constant_flow_active", 0x010F),
            ("supply_percentage", 0x0110),
            ("exhaust_percentage", 0x0111),
            ("supply_flowrate", 0x0112),
            ("exhaust_flowrate", 0x0113),
            ("min_percentage", 0x0114),
            ("max_percentage", 0x0115),
            ("water_removal_active", 0x012A),
        ]
        
        for name, address in cf_registers:
            if self._test_register_access("input", address, name):
                available.add(name)
        
        # Test DAC outputs
        dac_registers = [
            ("dac_supply", 0x0500),
            ("dac_exhaust", 0x0501),
            ("dac_heater", 0x0502),
            ("dac_cooler", 0x0503),
        ]
        
        for name, address in dac_registers:
            if self._test_register_access("input", address, name):
                available.add(name)
        
        # Test firmware and serial registers
        fw_serial_registers = [
            ("firmware_patch", 0x0004),
            ("compilation_days", 0x000E),
            ("compilation_seconds", 0x000F),
        ] + [(f"serial_number_{i}", 0x0018 + i - 1) for i in range(1, 7)]
        
        for name, address in fw_serial_registers:
            if self._test_register_access("input", address, name):
                available.add(name)

        return available

    def _test_register_access(self, reg_type: str, address: int, name: str) -> bool:
        """Test if a specific register is accessible."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=5)
        
        try:
            if not client.connect():
                return False
            
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
        finally:
            client.close()

    def _is_valid_register_value(self, name: str, value: int) -> bool:
        """Validate if a register value seems reasonable."""
        # Temperature sensors should not be 0x8000 (invalid)
        if "temperature" in name:
            return value != INVALID_TEMPERATURE
        
        # Flow rates should not be 65535 (invalid)
        if "flowrate" in name or "air_flow" in name:
            return value != INVALID_FLOW
        
        # Percentage values should be reasonable
        if "percentage" in name or "coef" in name:
            return 0 <= value <= 200  # Allow up to 200% for boost
        
        # Mode values should be in expected range
        if name in ["mode", "season_mode"]:
            return 0 <= value <= 2
        
        if name == "special_mode":
            return 0 <= value <= 11
        
        # Default: accept any non-zero value as valid
        return True

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
                        _LOGGER.debug("Found discrete input %s (0x%04X) = %s", name, address, result.bits[idx])
            else:
                self._scan_stats["failed_reads"] += 1
                
        except Exception as exc:
            self._scan_stats["failed_reads"] += 1
            _LOGGER.debug("Failed to read discrete inputs: %s", exc)
        
        return available

    def _extract_device_info(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Extract device information from firmware registers."""
        device_info = {
            "device_name": "ThesslaGreen AirPack",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "firmware": "Unknown",
            "serial_number": None,
        }
        
        try:
            # Read firmware version
            result = client.read_input_registers(0x0000, 5, slave=self.slave_id)
            if not result.isError() and len(result.registers) >= 3:
                major = result.registers[0]
                minor = result.registers[1] 
                patch = result.registers[4] if len(result.registers) > 4 else 0
                device_info["firmware"] = f"{major}.{minor}.{patch}"
                _LOGGER.debug("Device firmware: %s", device_info["firmware"])
        except Exception as exc:
            _LOGGER.debug("Failed to read firmware: %s", exc)
        
        try:
            # Read serial number
            result = client.read_input_registers(0x0018, 6, slave=self.slave_id)
            if not result.isError():
                # Convert serial number parts to string
                serial_parts = []
                for value in result.registers:
                    if value != 0:
                        serial_parts.append(f"{value:04X}")
                if serial_parts:
                    device_info["serial_number"] = "".join(serial_parts)
                    _LOGGER.debug("Device serial: %s", device_info["serial_number"])
        except Exception as exc:
            _LOGGER.debug("Failed to read serial number: %s", exc)
        
        return device_info

    def _analyze_capabilities_enhanced(self) -> Dict[str, Any]:
        """Enhanced capability analysis based on available registers."""
        capabilities = {
            # Basic functionality
            "basic_control": False,
            "temperature_control": False,
            "speed_control": False,
            
            # Advanced systems
            "constant_flow": False,
            "gwc_system": False,
            "bypass_system": False,
            "comfort_mode": False,
            "special_functions": False,
            
            # Hardware modules
            "expansion_module": False,
            "airs_panel": False,
            
            # Sensors
            "temperature_sensors_count": 0,
            "sensor_outside_temperature": False,
            "sensor_supply_temperature": False,
            "sensor_exhaust_temperature": False,
            "sensor_fpx_temperature": False,
            "contamination_sensor": False,
            "humidity_sensor": False,
        }
        
        holding_regs = self.available_registers.get("holding_registers", set())
        input_regs = self.available_registers.get("input_registers", set())
        coil_regs = self.available_registers.get("coil_registers", set())
        discrete_regs = self.available_registers.get("discrete_inputs", set())
        
        # Basic control capabilities
        if "on_off_panel_mode" in holding_regs and "mode" in holding_regs:
            capabilities["basic_control"] = True
        
        if "air_flow_rate_manual" in holding_regs:
            capabilities["speed_control"] = True
        
        if "supply_air_temperature_manual" in holding_regs:
            capabilities["temperature_control"] = True
        
        # System capabilities
        if "constant_flow_active" in input_regs:
            capabilities["constant_flow"] = True
        
        if "gwc_mode" in holding_regs or "gwc_off" in holding_regs:
            capabilities["gwc_system"] = True
        
        if "bypass_mode" in holding_regs or "bypass_off" in holding_regs:
            capabilities["bypass_system"] = True
        
        if "comfort_mode" in holding_regs:
            capabilities["comfort_mode"] = True
        
        if "special_mode" in holding_regs:
            capabilities["special_functions"] = True
        
        # Hardware modules
        if "expansion" in discrete_regs:
            capabilities["expansion_module"] = True
        
        if any(reg in holding_regs for reg in ["fan_speed_1_coef", "fan_speed_2_coef", "fan_speed_3_coef"]):
            capabilities["airs_panel"] = True
        
        # Sensor analysis
        temp_sensors = [
            ("outside_temperature", "sensor_outside_temperature"),
            ("supply_temperature", "sensor_supply_temperature"),
            ("exhaust_temperature", "sensor_exhaust_temperature"),
            ("fpx_temperature", "sensor_fpx_temperature"),
        ]
        
        for sensor_reg, capability_key in temp_sensors:
            if sensor_reg in input_regs:
                capabilities[capability_key] = True
                capabilities["temperature_sensors_count"] += 1
        
        if "contamination_sensor" in discrete_regs:
            capabilities["contamination_sensor"] = True
        
        if "airing_sensor" in discrete_regs:
            capabilities["humidity_sensor"] = True
        
        return capabilities