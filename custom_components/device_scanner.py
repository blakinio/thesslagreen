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
        _LOGGER.info("Starting device capability scan...")
        
        client = ModbusTcpClient(host=self.host, port=self.port)
        
        try:
            if not client.connect():
                raise Exception("Failed to connect to device")
            
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
            result = client.read_input_registers(0x0000, 5, slave=self.slave_id)
            if not result.isError():
                major = result.registers[0]
                minor = result.registers[1]
                patch = result.registers[4] if len(result.registers) > 4 else 0
                
                self.device_info["firmware"] = f"{major}.{minor}.{patch}"
                self.device_info["firmware_major"] = major
                
                # Determine processor type based on firmware
                if major == 3:
                    self.device_info["processor"] = "ATmega128"
                elif major == 4:
                    self.device_info["processor"] = "ATmega2561"
                else:
                    self.device_info["processor"] = "Unknown"
            
            # Try to read serial number
            result = client.read_input_registers(0x0018, 6, slave=self.slave_id)
            if not result.isError():
                serial_parts = [f"{reg:04x}" for reg in result.registers]
                self.device_info["serial_number"] = f"S/N: {serial_parts[0]}{serial_parts[1]} {serial_parts[2]}{serial_parts[3]} {serial_parts[4]}{serial_parts[5]}"
            
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
        
        for name, address in INPUT_REGISTERS.items():
            try:
                result = client.read_input_registers(address, 1, slave=self.slave_id)
                if not result.isError():
                    # Check if register returns valid data (not 0xFFFF or error values)
                    value = result.registers[0]
                    if self._is_valid_register_value(name, value):
                        available.add(name)
                        _LOGGER.debug("Found input register %s (0x%04X) = %s", name, address, value)
            except Exception:
                continue
        
        return available

    def _scan_holding_registers(self, client: ModbusTcpClient) -> Set[str]:
        """Scan available holding registers."""
        available = set()
        
        for name, address in HOLDING_REGISTERS.items():
            try:
                result = client.read_holding_registers(address, 1, slave=self.slave_id)
                if not result.isError():
                    value = result.registers[0]
                    available.add(name)
                    _LOGGER.debug("Found holding register %s (0x%04X) = %s", name, address, value)
            except Exception:
                continue
        
        return available

    def _scan_coil_registers(self, client: ModbusTcpClient) -> Set[str]:
        """Scan available coil registers."""
        available = set()
        
        if not COIL_REGISTERS:
            return available
        
        for name, address in COIL_REGISTERS.items():
            try:
                result = client.read_coils(address, 1, slave=self.slave_id)
                if not result.isError():
                    available.add(name)
                    _LOGGER.debug("Found coil %s (0x%04X) = %s", name, address, result.bits[0] if result.bits else False)
            except Exception:
                continue
        
        return available

    def _scan_discrete_inputs(self, client: ModbusTcpClient) -> Set[str]:
        """Scan available discrete input registers."""
        available = set()
        
        if not DISCRETE_INPUT_REGISTERS:
            return available
        
        for name, address in DISCRETE_INPUT_REGISTERS.items():
            try:
                result = client.read_discrete_inputs(address, 1, slave=self.slave_id)
                if not result.isError():
                    available.add(name)
                    _LOGGER.debug("Found discrete input %s (0x%04X) = %s", name, address, result.bits[0] if result.bits else False)
            except Exception:
                continue
        
        return available

    def _is_valid_register_value(self, register_name: str, value: int) -> bool:
        """Check if register value indicates the register is available."""
        # Some registers return specific values when not available
        if value == 0xFFFF or value == 65535:
            # Temperature sensors return 0x8000 (32768) when not connected
            if "temperature" in register_name and value == 32768:
                return False
            # Air flow sensors return 65535 when CF is not active
            if "air_flow" in register_name and value == 65535:
                return False
        
        return True

    def _analyze_capabilities(self) -> Dict[str, bool]:
        """Analyze device capabilities based on available registers."""
        capabilities = {}
        
        # Check for major system capabilities
        capabilities["constant_flow"] = "constant_flow_active" in self.available_registers.get("input_registers", set())
        capabilities["gwc_system"] = "gwc_mode" in self.available_registers.get("holding_registers", set())
        capabilities["bypass_system"] = "bypass_mode" in self.available_registers.get("holding_registers", set())
        capabilities["comfort_mode"] = "comfort_temperature_winter" in self.available_registers.get("holding_registers", set())
        capabilities["expansion_module"] = "expansion" in self.available_registers.get("discrete_inputs", set())
        capabilities["cf_module"] = "cf_version" in self.available_registers.get("holding_registers", set())
        
        # Check for temperature sensors
        temp_sensors = ["outside_temperature", "supply_temperature", "exhaust_temperature", 
                       "fpx_temperature", "duct_supply_temperature", "gwc_temperature", "ambient_temperature"]
        for sensor in temp_sensors:
            capabilities[f"sensor_{sensor}"] = sensor in self.available_registers.get("input_registers", set())
        
        # Check for special functions
        special_functions = ["hood_supply_coef", "fireplace_supply_coef", "airing_coef", 
                           "contamination_coef", "empty_house_coef"]
        for func in special_functions:
            capabilities[f"function_{func.replace('_coef', '')}"] = func in self.available_registers.get("holding_registers", set())
        
        # Check for control outputs
        outputs = ["power_supply_fans", "heating_cable", "gwc", "hood", "bypass"]
        for output in outputs:
            capabilities[f"output_{output}"] = output in self.available_registers.get("coil_registers", set())
        
        # Check for inputs
        inputs = ["contamination_sensor", "airing_sensor", "fireplace", "empty_house"]
        for input_reg in inputs:
            capabilities[f"input_{input_reg}"] = input_reg in self.available_registers.get("discrete_inputs", set())
        
        # Check for heating/cooling systems
        capabilities["heating_system"] = "heating_enable" in self.available_registers.get("holding_registers", set())
        capabilities["cooling_system"] = "cooling_enable" in self.available_registers.get("holding_registers", set())
        
        # Check for advanced features
        capabilities["airs_system"] = "airs_enable" in self.available_registers.get("holding_registers", set())
        capabilities["modbus_config"] = "modbus_address" in self.available_registers.get("holding_registers", set())
        
        return capabilities