"""Device capability scanner for ThesslaGreen Modbus."""
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
    """Scanner to detect available capabilities of ThesslaGreen device."""

    def __init__(self, host: str, port: int, slave_id: int) -> None:
        """Initialize the scanner."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.available_registers: Dict[str, Set[str]] = {}
        self.device_info: Dict[str, Any] = {}

    async def scan_device(self) -> Dict[str, Any]:
        """Scan device and return available capabilities."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._scan_device_sync
        )

    def _scan_device_sync(self) -> Dict[str, Any]:
        """Synchronous device scanning."""
        _LOGGER.info("Starting device capability scan for %s:%s slave_id=%s", 
                    self.host, self.port, self.slave_id)
        
        client = ModbusTcpClient(host=self.host, port=self.port)
        
        try:
            if not client.connect():
                raise Exception("Failed to connect to device")
            
            _LOGGER.debug("Connected to device successfully")
            
            # First, read basic device info to identify model/capabilities
            self._scan_device_info(client)
            
            # Scan each register type
            self.available_registers["input_registers"] = self._scan_input_registers(client)
            self.available_registers["holding_registers"] = self._scan_holding_registers(client)
            self.available_registers["coil_registers"] = self._scan_coil_registers(client)
            self.available_registers["discrete_inputs"] = self._scan_discrete_inputs(client)
            
            # Analyze capabilities based on available registers
            capabilities = self._analyze_capabilities()
            
            _LOGGER.info(
                "Device scan complete. Found %d input registers, %d holding registers, "
                "%d coils, %d discrete inputs",
                len(self.available_registers["input_registers"]),
                len(self.available_registers["holding_registers"]),
                len(self.available_registers["coil_registers"]),
                len(self.available_registers["discrete_inputs"])
            )
            
            return {
                "available_registers": self.available_registers,
                "device_info": self.device_info,
                "capabilities": capabilities,
            }
            
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise
        finally:
            client.close()

    def _scan_device_info(self, client: ModbusTcpClient) -> None:
        """Scan basic device information."""
        try:
            # Read firmware version (always available)
            _LOGGER.debug("Reading firmware version...")
            result = client.read_input_registers(0x0000, count=5, slave=self.slave_id)
            if not result.isError():
                major = result.registers[0]
                minor = result.registers[1]
                patch = result.registers[4] if len(result.registers) > 4 else 0
                
                self.device_info["firmware"] = f"{major}.{minor}.{patch}"
                self.device_info["firmware_major"] = major
                _LOGGER.debug("Firmware version: %s", self.device_info["firmware"])
                
                # Determine processor type based on firmware
                if major == 3:
                    self.device_info["processor"] = "ATmega128"
                elif major == 4:
                    self.device_info["processor"] = "ATmega2561"
                else:
                    self.device_info["processor"] = "Unknown"
            else:
                _LOGGER.warning("Failed to read firmware version: %s", result)
            
            # Try to read serial number
            _LOGGER.debug("Reading serial number...")
            result = client.read_input_registers(0x0018, count=6, slave=self.slave_id)
            if not result.isError():
                serial_parts = [f"{reg:04x}" for reg in result.registers]
                self.device_info["serial_number"] = f"S/N: {serial_parts[0]}{serial_parts[1]} {serial_parts[2]}{serial_parts[3]} {serial_parts[4]}{serial_parts[5]}"
                _LOGGER.debug("Serial number: %s", self.device_info["serial_number"])
            else:
                _LOGGER.debug("Serial number not available: %s", result)
            
            # Set device name based on firmware version
            if "firmware" in self.device_info:
                self.device_info["device_name"] = f"ThesslaGreen AirPack ({self.device_info['firmware']})"
            else:
                self.device_info["device_name"] = "ThesslaGreen AirPack"
            
        except Exception as exc:
            _LOGGER.warning("Failed to read device info: %s", exc)
            self.device_info["device_name"] = "ThesslaGreen AirPack"

    def _scan_input_registers(self, client: ModbusTcpClient) -> Set[str]:
        """Scan available input registers."""
        available = set()
        
        _LOGGER.debug("Scanning input registers...")
        
        for name, address in INPUT_REGISTERS.items():
            try:
                result = client.read_input_registers(address, count=1, slave=self.slave_id)
                if not result.isError():
                    value = result.registers[0]
                    if self._is_valid_register_value(name, value):
                        available.add(name)
                        _LOGGER.debug("Found input register %s (0x%04X) = %s", name, address, value)
                else:
                    _LOGGER.debug("Input register %s (0x%04X) error: %s", name, address, result)
            except Exception as exc:
                _LOGGER.debug("Exception reading input register %s: %s", name, exc)
                continue
        
        return available

    def _scan_holding_registers(self, client: ModbusTcpClient) -> Set[str]:
        """Scan available holding registers."""
        available = set()
        
        _LOGGER.debug("Scanning holding registers...")
        
        for name, address in HOLDING_REGISTERS.items():
            try:
                result = client.read_holding_registers(address, count=1, slave=self.slave_id)
                if not result.isError():
                    value = result.registers[0]
                    available.add(name)
                    _LOGGER.debug("Found holding register %s (0x%04X) = %s", name, address, value)
                else:
                    _LOGGER.debug("Holding register %s (0x%04X) error: %s", name, address, result)
            except Exception as exc:
                _LOGGER.debug("Exception reading holding register %s: %s", name, exc)
                continue
        
        return available

    def _scan_coil_registers(self, client: ModbusTcpClient) -> Set[str]:
        """Scan available coil registers."""
        available = set()
        
        if not COIL_REGISTERS:
            return available
        
        _LOGGER.debug("Scanning coil registers...")
        
        for name, address in COIL_REGISTERS.items():
            try:
                result = client.read_coils(address, count=1, slave=self.slave_id)
                if not result.isError():
                    available.add(name)
                    value = result.bits[0] if result.bits else False
                    _LOGGER.debug("Found coil %s (0x%04X) = %s", name, address, value)
                else:
                    _LOGGER.debug("Coil %s (0x%04X) error: %s", name, address, result)
            except Exception as exc:
                _LOGGER.debug("Exception reading coil %s: %s", name, exc)
                continue
        
        return available

    def _scan_discrete_inputs(self, client: ModbusTcpClient) -> Set[str]:
        """Scan available discrete input registers."""
        available = set()
        
        if not DISCRETE_INPUT_REGISTERS:
            return available
        
        _LOGGER.debug("Scanning discrete input registers...")
        
        for name, address in DISCRETE_INPUT_REGISTERS.items():
            try:
                result = client.read_discrete_inputs(address, count=1, slave=self.slave_id)
                if not result.isError():
                    available.add(name)
                    value = result.bits[0] if result.bits else False
                    _LOGGER.debug("Found discrete input %s (0x%04X) = %s", name, address, value)
                else:
                    _LOGGER.debug("Discrete input %s (0x%04X) error: %s", name, address, result)
            except Exception as exc:
                _LOGGER.debug("Exception reading discrete input %s: %s", name, exc)
                continue
        
        return available

    def _is_valid_register_value(self, register_name: str, value: int) -> bool:
        """Check if register value indicates the register is available."""
        # Temperature sensors return 0x8000 (32768) when not connected
        if "temperature" in register_name and value == INVALID_TEMPERATURE:
            return False
        
        # Air flow sensors return 0xFFFF when CF is not active
        if "air_flow" in register_name and value == INVALID_FLOW:
            return False
        
        # General check for obvious invalid values
        if value == 0xFFFF or value == 0x8000:
            return False
        
        return True

    def _analyze_capabilities(self) -> Dict[str, Any]:
        """Analyze device capabilities based on available registers."""
        capabilities = {}
        
        input_regs = self.available_registers.get("input_registers", set())
        holding_regs = self.available_registers.get("holding_registers", set())
        coil_regs = self.available_registers.get("coil_registers", set())
        discrete_regs = self.available_registers.get("discrete_inputs", set())
        
        # Basic device capabilities
        capabilities["constant_flow"] = "constant_flow_active" in input_regs
        capabilities["gwc_system"] = "gwc_mode" in holding_regs or "gwc" in coil_regs
        capabilities["bypass_system"] = "bypass_mode" in holding_regs or "bypass" in coil_regs
        capabilities["expansion_module"] = "expansion" in discrete_regs
        
        # Available sensors
        capabilities["sensor_outside_temperature"] = "outside_temperature" in input_regs
        capabilities["sensor_supply_temperature"] = "supply_temperature" in input_regs
        capabilities["sensor_exhaust_temperature"] = "exhaust_temperature" in input_regs
        capabilities["sensor_fpx_temperature"] = "fpx_temperature" in input_regs
        capabilities["sensor_ambient_temperature"] = "ambient_temperature" in input_regs
        capabilities["sensor_duct_temperature"] = "duct_temperature" in input_regs
        capabilities["sensor_gwc_temperature"] = "gwc_temperature" in input_regs
        
        # Air flow measurement
        capabilities["air_flow_measurement"] = (
            "supply_air_flow" in input_regs or
            "exhaust_air_flow" in input_regs or
            "constant_flow_active" in input_regs
        )
        
        # Control capabilities
        capabilities["manual_control"] = "air_flow_rate_manual" in holding_regs
        capabilities["temperature_control"] = "supply_air_temperature_manual" in holding_regs
        capabilities["special_functions"] = "special_mode" in holding_regs
        
        # Air quality sensors
        capabilities["contamination_sensor"] = "contamination_sensor" in discrete_regs
        capabilities["humidity_sensor"] = "airing_sensor" in discrete_regs
        
        return capabilities

    def _group_registers_by_range(self, registers: Dict[str, int], max_gap: int = 10) -> Dict[int, Dict[str, int]]:
        """Group registers by address ranges for efficient bulk reading."""
        if not registers:
            return {}
        
        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        chunks = {}
        current_chunk_start = sorted_regs[0][1]
        current_chunk = {}
        
        for name, address in sorted_regs:
            if address - current_chunk_start > max_gap and current_chunk:
                chunks[current_chunk_start] = current_chunk
                current_chunk_start = address
                current_chunk = {}
            
            current_chunk[name] = address
        
        if current_chunk:
            chunks[current_chunk_start] = current_chunk
        
        return chunks