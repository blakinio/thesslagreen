"""Device scanner for ThesslaGreen Modbus integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Set

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ConnectionException

_LOGGER = logging.getLogger(__name__)

DEFAULT_SLAVE_ID = 10
SOCKET_TIMEOUT = 6.0

@dataclass
class DeviceInfo:
    model: str = "Unknown AirPack"
    firmware: str = "Unknown"
    serial_number: str = "Unknown"

@dataclass
class DeviceCapabilities:
    basic_control: bool = False
    temperature_sensors: set = None
    flow_sensors: set = None
    special_functions: set = None
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

    def __post_init__(self):
        # Avoid None in sets
        if self.temperature_sensors is None:
            self.temperature_sensors = set()
        if self.flow_sensors is None:
            self.flow_sensors = set()
        if self.special_functions is None:
            self.special_functions = set()

    def as_dict(self) -> Dict:
        return asdict(self)


class ThesslaGreenDeviceScanner:
    """Device scanner for ThesslaGreen AirPack Home - compatible with pymodbus 3.5.*+"""

    def __init__(self, host: str, port: int, slave_id: int = DEFAULT_SLAVE_ID, timeout: int = 10, retry: int = 3) -> None:
        """Initialize device scanner with consistent parameter names."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        
        # Available registers storage
        self.available_registers: Dict[str, Set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

    async def _read_input(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[int]]:
        """Read input registers."""
        try:
            response = await client.read_input_registers(address, count, slave=self.slave_id)
            if not response.isError():
                return response.registers
        except Exception as e:
            _LOGGER.debug("Failed to read input 0x%04X: %s", address, e)
        return None

    async def _read_holding(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[int]]:
        """Read holding registers."""
        try:
            response = await client.read_holding_registers(address, count, slave=self.slave_id)
            if not response.isError():
                return response.registers
        except Exception as e:
            _LOGGER.debug("Failed to read holding 0x%04X: %s", address, e)
        return None

    async def _read_coil(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[bool]]:
        """Read coil registers."""
        try:
            response = await client.read_coils(address, count, slave=self.slave_id)
            if not response.isError():
                return response.bits[:count]
        except Exception as e:
            _LOGGER.debug("Failed to read coil 0x%04X: %s", address, e)
        return None

    async def _read_discrete(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[bool]]:
        """Read discrete input registers."""
        try:
            response = await client.read_discrete_inputs(address, count, slave=self.slave_id)
            if not response.isError():
                return response.bits[:count]
        except Exception as e:
            _LOGGER.debug("Failed to read discrete 0x%04X: %s", address, e)
        return None

    def _is_valid_register_value(self, register_name: str, value: int) -> bool:
        """Check if register value is valid (not a sensor error/missing value)."""
        # Temperature sensors use 0x8000 to indicate no sensor
        if "temperature" in register_name.lower():
            return value != 0x8000 and value != 32768
        
        # Air flow sensors use 0x8000 to indicate no sensor
        if any(x in register_name.lower() for x in ["flow", "air_flow", "flowrate"]):
            return value != 0x8000 and value != 32768 and value != 65535
        
        # Mode values should be in valid range
        if "mode" in register_name.lower():
            return 0 <= value <= 4
        
        # Default: consider valid
        return True

    def _analyze_capabilities(self) -> Dict[str, bool]:
        """Analyze available registers to determine device capabilities."""
        caps = {}
        
        # Check for constant flow control
        caps["constant_flow"] = any(
            "constant_flow" in reg or "cf_" in reg 
            for reg in self.available_registers["input_registers"]
        )
        
        # Check for GWC system
        caps["gwc_system"] = any(
            "gwc" in reg.lower() 
            for registers in self.available_registers.values() 
            for reg in registers
        )
        
        # Check for bypass system
        caps["bypass_system"] = any(
            "bypass" in reg.lower() 
            for registers in self.available_registers.values() 
            for reg in registers
        )
        
        # Check for expansion module
        caps["expansion_module"] = "expansion" in self.available_registers["discrete_inputs"]
        
        # Check for heating/cooling
        caps["heating_system"] = any(
            "heating" in reg.lower() or "heater" in reg.lower()
            for registers in self.available_registers.values() 
            for reg in registers
        )
        
        caps["cooling_system"] = any(
            "cooling" in reg.lower() or "cooler" in reg.lower()
            for registers in self.available_registers.values() 
            for reg in registers
        )
        
        # Check for temperature sensors
        temp_sensors = [
            "outside_temperature", "supply_temperature", "exhaust_temperature",
            "fpx_temperature", "duct_supply_temperature", "gwc_temperature",
            "ambient_temperature", "heating_temperature"
        ]
        
        for sensor in temp_sensors:
            caps[f"sensor_{sensor}"] = sensor in self.available_registers["input_registers"]
        
        # Check for air quality sensors
        caps["air_quality"] = any(
            sensor in self.available_registers["input_registers"]
            for sensor in ["co2_level", "voc_level", "pm25_level", "air_quality_index"]
        )
        
        # Check for weekly schedule
        caps["weekly_schedule"] = any(
            "schedule" in reg.lower() or "weekly" in reg.lower()
            for registers in self.available_registers.values() 
            for reg in registers
        )
        
        # Basic control is always available if we can read mode
        caps["basic_control"] = "mode" in self.available_registers["holding_registers"]
        
        return caps

    def _group_registers_by_range(self, registers: Dict[str, int], max_gap: int = 10) -> Dict[int, List[str]]:
        """Group registers by address ranges for optimized batch reading."""
        if not registers:
            return {}
        
        # Sort by address
        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        
        chunks = {}
        current_chunk_start = None
        current_chunk = []
        
        for name, addr in sorted_regs:
            if current_chunk_start is None:
                current_chunk_start = addr
                current_chunk = [name]
            elif addr - (current_chunk_start + len(current_chunk) - 1) <= max_gap:
                current_chunk.append(name)
            else:
                chunks[current_chunk_start] = current_chunk
                current_chunk_start = addr
                current_chunk = [name]
        
        if current_chunk:
            chunks[current_chunk_start] = current_chunk
        
        return chunks

    async def scan(self) -> Tuple[DeviceInfo, DeviceCapabilities, Dict[str, Tuple[int, int]]]:
        """Scan device and return device info, capabilities and present blocks."""
        client = AsyncModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            _LOGGER.debug("Connecting to ThesslaGreen device at %s:%s", self.host, self.port)
            connected = await client.connect()
            if not connected:
                raise ConnectionException(f"Failed to connect to {self.host}:{self.port}")
            
            _LOGGER.debug("Connected successfully, starting device scan")
            
            info = DeviceInfo()
            caps = DeviceCapabilities()
            present_blocks = {}
            
            # Read firmware version
            fw_data = await self._read_input(client, 0x0000, 5)
            if fw_data and len(fw_data) >= 3:
                fw = f"{fw_data[0]}.{fw_data[1]}.{fw_data[2]}"
                info.firmware = fw
                _LOGGER.debug("Firmware version: %s", fw)
            
            # Determine model based on firmware features
            model = "AirPack Home Serie 4"
            if fw_data and fw_data[0] >= 4:
                if fw_data[1] >= 85:
                    model = "AirPack⁴ Energy++"
                else:
                    model = "AirPack⁴ Energy+"
            info.model = model
            
            # Scan temperature sensors (0x0010-0x0017)
            temp_sensors = [
                (0x0010, "outside_temperature"),
                (0x0011, "supply_temperature"),
                (0x0012, "exhaust_temperature"),
                (0x0013, "fpx_temperature"),
                (0x0014, "duct_supply_temperature"),
                (0x0015, "gwc_temperature"),
                (0x0016, "ambient_temperature"),
                (0x0017, "heating_temperature"),
            ]
            
            for addr, reg_name in temp_sensors:
                val = await self._read_input(client, addr, 1)
                if val is not None and self._is_valid_register_value(reg_name, val[0]):
                    caps.temperature_sensors.add(reg_name)
                    setattr(caps, f"sensor_{reg_name}", True)
                    caps.temperature_sensors_count += 1
                    self.available_registers["input_registers"].add(reg_name)
            
            if caps.temperature_sensors_count > 0:
                present_blocks["temperature"] = (0x0010, 0x0017)
            
            # Scan flow sensors (0x0018-0x001E)
            flow_sensors = [
                (0x0018, "supply_flowrate"),
                (0x0019, "exhaust_flowrate"),
                (0x001A, "outdoor_flowrate"),
                (0x001B, "inside_flowrate"),
                (0x001C, "gwc_flowrate"),
                (0x001D, "heat_recovery_flowrate"),
                (0x001E, "bypass_flowrate"),
            ]
            
            for addr, reg_name in flow_sensors:
                val = await self._read_input(client, addr, 1)
                if val is not None and self._is_valid_register_value(reg_name, val[0]):
                    caps.flow_sensors.add(reg_name)
                    self.available_registers["input_registers"].add(reg_name)
            
            if len(caps.flow_sensors) > 0:
                present_blocks["flow"] = (0x0018, 0x001E)
            
            # Scan control registers
            control_registers = [
                (0x0000, "mode"),
                (0x0001, "on_off_panel_mode"),
                (0x0002, "manual_override"),
                (0x0012, "gwc_mode"),
                (0x0014, "bypass_mode"),
                (0x0016, "cooling_mode"),
                (0x0020, "constant_flow_mode"),
            ]
            
            for addr, reg_name in control_registers:
                val = await self._read_holding(client, addr, 1)
                if val is not None and self._is_valid_register_value(reg_name, val[0]):
                    if "constant_flow" in reg_name:
                        caps.constant_flow = True
                    elif "gwc" in reg_name:
                        caps.gwc_system = True
                    elif "bypass" in reg_name:
                        caps.bypass_system = True
                    elif "cooling" in reg_name:
                        caps.cooling_system = True
                        
                    self.available_registers["holding_registers"].add(reg_name)
            
            if len(self.available_registers["holding_registers"]) > 0:
                present_blocks["control"] = (0x0000, 0x0020)
            
            # Scan coil registers
            coil_registers = [
                (0x0000, "power_supply_fans"),
                (0x0001, "power_exhaust_fans"),
                (0x0002, "gwc_enabled"),
                (0x0003, "bypass_enabled"),
                (0x0004, "heating_enabled"),
                (0x0005, "cooling_enabled"),
            ]
            
            for addr, reg_name in coil_registers:
                val = await self._read_coil(client, addr, 1)
                if val is not None:
                    if "heating" in reg_name and val[0]:
                        caps.heating_system = True
                    elif "cooling" in reg_name and val[0]:
                        caps.cooling_system = True
                        
                    self.available_registers["coil_registers"].add(reg_name)
            
            if len(self.available_registers["coil_registers"]) > 0:
                present_blocks["coil"] = (0x0000, 0x0005)
            
            # Scan discrete inputs
            discrete_registers = [
                (0x0000, "expansion"),
                (0x0005, "contamination_sensor"),
                (0x0007, "airing_switch"),
                (0x000E, "fireplace"),
            ]
            
            for addr, reg_name in discrete_registers:
                val = await self._read_discrete(client, addr, 1)
                if val is not None:
                    if "expansion" in reg_name and val[0]:
                        caps.expansion_module = True
                    elif "contamination_sensor" in reg_name:
                        caps.air_quality = True
                    elif reg_name in ["fireplace", "airing_switch"]:
                        caps.special_functions.add(reg_name)
                        
                    self.available_registers["discrete_inputs"].add(reg_name)
            
            if len(self.available_registers["discrete_inputs"]) > 0:
                present_blocks["discrete"] = (0x0000, 0x000F)
            
            _LOGGER.info(
                "Device scan completed: %d blocks found, %d capabilities detected",
                len(present_blocks),
                sum(1 for v in caps.as_dict().values() if bool(v) and not isinstance(v, (set, int))),
            )
            
            return info, caps, present_blocks
            
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise
        finally:
            try:
                await client.close()
            except Exception:
                pass
            _LOGGER.debug("Disconnected from ThesslaGreen device")

    async def scan_device(self) -> Dict[str, any]:
        """Scan device and return formatted result - compatible with coordinator."""
        try:
            info, caps, blocks = await self.scan()
            
            # Count total available registers
            register_count = sum(len(regs) for regs in self.available_registers.values())
            
            result = {
                "device_info": {
                    "device_name": f"ThesslaGreen {info.model}",
                    "model": info.model,
                    "firmware": info.firmware,
                    "serial_number": info.serial_number,
                },
                "capabilities": caps.as_dict(),
                "available_registers": self.available_registers,
                "register_count": register_count,
                "scan_blocks": blocks,
            }
            
            _LOGGER.info(
                "Device scan successful: %s v%s, %d registers, %d capabilities",
                info.model, info.firmware, register_count,
                sum(1 for v in caps.as_dict().values() if bool(v) and not isinstance(v, (set, int)))
            )
            
            return result
            
        except ConnectionException as exc:
            _LOGGER.error("Connection failed during device scan: %s", exc)
            raise Exception("Failed to connect to device") from exc
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise Exception(f"Device scan failed: {exc}") from exc
    
    async def close(self):
        """Close the scanner connection if any."""
        # Nothing to close in scanner itself
        pass

    def _analyze_capabilities_enhanced(self) -> Dict[str, bool]:
        """Enhanced capability analysis for optimization tests."""
        return self._analyze_capabilities()

    def _group_registers_for_batch_read(self, addresses: List[int], max_gap: int = 10) -> List[Tuple[int, int]]:
        """Group registers for batch reading optimization."""
        if not addresses:
            return []
            
        groups = []
        current_start = addresses[0]
        current_end = addresses[0]
        
        for addr in addresses[1:]:
            if addr - current_end <= max_gap and current_end - current_start + 1 < 16:
                current_end = addr
            else:
                groups.append((current_start, current_end - current_start + 1))
                current_start = addr
                current_end = addr
                
        groups.append((current_start, current_end - current_start + 1))
        return groups


# Legacy compatibility - ThesslaDeviceScanner alias
ThesslaDeviceScanner = ThesslaGreenDeviceScanner