"""Enhanced coordinator for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Set

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COIL_REGISTERS,
    DISCRETE_INPUTS,
    DOMAIN,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    REGISTER_GROUPS,
)

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator):
    """Enhanced coordinator for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        scan_interval: int,
        timeout: int,
        retry: int,
        available_registers: Dict[str, Set[str]],
    ) -> None:
        """Initialize the enhanced coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        self.available_registers = available_registers
        
        # Enhanced optimization features (HA 2025.7+)
        self._consecutive_groups: Dict[str, list] = {}
        self._failed_registers: Set[str] = set()
        self._last_successful_read: Dict[str, float] = {}
        self._read_cache: Dict[str, Any] = {}
        self._batch_read_enabled = True
        
        # Performance metrics
        self._read_stats = {
            "total_reads": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "average_read_time": 0.0,
            "last_update_time": 0.0,
        }
        
        # Pre-compute consecutive register groups for batch reading
        self._initialize_register_groups()
        
        _LOGGER.info(
            "Enhanced coordinator initialized: %s:%s (slave_id=%s, interval=%ss, timeout=%ss)",
            host, port, slave_id, scan_interval, timeout
        )

    def _initialize_register_groups(self) -> None:
        """Pre-compute consecutive register groups for optimized batch reading."""
        for reg_type in ["input_registers", "holding_registers", "coil_registers", "discrete_inputs"]:
            available = self.available_registers.get(reg_type, set())
            if not available:
                continue
                
            register_map = {
                "input_registers": INPUT_REGISTERS,
                "holding_registers": HOLDING_REGISTERS,
                "coil_registers": COIL_REGISTERS,
                "discrete_inputs": DISCRETE_INPUTS,
            }[reg_type]
            
            # Get addresses for available registers
            addresses = {key: addr for key, addr in register_map.items() if key in available}
            self._consecutive_groups[reg_type] = self._create_consecutive_groups(addresses)
            
        total_groups = sum(len(groups) for groups in self._consecutive_groups.values())
        _LOGGER.debug("Created %d optimized register groups for batch reading", total_groups)

    def _create_consecutive_groups(self, registers: Dict[str, int]) -> list:
        """Create consecutive register groups for batch reading (max 125 registers per group)."""
        if not registers:
            return []
            
        # Sort by address
        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        groups = []
        current_group_start = None
        current_group_keys = []
        current_group_start_addr = None
        
        for key, addr in sorted_regs:
            if current_group_start is None:
                # Start new group
                current_group_start = key
                current_group_start_addr = addr
                current_group_keys = [key]
            elif (addr == current_group_start_addr + len(current_group_keys) and 
                  len(current_group_keys) < 125):  # pymodbus limit
                # Continue current group
                current_group_keys.append(key)
            else:
                # Finish current group and start new one
                if current_group_keys:
                    groups.append((
                        current_group_start_addr,
                        len(current_group_keys),
                        {key: i for i, key in enumerate(current_group_keys)}
                    ))
                current_group_start = key
                current_group_start_addr = addr
                current_group_keys = [key]
        
        # Add the last group
        if current_group_keys:
            groups.append((
                current_group_start_addr,
                len(current_group_keys),
                {key: i for i, key in enumerate(current_group_keys)}
            ))
            
        return groups

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from ThesslaGreen with enhanced optimization."""
        import time
        start_time = time.time()
        
        try:
            data = await self.hass.async_add_executor_job(self._fetch_modbus_data)
            
            # Update performance metrics
            read_time = time.time() - start_time
            self._read_stats["total_reads"] += 1
            self._read_stats["successful_reads"] += 1
            self._read_stats["last_update_time"] = read_time
            
            # Calculate rolling average
            current_avg = self._read_stats["average_read_time"]
            self._read_stats["average_read_time"] = (current_avg * 0.9) + (read_time * 0.1)
            
            _LOGGER.debug(
                "Data update completed in %.2fs (avg: %.2fs, success rate: %.1f%%)",
                read_time,
                self._read_stats["average_read_time"],
                (self._read_stats["successful_reads"] / self._read_stats["total_reads"]) * 100
            )
            
            return data
            
        except Exception as exc:
            self._read_stats["total_reads"] += 1
            self._read_stats["failed_reads"] += 1
            _LOGGER.error("Enhanced coordinator update failed: %s", exc)
            raise UpdateFailed(f"Error communicating with device: {exc}")

    def _fetch_modbus_data(self) -> Dict[str, Any]:
        """Enhanced Modbus data fetching with batch optimization."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        data = {}
        
        try:
            if not client.connect():
                raise UpdateFailed("Failed to connect to Modbus device")
            
            # Enhanced batch reading for each register type (HA 2025.7+)
            register_readers = {
                "input_registers": self._read_input_registers_batch,
                "holding_registers": self._read_holding_registers_batch,
                "coil_registers": self._read_coil_registers_batch,
                "discrete_inputs": self._read_discrete_inputs_batch,
            }
            
            for reg_type, reader_func in register_readers.items():
                if reg_type in self._consecutive_groups:
                    try:
                        reg_data = reader_func(client)
                        data.update(reg_data)
                    except Exception as exc:
                        _LOGGER.warning("Failed to read %s: %s", reg_type, exc)
                        # Continue with other register types
                        continue
            
            # Post-process data with enhanced validation
            data = self._post_process_data(data)
            
        finally:
            client.close()
            
        return data

    def _read_input_registers_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of input registers."""
        data = {}
        groups = self._consecutive_groups.get("input_registers", [])
        
        for start_addr, count, key_map in groups:
            try:
                response = client.read_input_registers(start_addr, count, slave=self.slave_id)
                if response.isError():
                    _LOGGER.debug("Error reading input registers at %s: %s", start_addr, response)
                    continue
                    
                # Process each register in the batch
                for key, offset in key_map.items():
                    raw_value = response.registers[offset]
                    processed_value = self._process_register_value(key, raw_value)
                    if processed_value is not None:
                        data[key] = processed_value
                        
            except Exception as exc:
                _LOGGER.debug("Failed to read input register batch at %s: %s", start_addr, exc)
                continue
                
        return data

    def _read_holding_registers_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of holding registers."""
        data = {}
        groups = self._consecutive_groups.get("holding_registers", [])
        
        for start_addr, count, key_map in groups:
            try:
                response = client.read_holding_registers(start_addr, count, slave=self.slave_id)
                if response.isError():
                    _LOGGER.debug("Error reading holding registers at %s: %s", start_addr, response)
                    continue
                    
                for key, offset in key_map.items():
                    raw_value = response.registers[offset]
                    processed_value = self._process_register_value(key, raw_value)
                    if processed_value is not None:
                        data[key] = processed_value
                        
            except Exception as exc:
                _LOGGER.debug("Failed to read holding register batch at %s: %s", start_addr, exc)
                continue
                
        return data

    def _read_coil_registers_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of coil registers."""
        data = {}
        groups = self._consecutive_groups.get("coil_registers", [])
        
        for start_addr, count, key_map in groups:
            try:
                response = client.read_coils(start_addr, count, slave=self.slave_id)
                if response.isError():
                    _LOGGER.debug("Error reading coils at %s: %s", start_addr, response)
                    continue
                    
                for key, offset in key_map.items():
                    bit_value = response.bits[offset]
                    data[key] = bool(bit_value)
                    
            except Exception as exc:
                _LOGGER.debug("Failed to read coil batch at %s: %s", start_addr, exc)
                continue
                
        return data

    def _read_discrete_inputs_batch(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Enhanced batch reading of discrete inputs."""
        data = {}
        groups = self._consecutive_groups.get("discrete_inputs", [])
        
        for start_addr, count, key_map in groups:
            try:
                response = client.read_discrete_inputs(start_addr, count, slave=self.slave_id)
                if response.isError():
                    _LOGGER.debug("Error reading discrete inputs at %s: %s", start_addr, response)
                    continue
                    
                for key, offset in key_map.items():
                    bit_value = response.bits[offset]
                    data[key] = bool(bit_value)
                    
            except Exception as exc:
                _LOGGER.debug("Failed to read discrete input batch at %s: %s", start_addr, exc)
                continue
                
        return data

    def _process_register_value(self, key: str, raw_value: int) -> Any:
        """Enhanced register value processing with better validation."""
        # Handle invalid sensor readings (typical 0x8000 for disconnected sensors)
        if raw_value == 0x8000 or raw_value == 0xFFFF:
            return None
            
        # Temperature registers (0.5°C resolution, signed)
        temperature_regs = [
            "outside_temperature", "supply_temperature", "exhaust_temperature",
            "fpx_temperature", "duct_supply_temperature", "gwc_temperature", "ambient_temperature",
            "supply_temperature_manual", "supply_temperature_temporary", 
            "comfort_temperature_heating", "comfort_temperature_cooling",
            "min_bypass_temperature", "air_temperature_summer_free_heating",
            "air_temperature_summer_free_cooling", "min_gwc_air_temperature",
            "max_gwc_air_temperature", "delta_t_gwc", "gwc_inlet_temperature",
            "gwc_outlet_temperature", "bypass_inlet_temperature", "bypass_outlet_temperature"
        ]
        
        if key in temperature_regs:
            # Convert from unsigned to signed 16-bit
            if raw_value > 32767:
                signed_value = raw_value - 65536
            else:
                signed_value = raw_value
            return signed_value * 0.5  # 0.5°C resolution
        
        # Enhanced firmware version handling (HA 2025.7+)
        if key == "firmware_version":
            major = (raw_value >> 8) & 0xFF
            minor = raw_value & 0xFF
            return f"{major}.{minor}"
        
        # Enhanced power consumption handling (HA 2025.7+)
        if key == "actual_power_consumption":
            return raw_value  # Watts
        
        if key == "cumulative_power_consumption":
            return raw_value * 0.1  # Convert to kWh
        
        # Percentage values with validation
        percentage_regs = [
            "supply_percentage", "exhaust_percentage", "heat_recovery_efficiency",
            "heating_efficiency", "air_flow_rate_manual", "air_flow_rate_temporary",
            "air_flow_rate_auto", "bypass_position", "gwc_efficiency",
            "constant_flow_tolerance"
        ]
        
        if key in percentage_regs:
            # Validate percentage range
            if 0 <= raw_value <= 1500:  # Allow up to 150%
                return raw_value
            return None
        
        # Flow rates (already in m³/h)
        flow_regs = [
            "supply_flowrate", "exhaust_flowrate", "supply_air_flow", "exhaust_air_flow",
            "constant_flow_supply", "constant_flow_exhaust", "constant_flow_supply_setpoint",
            "constant_flow_exhaust_setpoint", "constant_flow_supply_target", "constant_flow_exhaust_target"
        ]
        
        if key in flow_regs:
            return raw_value
        
        # Time values (hours, days, minutes)
        time_regs = [
            "operating_hours", "filter_time_remaining", "boost_time_remaining",
            "temporary_time_remaining", "filter_change_interval", "filter_warning_threshold"
        ]
        
        if key in time_regs:
            return raw_value
        
        # Mode values (enums) - validate range
        mode_regs = {
            "mode": (0, 4),                    # 0-4 for operating modes
            "special_mode": (0, 15),           # 0-15 for special functions  
            "season_mode": (0, 2),             # 0-2 for season modes
            "comfort_mode": (0, 2),            # 0-2 for comfort modes
            "gwc_mode": (0, 2),                # 0-2 for GWC modes
            "bypass_mode": (0, 2),             # 0-2 for bypass modes
            "gwc_regeneration_mode": (0, 3),   # 0-3 for GWC regeneration
            "constant_flow_mode": (0, 1),      # 0-1 for CF mode
        }
        
        if key in mode_regs:
            min_val, max_val = mode_regs[key]
            if min_val <= raw_value <= max_val:
                return raw_value
            return None
        
        # Error and warning codes
        if key in ["error_code", "warning_code"]:
            return raw_value
        
        # Default: return raw value for unspecified registers
        return raw_value

    def _post_process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced post-processing of fetched data."""
        # Remove None values
        processed_data = {k: v for k, v in data.items() if v is not None}
        
        # Add computed values (HA 2025.7+ enhancement)
        self._add_computed_values(processed_data)
        
        # Validate critical values
        self._validate_critical_values(processed_data)
        
        return processed_data

    def _add_computed_values(self, data: Dict[str, Any]) -> None:
        """Add computed values for enhanced functionality."""
        # Compute actual intensity based on mode
        mode = data.get("mode", 0)
        if mode == 0:  # Auto mode
            data["current_intensity"] = data.get("supply_percentage", 0)
        elif mode == 1:  # Manual mode
            data["current_intensity"] = data.get("air_flow_rate_manual", 0)
        elif mode == 2:  # Temporary mode
            data["current_intensity"] = data.get("air_flow_rate_temporary", 0)
        
        # Compute heat recovery effectiveness
        supply_temp = data.get("supply_temperature")
        outside_temp = data.get("outside_temperature")
        exhaust_temp = data.get("exhaust_temperature")
        
        if all(temp is not None for temp in [supply_temp, outside_temp, exhaust_temp]):
            if exhaust_temp != outside_temp:
                effectiveness = (supply_temp - outside_temp) / (exhaust_temp - outside_temp)
                data["computed_effectiveness"] = max(0, min(1, effectiveness)) * 100
        
        # Enhanced diagnostics (HA 2025.7+)
        if "actual_power_consumption" in data and "current_intensity" in data:
            intensity = data["current_intensity"]
            if intensity > 0:
                data["power_efficiency"] = data["actual_power_consumption"] / intensity

    def _validate_critical_values(self, data: Dict[str, Any]) -> None:
        """Validate critical system values."""
        # Temperature range validation
        for temp_key in ["outside_temperature", "supply_temperature", "exhaust_temperature"]:
            temp = data.get(temp_key)
            if temp is not None and (temp < -40 or temp > 70):
                _LOGGER.warning("Temperature %s out of realistic range: %.1f°C", temp_key, temp)
                data[temp_key] = None
        
        # Flow rate validation
        for flow_key in ["supply_flowrate", "exhaust_flowrate"]:
            flow = data.get(flow_key)
            if flow is not None and (flow < 0 or flow > 2000):  # Realistic range for home units
                _LOGGER.warning("Flow rate %s out of realistic range: %d m³/h", flow_key, flow)
                data[flow_key] = None

    async def async_write_register(self, key: str, value: int) -> bool:
        """Enhanced register writing with validation."""
        if key not in HOLDING_REGISTERS and key not in COIL_REGISTERS:
            _LOGGER.error("Register %s is not writable", key)
            return False
        
        try:
            success = await self.hass.async_add_executor_job(
                self._write_register_sync, key, value
            )
            if success:
                _LOGGER.debug("Successfully wrote %s = %s", key, value)
                # Update local cache immediately for better responsiveness
                self._read_cache[key] = value
            return success
        except Exception as exc:
            _LOGGER.error("Failed to write register %s: %s", key, exc)
            return False

    def _write_register_sync(self, key: str, value: int) -> bool:
        """Synchronous register writing."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            if not client.connect():
                return False
            
            if key in HOLDING_REGISTERS:
                address = HOLDING_REGISTERS[key]
                response = client.write_register(address, value, slave=self.slave_id)
            elif key in COIL_REGISTERS:
                address = COIL_REGISTERS[key]
                response = client.write_coil(address, bool(value), slave=self.slave_id)
            else:
                return False
            
            return not response.isError()
            
        except Exception as exc:
            _LOGGER.error("Modbus write error for %s: %s", key, exc)
            return False
        finally:
            client.close()

    @property
    def device_info(self) -> Dict[str, Any]:
        """Enhanced device information."""
        return {
            "identifiers": {(DOMAIN, f"{self.host}_{self.slave_id}")},
            "name": f"ThesslaGreen {self.host}",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": self.data.get("firmware_version", "Unknown") if self.data else "Unknown",
            "configuration_url": f"http://{self.host}",
        }

    @property
    def diagnostics_data(self) -> Dict[str, Any]:
        """Enhanced diagnostics data for HA 2025.7+."""
        return {
            "coordinator_stats": self._read_stats,
            "available_registers": {
                reg_type: len(registers) 
                for reg_type, registers in self.available_registers.items()
            },
            "batch_groups": {
                reg_type: len(groups)
                for reg_type, groups in self._consecutive_groups.items()
            },
            "connection_info": {
                "host": self.host,
                "port": self.port,
                "slave_id": self.slave_id,
                "timeout": self.timeout,
                "scan_interval": self.update_interval.total_seconds(),
            },
            "failed_registers": list(self._failed_registers),
            "last_successful_data": dict(self.data) if self.data else {},
        }