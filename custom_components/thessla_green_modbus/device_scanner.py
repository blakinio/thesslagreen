"""Device scanner for ThesslaGreen Modbus integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Set

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ConnectionException

_LOGGER = logging.getLogger(__name__)

DEFAULT_UNIT = 1
SOCKET_TIMEOUT = 6.0

@dataclass
class DeviceInfo:
    model: str = "Unknown AirPack"
    firmware: str = "Unknown"

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
        # unikaj None w setach
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

    def __init__(self, host: str, port: int, unit: int = DEFAULT_UNIT, timeout: int = 10) -> None:
        self._host = host
        self._port = port
        self._unit = unit
        self._timeout = timeout
        
        # For compatibility with tests
        self.host = host
        self.port = port
        self.slave_id = unit
        
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
            rr = await client.read_input_registers(address=address, count=count, unit=self._unit)
            if rr.isError():  # type: ignore[attr-defined]
                _LOGGER.debug("Input reg error @0x%04X: %s", address, rr)
                return None
            return rr.registers  # type: ignore[attr-defined]
        except Exception as e:
            _LOGGER.debug("Exception input @0x%04X: %s", address, e)
            return None

    async def _read_holding(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[int]]:
        """Read holding registers."""
        try:
            rr = await client.read_holding_registers(address=address, count=count, unit=self._unit)
            if rr.isError():  # type: ignore[attr-defined]
                _LOGGER.debug("Holding reg error @0x%04X: %s", address, rr)
                return None
            return rr.registers  # type: ignore[attr-defined]
        except Exception as e:
            _LOGGER.debug("Exception holding @0x%04X: %s", address, e)
            return None

    async def _read_coils(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[bool]]:
        """Read coil registers."""
        try:
            rr = await client.read_coils(address=address, count=count, unit=self._unit)
            if rr.isError():  # type: ignore[attr-defined]
                _LOGGER.debug("Coils error @0x%04X: %s", address, rr)
                return None
            return rr.bits  # type: ignore[attr-defined]
        except Exception as e:
            _LOGGER.debug("Exception coils @0x%04X: %s", address, e)
            return None

    async def _read_discrete(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[bool]]:
        """Read discrete input registers."""
        try:
            rr = await client.read_discrete_inputs(address=address, count=count, unit=self._unit)
            if rr.isError():  # type: ignore[attr-defined]
                _LOGGER.debug("Discrete error @0x%04X: %s", address, rr)
                return None
            return rr.bits  # type: ignore[attr-defined]
        except Exception as e:
            _LOGGER.debug("Exception discrete @0x%04X: %s", address, e)
            return None

    def _is_valid_register_value(self, register_name: str, value: int) -> bool:
        """Validate register values to filter out invalid/disconnected sensors."""
        if value is None:
            return False
            
        # Temperature sensor validation (common invalid values)
        if "temperature" in register_name.lower():
            # Common invalid temperature values indicating disconnected sensor
            invalid_temp_values = [32768, 65535, 0x8000, 0xFFFF, -32768]
            if value in invalid_temp_values:
                return False
            # Reasonable temperature range check (-40°C to +85°C for sensor range)
            if value < -800 or value > 1700:  # considering 0.1°C multiplier from documentation
                return False
                
        # Flow sensor validation  
        if "flow" in register_name.lower() or "flowrate" in register_name.lower():
            # Invalid flow values
            if value == 65535 or value == 0x8000 or value == 0xFFFF:
                return False
            if value < 0 or value > 10000:  # reasonable range 0-10000 m³/h
                return False
                
        # Air quality sensor validation
        if register_name in ["co2_level", "pm1_level", "pm25_level", "pm10_level", "voc_level"]:
            if value == 65535 or value == 0x8000 or value == 0xFFFF:
                return False
            if value < 0:
                return False
                
        # Humidity validation (0-100%)
        if "humidity" in register_name.lower():
            if value == 65535 or value == 0x8000 or value == 0xFFFF:
                return False
            if value < 0 or value > 1000:  # 0-100% with 0.1% resolution
                return False
                
        # Percentage validation (for flow rates, etc.)
        if "percentage" in register_name.lower():
            if value < 0 or value > 1000:  # 0-100% with 0.1% resolution
                return False
                
        # Mode validation
        if register_name in ["mode", "cfgMode1", "cfgMode2"]:
            # Valid modes: 0=auto, 1=manual, 2=temporary
            if value not in [0, 1, 2]:
                return False
                
        # Season mode validation 
        if register_name == "season_mode":
            # Valid season modes: 0=auto, 1=summer, 2=winter
            if value not in [0, 1, 2]:
                return False
                
        # Special mode validation
        if register_name == "special_mode":
            # Valid special modes: 0=none, 1=okap, 2=party, 3=fireplace, 4=vacation, etc.
            if value < 0 or value > 10:
                return False
                
        # Intensity validation (for special functions)
        if "intensity" in register_name.lower():
            if value < 0 or value > 100:
                return False
                
        # Duration validation (in minutes)
        if "duration" in register_name.lower():
            if value < 0 or value > 1440:  # max 24 hours
                return False
                
        return True

    def _analyze_capabilities(self) -> Dict[str, bool]:
        """Analyze device capabilities based on available registers."""
        capabilities = {
            "basic_control": False,
            "constant_flow": False,
            "gwc_system": False,
            "bypass_system": False,
            "expansion_module": False,
            "sensor_outside_temperature": False,
            "sensor_supply_temperature": False,
            "sensor_exhaust_temperature": False,
            "sensor_fpx_temperature": False,
            "sensor_duct_supply_temperature": False,
            "sensor_gwc_temperature": False,
            "sensor_ambient_temperature": False,
            "sensor_heating_temperature": False,
            "heating_system": False,
            "cooling_system": False,
            "air_quality": False,
            "weekly_schedule": False,
            "special_functions": False,
            "temperature_sensors_count": 0,
        }
        
        input_regs = self.available_registers.get("input_registers", set())
        holding_regs = self.available_registers.get("holding_registers", set())
        coil_regs = self.available_registers.get("coil_registers", set())
        discrete_regs = self.available_registers.get("discrete_inputs", set())
        
        # Basic control - check for core control registers
        if any(reg in holding_regs for reg in ["mode", "cfgMode1", "on_off_panel_mode", "air_flow_rate_manual"]):
            capabilities["basic_control"] = True
            
        # Temperature sensors
        temp_sensors = 0
        for sensor in ["outside_temperature", "supply_temperature", "exhaust_temperature", 
                      "fpx_temperature", "duct_supply_temperature", "gwc_temperature", 
                      "ambient_temperature", "heating_temperature"]:
            if sensor in input_regs:
                capabilities[f"sensor_{sensor}"] = True
                temp_sensors += 1
        capabilities["temperature_sensors_count"] = temp_sensors
            
        # Flow sensors and control
        if "constant_flow_active" in holding_regs or "constant_flow_active" in input_regs:
            capabilities["constant_flow"] = True
            
        # GWC system - check for GWC-related registers
        if any(reg in holding_regs for reg in ["gwc_mode", "gwc_switch_temperature"]) or "gwc" in coil_regs:
            capabilities["gwc_system"] = True
            
        # Bypass system - check for bypass-related registers
        if "bypass_mode" in holding_regs or "bypass" in coil_regs or "bypass_flowrate" in input_regs:
            capabilities["bypass_system"] = True
            
        # Expansion module
        if "expansion" in discrete_regs:
            capabilities["expansion_module"] = True
            
        # Heating system - check for heating controls and sensors
        if any(reg in holding_regs for reg in ["heating_mode", "comfort_temperature", "heating_sensor_correction"]) or \
           any(reg in coil_regs for reg in ["heating_cable", "duct_water_heater_pump"]):
            capabilities["heating_system"] = True
            
        # Cooling system  
        if any(reg in holding_regs for reg in ["cooling_mode", "cooling_temp_max", "cooling_temp_min", "night_cooling_minimum"]):
            capabilities["cooling_system"] = True
            
        # Air quality sensors
        if any(reg in input_regs for reg in ["co2_level", "humidity_indoor", "pm1_level", "pm25_level", "pm10_level", "voc_level"]) or \
           "contamination_sensor" in discrete_regs:
            capabilities["air_quality"] = True
            
        # Special functions - check for special mode controls
        if any(reg in holding_regs for reg in ["special_mode", "okap_intensity", "party_intensity", "fireplace_intensity", "vacation_mode"]) or \
           any(reg in discrete_regs for reg in ["hood", "fireplace", "empty_house", "airing_switch"]):
            capabilities["special_functions"] = True
            
        # Weekly schedule (if any schedule-related registers are found)
        # Note: This would need to be expanded when schedule registers are documented
        if any("schedule" in reg or "weekly" in reg for reg in holding_regs):
            capabilities["weekly_schedule"] = True
            
        return capabilities

    def _group_registers_by_range(self, registers: Dict[str, int], max_gap: int = 10) -> Dict[int, List[str]]:
        """Group registers by address ranges for efficient batch reading."""
        if not registers:
            return {}
            
        # Sort registers by address
        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        
        chunks = {}
        current_start = None
        current_regs = []
        
        for reg_name, address in sorted_regs:
            if current_start is None:
                current_start = address
                current_regs = [reg_name]
            elif address - current_start <= max_gap and len(current_regs) < 16:
                current_regs.append(reg_name)
            else:
                # Save current chunk
                chunks[current_start] = current_regs
                # Start new chunk
                current_start = address
                current_regs = [reg_name]
                
        # Add last chunk
        if current_start is not None:
            chunks[current_start] = current_regs
            
        return chunks

    async def scan(self) -> Tuple[DeviceInfo, DeviceCapabilities, Dict[str, Tuple[int, int]]]:
        """Full device scan - compatible with config_flow."""
        _LOGGER.info("Starting comprehensive device scan for %s:%s", self._host, self._port)

        client = AsyncModbusTcpClient(self._host, port=self._port, timeout=SOCKET_TIMEOUT)
        try:
            await client.connect()
            if not client.connected:
                raise ConnectionError("Unable to connect")

            _LOGGER.info("Connected to ThesslaGreen device at %s:%s", self._host, self._port)

            caps = DeviceCapabilities()
            present_blocks: Dict[str, Tuple[int, int]] = {}

            # Basic device info - INPUT 0x0000..0x0016
            _LOGGER.debug("Scanning input registers...")
            ver_major = await self._read_input(client, 0x0000, 1)
            ver_minor = await self._read_input(client, 0x0001, 1)
            ver_patch = await self._read_input(client, 0x0004, 1)
            model = "AirPack Home"
            fw = "Unknown"
            if ver_major and ver_minor and ver_patch:
                try:
                    fw = f"{ver_major[0]}.{ver_minor[0]}.{ver_patch[0]}"
                except Exception:
                    pass

            # Comprehensive register scanning based on MODBUS documentation
            
            # Temperature sensors (0x0010-0x0017) - all possible temperature points
            temp_registers = [
                (0x0010, "outside_temperature"),
                (0x0011, "supply_temperature"), 
                (0x0012, "exhaust_temperature"),
                (0x0013, "fpx_temperature"),
                (0x0014, "duct_supply_temperature"),
                (0x0015, "gwc_temperature"),
                (0x0016, "ambient_temperature"),
                (0x0017, "heating_temperature"),
            ]
            
            for addr, reg_name in temp_registers:
                temp_val = await self._read_input(client, addr, 1)
                if temp_val is not None and self._is_valid_register_value(reg_name, temp_val[0]):
                    if "outside" in reg_name:
                        caps.sensor_outside_temperature = True
                    elif "supply" in reg_name:
                        caps.sensor_supply_temperature = True  
                    elif "exhaust" in reg_name:
                        caps.sensor_exhaust_temperature = True
                    elif "fpx" in reg_name:
                        caps.sensor_fpx_temperature = True
                    elif "duct_supply" in reg_name:
                        caps.sensor_duct_supply_temperature = True
                    elif "gwc" in reg_name:
                        caps.sensor_gwc_temperature = True
                    elif "ambient" in reg_name:
                        caps.sensor_ambient_temperature = True
                    elif "heating" in reg_name:
                        caps.sensor_heating_temperature = True
                        
                    caps.temperature_sensors.add(reg_name.replace("_temperature", ""))
                    self.available_registers["input_registers"].add(reg_name)
            
            # Flow sensors (0x0018-0x001E)
            flow_registers = [
                (0x0018, "supply_flowrate"),
                (0x0019, "exhaust_flowrate"),
                (0x001A, "outdoor_flowrate"),
                (0x001B, "inside_flowrate"),
                (0x001C, "gwc_flowrate"),
                (0x001D, "heat_recovery_flowrate"),
                (0x001E, "bypass_flowrate"),
            ]
            
            for addr, reg_name in flow_registers:
                flow_val = await self._read_input(client, addr, 1)
                if flow_val is not None and self._is_valid_register_value(reg_name, flow_val[0]):
                    caps.flow_sensors.add(reg_name.replace("_flowrate", ""))
                    self.available_registers["input_registers"].add(reg_name)
                    
            # Air quality sensors (0x0020-0x0027)  
            air_quality_registers = [
                (0x0020, "co2_level"),
                (0x0021, "humidity_indoor"),
                (0x0022, "humidity_outdoor"),
                (0x0023, "pm1_level"),
                (0x0024, "pm25_level"),
                (0x0025, "pm10_level"),
                (0x0026, "voc_level"),
                (0x0027, "air_quality_index"),
            ]
            
            for addr, reg_name in air_quality_registers:
                aq_val = await self._read_input(client, addr, 1)
                if aq_val is not None and self._is_valid_register_value(reg_name, aq_val[0]):
                    caps.air_quality = True
                    self.available_registers["input_registers"].add(reg_name)
                    
            caps.temperature_sensors_count = len(caps.temperature_sensors)
            if caps.temperature_sensors_count > 0:
                present_blocks["input_temps"] = (0x0010, 0x0017)
            if len(caps.flow_sensors) > 0:
                present_blocks["input_flows"] = (0x0018, 0x001E)
            if caps.air_quality:
                present_blocks["input_air_quality"] = (0x0020, 0x0027)

            # HOLDING REGISTERS - control and configuration (0x1070+)
            _LOGGER.debug("Scanning holding registers...")
            
            # Core control registers (0x1070-0x1080)
            core_holding = [
                (0x1070, "mode"),
                (0x1071, "on_off_panel_mode"), 
                (0x1072, "air_flow_rate_manual"),
                (0x1073, "supply_percentage"),
                (0x1074, "exhaust_percentage"),
                (0x1075, "season_mode"),
                (0x1076, "special_mode"),
                (0x1077, "comfort_temperature"),
                (0x1078, "eco_temperature"),
                (0x1079, "anti_freeze_hysteresis"),
                (0x107A, "heating_sensor_correction"),
                (0x107B, "cooling_temp_max"),
                (0x107C, "cooling_temp_min"),
                (0x107D, "gwc_switch_temperature"),
                (0x107E, "air_flow_minimum"),
                (0x107F, "air_flow_boost"),
                (0x1080, "night_cooling_minimum"),
            ]
            
            for addr, reg_name in core_holding:
                val = await self._read_holding(client, addr, 1)
                if val is not None:
                    caps.basic_control = True
                    self.available_registers["holding_registers"].add(reg_name)
                    
            # Special function registers (0x1081-0x1100)
            special_holding = [
                (0x1081, "okap_intensity"),
                (0x1082, "okap_duration"),
                (0x1083, "party_intensity"),
                (0x1084, "party_duration"),
                (0x1085, "fireplace_intensity"),
                (0x1086, "fireplace_duration"),
                (0x1087, "supply_reduction"),
                (0x1088, "vacation_mode"),
                (0x1089, "balance_mode"),
                (0x108A, "air_flow_correction"),
                (0x108B, "temperature_correction"),
                (0x108C, "gwc_mode"),
                (0x108D, "bypass_mode"),
                (0x108E, "constant_flow_active"),
                (0x108F, "heating_mode"),
                (0x1090, "cooling_mode"),
            ]
            
            for addr, reg_name in special_holding:
                val = await self._read_holding(client, addr, 1)
                if val is not None:
                    if "constant_flow" in reg_name:
                        caps.constant_flow = True
                    elif "gwc" in reg_name:
                        caps.gwc_system = True
                    elif "bypass" in reg_name:
                        caps.bypass_system = True
                    elif "heating" in reg_name:
                        caps.heating_system = True
                    elif "cooling" in reg_name:
                        caps.cooling_system = True
                    elif reg_name in ["okap_intensity", "party_intensity", "fireplace_intensity"]:
                        caps.special_functions.add(reg_name.split("_")[0])
                        
                    self.available_registers["holding_registers"].add(reg_name)
                    
            if caps.basic_control:
                present_blocks["holding_core"] = (0x1070, 0x1100)

            # COIL REGISTERS - output controls (0x0005-0x000F)
            _LOGGER.debug("Scanning coil registers...")
            
            coil_registers = [
                (0x0005, "duct_water_heater_pump"),
                (0x0009, "bypass"),
                (0x000A, "info"),
                (0x000B, "power_supply_fans"),
                (0x000C, "heating_cable"),
                (0x000D, "work_permit"),
                (0x000E, "gwc"),
                (0x000F, "hood"),
            ]
            
            for addr, reg_name in coil_registers:
                val = await self._read_coils(client, addr, 1)
                if val is not None:
                    if "bypass" in reg_name:
                        caps.bypass_system = True
                    elif "gwc" in reg_name:
                        caps.gwc_system = True
                    elif "heating" in reg_name:
                        caps.heating_system = True
                    elif "power_supply_fans" in reg_name:
                        caps.basic_control = True
                        
                    self.available_registers["coil_registers"].add(reg_name)
                    
            if len(self.available_registers["coil_registers"]) > 0:
                present_blocks["coils"] = (0x0005, 0x000F)

            # DISCRETE INPUTS - digital inputs and sensor states (0x0000-0x0015)
            _LOGGER.debug("Scanning discrete input registers...")
            
            discrete_registers = [
                (0x0000, "duct_heater_protection"),
                (0x0001, "expansion"),
                (0x0003, "dp_duct_filter_overflow"),
                (0x0004, "hood"),
                (0x0005, "contamination_sensor"),
                (0x0006, "airing_sensor"),
                (0x0007, "airing_switch"),
                (0x000A, "airing_mini"),
                (0x000B, "fan_speed_3"),
                (0x000C, "fan_speed_2"),
                (0x000D, "fan_speed_1"),
                (0x000E, "fireplace"),
                (0x000F, "ppoz"),
                (0x0012, "dp_ahu_filter_overflow"),
                (0x0013, "ahu_filter_protection"),
                (0x0015, "empty_house"),
            ]
            
            for addr, reg_name in discrete_registers:
                val = await self._read_discrete(client, addr, 1)
                if val is not None:
                    if "expansion" in reg_name and val[0]:
                        caps.expansion_module = True
                    elif "contamination_sensor" in reg_name:
                        caps.air_quality = True
                    elif reg_name in ["hood", "fireplace", "empty_house", "airing_switch"]:
                        caps.special_functions.add(reg_name)
                        
                    self.available_registers["discrete_inputs"].add(reg_name)
                    
            if len(self.available_registers["discrete_inputs"]) > 0:
                present_blocks["discrete"] = (0x0000, 0x0015)

            info = DeviceInfo(model=model, firmware=fw)

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