"""Enhanced data coordinator for ThesslaGreen Modbus - FIXED VERSION."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    INVALID_TEMPERATURE,
    INVALID_FLOW,
)

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator):
    """Enhanced coordinator for managing data from ThesslaGreen device."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        scan_interval: int,
        timeout: int = 10,
    ) -> None:
        """Initialize the coordinator."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        
        # Enhanced state tracking
        self.available_registers: dict[str, set[str]] = {}
        self.device_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        self._register_groups: dict[str, list] = {}
        self._failed_registers: set[str] = set()
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_setup_device(self) -> None:
        """Enhanced device setup with improved scanning."""
        from .device_scanner import ThesslaGreenDeviceScanner
        
        scanner = ThesslaGreenDeviceScanner(self.host, self.port, self.slave_id)
        
        try:
            _LOGGER.info("Starting enhanced device scan on %s:%d (slave %d)", 
                        self.host, self.port, self.slave_id)
            
            scan_result = await scanner.scan_device()
            
            self.available_registers = scan_result["available_registers"]
            self.device_info = scan_result["device_info"]
            self.capabilities = scan_result["capabilities"]
            
            _LOGGER.info(
                "Device scan complete: %s - Found %d register types, pre-computed %d read groups",
                self.device_info.get("device_name", "Unknown"),
                len(self.available_registers),
                sum(len(groups) for groups in self._register_groups.values())
            )
            
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise
        
        # Pre-compute register groups for optimization
        self._precompute_register_groups()
        
        # Perform initial data refresh
        await super().async_config_entry_first_refresh()

    def _precompute_register_groups(self) -> None:
        """Pre-compute optimal register groups for efficient batch reading."""
        self._register_groups = {}
        
        register_sets = {
            "input_registers": (INPUT_REGISTERS, self.available_registers.get("input_registers", set())),
            "holding_registers": (HOLDING_REGISTERS, self.available_registers.get("holding_registers", set())),
        }
        
        for reg_type, (all_registers, available) in register_sets.items():
            available_regs = {name: addr for name, addr in all_registers.items() if name in available}
            
            if available_regs:
                groups = self._group_registers_by_range(available_regs, max_gap=15, max_size=100)
                self._register_groups[reg_type] = [
                    (start_addr, count, regs) 
                    for start_addr, regs in groups.items()
                    for count in [max(addr for addr in regs.values()) - start_addr + 1]
                    if count <= 125  # Modbus limit
                ]
                
                _LOGGER.debug(
                    "Pre-computed %d register groups for %s", 
                    len(self._register_groups[reg_type]), reg_type
                )

    async def _async_update_data(self) -> dict[str, Any]:
        """Optimized data fetch from the device."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._update_data_sync
        )

    def _update_data_sync(self) -> dict[str, Any]:
        """Optimized synchronous data fetch from the device."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        data: dict[str, Any] = {}

        try:
            if not client.connect():
                raise UpdateFailed("Failed to connect to device")

            # Read available input registers (optimized)
            if "input_registers" in self._register_groups:
                input_data = self._read_input_registers_optimized(client)
                data.update(input_data)

            # Read available holding registers (optimized) 
            if "holding_registers" in self._register_groups:
                holding_data = self._read_holding_registers_optimized(client)
                data.update(holding_data)

            # Read coil and discrete registers (small sets, read all at once)
            coil_data = self._read_coil_registers_batch(client)
            data.update(coil_data)
            
            discrete_data = self._read_discrete_inputs_batch(client)
            data.update(discrete_data)

            # Enhanced device status determination
            device_status = self._determine_device_status_enhanced(data)
            data["device_status_smart"] = device_status

            # Performance logging
            total_registers = len(data)
            failed_count = len(self._failed_registers)
            success_rate = ((total_registers - failed_count) / total_registers * 100) if total_registers > 0 else 0
            
            _LOGGER.debug(
                "Optimized data update complete: %d registers read, %.1f%% success rate",
                total_registers, success_rate
            )

            return data

        except Exception as exc:
            _LOGGER.error("Error in optimized data update: %s", exc)
            raise UpdateFailed(f"Error communicating with device: {exc}") from exc
        finally:
            client.close()

    def _determine_device_status_enhanced(self, data: dict) -> bool:
        """Enhanced device status detection with multiple fallback methods."""
        
        # Method 1: Check main ON/OFF switch (most reliable)
        panel_mode = data.get("on_off_panel_mode")
        if panel_mode is not None:
            if panel_mode == 1:
                _LOGGER.debug("Device status: ON (panel mode active)")
                return True
            elif panel_mode == 0:
                _LOGGER.debug("Device status: OFF (panel mode disabled)")
                return False
        
        # Method 2: Check fan power supply (coil register)
        fan_power = data.get("power_supply_fans")
        if fan_power is not None:
            status = bool(fan_power)
            _LOGGER.debug("Device status: %s (fan power coil)", "ON" if status else "OFF")
            return status
        
        # Method 3: Check fan activity based on speed percentages
        supply_percentage = data.get("supply_percentage")
        exhaust_percentage = data.get("exhaust_percentage")
        
        if supply_percentage is not None and exhaust_percentage is not None:
            # If any fan has speed > 5%, device is active
            if supply_percentage > 5 or exhaust_percentage > 5:
                _LOGGER.debug("Device status: ON (fan activity: supply=%s%%, exhaust=%s%%)", 
                            supply_percentage, exhaust_percentage)
                return True
            else:
                _LOGGER.debug("Device status: OFF (no fan activity)")
                return False
        
        # Method 4: Check air flows (m³/h)
        supply_flow = data.get("supply_flowrate")
        exhaust_flow = data.get("exhaust_flowrate")
        
        if supply_flow is not None and exhaust_flow is not None:
            # If there's any meaningful airflow, device is working
            if supply_flow > 10 or exhaust_flow > 10:  # 10 m³/h as minimum threshold
                _LOGGER.debug("Device status: ON (air flow: supply=%sm³/h, exhaust=%sm³/h)", 
                            supply_flow, exhaust_flow)
                return True
            else:
                _LOGGER.debug("Device status: OFF (no air flow)")
                return False
        
        # Method 5: Check if device is responding but in standby
        valid_readings = len([v for v in data.values() if v is not None])
        if valid_readings > 3:
            # Device is communicating but fans are off - probably standby
            _LOGGER.info("Device appears to be in standby mode - communicating but fans off (%d valid readings)", 
                        valid_readings)
            return False  # Standby = OFF for user perspective
        
        # Default: insufficient data to determine status
        _LOGGER.warning("Cannot determine device status - insufficient data (only %d valid readings)", 
                       valid_readings)
        return False

    def _read_input_registers_optimized(self, client: ModbusTcpClient) -> dict[str, Any]:
        """Optimized input register reading using pre-computed groups."""
        data = {}
        
        for start_addr, count, registers in self._register_groups.get("input_registers", []):
            try:
                result = client.read_input_registers(start_addr, count=count, slave=self.slave_id)
                if result.isError():
                    _LOGGER.debug("Error reading input register group at 0x%04X: %s", start_addr, result)
                    continue

                # Process all registers in this group
                for name, address in registers.items():
                    idx = address - start_addr
                    if idx < len(result.registers):
                        raw_value = result.registers[idx]
                        processed_value = self._process_input_register_value(name, raw_value)
                        if processed_value is not None:
                            data[name] = processed_value
                            self._failed_registers.discard(name)
                        else:
                            self._failed_registers.add(name)

            except Exception as exc:
                _LOGGER.debug("Failed to read input register group at 0x%04X: %s", start_addr, exc)
                # Mark all registers in this group as failed
                for name in registers:
                    self._failed_registers.add(name)

        return data

    def _read_holding_registers_optimized(self, client: ModbusTcpClient) -> dict[str, Any]:
        """Optimized holding register reading with critical register prioritization."""
        data = {}
        
        # First, read critical registers individually for reliability
        critical_registers = {
            "on_off_panel_mode": 0x1123,
            "mode": 0x1070,
            "stop_ahu_code": 0x1120,
        }
        
        for reg_name, address in critical_registers.items():
            if reg_name in self.available_registers.get("holding_registers", set()):
                try:
                    result = client.read_holding_registers(address, count=1, slave=self.slave_id)
                    if not result.isError():
                        raw_value = result.registers[0]
                        processed_value = self._process_holding_register_value(reg_name, raw_value)
                        data[reg_name] = processed_value
                        self._failed_registers.discard(reg_name)
                        _LOGGER.debug("Critical register %s = %s", reg_name, processed_value)
                    else:
                        self._failed_registers.add(reg_name)
                        _LOGGER.warning("Failed to read critical register %s", reg_name)
                except Exception as exc:
                    self._failed_registers.add(reg_name)
                    _LOGGER.error("Exception reading critical register %s: %s", reg_name, exc)

        # Then read other registers in optimized groups
        for start_addr, count, registers in self._register_groups.get("holding_registers", []):
            # Skip if this group contains critical registers we already read
            if any(addr in critical_registers.values() for addr in registers.values()):
                continue
                
            try:
                result = client.read_holding_registers(start_addr, count=count, slave=self.slave_id)
                if result.isError():
                    _LOGGER.debug("Error reading holding register group at 0x%04X: %s", start_addr, result)
                    continue

                for name, address in registers.items():
                    idx = address - start_addr
                    if idx < len(result.registers):
                        raw_value = result.registers[idx]
                        processed_value = self._process_holding_register_value(name, raw_value)
                        if processed_value is not None:
                            data[name] = processed_value
                            self._failed_registers.discard(name)

            except Exception as exc:
                _LOGGER.debug("Failed to read holding register group at 0x%04X: %s", start_addr, exc)
                for name in registers:
                    self._failed_registers.add(name)

        return data

    def _read_coil_registers_batch(self, client: ModbusTcpClient) -> dict[str, Any]:
        """Read all coil registers in a single batch."""
        data = {}
        available_regs = self.available_registers.get("coil_registers", set())
        
        if not available_regs:
            return data

        available_coils = {name: addr for name, addr in COIL_REGISTERS.items() if name in available_regs}
        if not available_coils:
            return data

        min_addr = min(available_coils.values())
        max_addr = max(available_coils.values())
        count = max_addr - min_addr + 1

        try:
            result = client.read_coils(min_addr, count=count, slave=self.slave_id)
            if not result.isError():
                for name, address in available_coils.items():
                    idx = address - min_addr
                    if idx < len(result.bits):
                        data[name] = bool(result.bits[idx])
            else:
                _LOGGER.debug("Error reading coils: %s", result)
        except Exception as exc:
            _LOGGER.debug("Failed to read coils: %s", exc)

        return data

    def _read_discrete_inputs_batch(self, client: ModbusTcpClient) -> dict[str, Any]:
        """Read all discrete input registers in a single batch."""
        data = {}
        available_regs = self.available_registers.get("discrete_inputs", set())
        
        if not available_regs:
            return data

        available_inputs = {name: addr for name, addr in DISCRETE_INPUT_REGISTERS.items() if name in available_regs}
        if not available_inputs:
            return data

        min_addr = min(available_inputs.values())
        max_addr = max(available_inputs.values())
        count = max_addr - min_addr + 1

        try:
            result = client.read_discrete_inputs(min_addr, count=count, slave=self.slave_id)
            if not result.isError():
                for name, address in available_inputs.items():
                    idx = address - min_addr
                    if idx < len(result.bits):
                        data[name] = bool(result.bits[idx])
            else:
                _LOGGER.debug("Error reading discrete inputs: %s", result)
        except Exception as exc:
            _LOGGER.debug("Failed to read discrete inputs: %s", exc)

        return data

    def _group_registers_by_range(self, registers: dict[str, int], max_gap: int = 15, max_size: int = 100) -> dict[int, dict[str, int]]:
        """Optimized register grouping with better parameters."""
        if not registers:
            return {}

        sorted_regs = sorted(registers.items(), key=lambda x: x[1])
        chunks = {}
        current_chunk = {}
        current_start = None

        for name, addr in sorted_regs:
            if current_start is None:
                current_start = addr
                current_chunk[name] = addr
            elif addr - current_start <= max_gap and len(current_chunk) < max_size:
                current_chunk[name] = addr
            else:
                if current_chunk:
                    chunks[current_start] = current_chunk
                current_start = addr
                current_chunk = {name: addr}

        if current_chunk:
            chunks[current_start] = current_chunk

        return chunks

    def _process_input_register_value(self, name: str, raw_value: int) -> Any:
        """Enhanced input register value processing with better validation."""
        # Temperature registers (×0.1°C, 0x8000 = invalid)
        if "temperature" in name:
            if raw_value == INVALID_TEMPERATURE:
                return None
            
            # Handle signed 16-bit values
            if raw_value > 32767:
                signed_value = raw_value - 65536
            else:
                signed_value = raw_value
            
            # Apply correct multiplier: 0.1 according to documentation
            final_temp = round(signed_value * 0.1, 1)
            
            # Enhanced validation - reasonable temperature range for HVAC
            if final_temp < -50 or final_temp > 80:
                _LOGGER.debug("Temperature %s: Invalid value %.1f°C (raw: %d)", name, final_temp, raw_value)
                return None
            
            return final_temp

        # Air flow values
        if "air_flow" in name or "flowrate" in name:
            if raw_value == INVALID_FLOW:
                return None
            return raw_value

        # Percentage values
        if "percentage" in name:
            # Validate percentage range
            if raw_value > 200:  # Allow up to 200% for boost modes
                return None
            return raw_value

        # DAC outputs (0-10V) - multiplier 0.00244 according to documentation
        if "dac_" in name:
            voltage = round(raw_value * 0.00244, 2)
            return voltage if 0 <= voltage <= 10.5 else None  # Allow slight overvoltage

        # Firmware version components
        if "firmware_" in name or "version_" in name:
            return raw_value

        # Serial number components
        if "serial_number_" in name:
            return raw_value

        # Default: return raw value with basic validation
        return raw_value if 0 <= raw_value <= 65535 else None

    def _process_holding_register_value(self, name: str, raw_value: int) -> Any:
        """Enhanced holding register value processing."""
        # Temperature values (stored with 0.5°C resolution)
        if "temperature" in name and "manual" in name or "temporary" in name:
            # Convert to actual temperature (×0.5°C)
            return round(raw_value * 0.5, 1) if 0 <= raw_value <= 180 else None  # 0-90°C range
        
        # Special temperature registers for bypass/GWC (also ×0.5°C)
        if name in ["min_bypass_temperature", "air_temperature_summer_free_heating", 
                   "air_temperature_summer_free_cooling", "min_gwc_air_temperature", 
                   "max_gwc_air_temperature", "delta_t_gwc"]:
            return round(raw_value * 0.5, 1) if 0 <= raw_value <= 160 else None  # 0-80°C range
        
        # Percentage values
        if "coef" in name or "percentage" in name or "air_flow_rate" in name:
            # Validate percentage range (allow up to 200% for boost)
            return raw_value if 0 <= raw_value <= 200 else None
        
        # Time values in [GGMM] format
        if "time" in name and name.endswith("_time"):
            if raw_value == 0x2400 or raw_value == 9216:  # Disabled value
                return None
            # Extract hours and minutes
            hours = (raw_value >> 8) & 0xFF
            minutes = raw_value & 0xFF
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                return f"{hours:02d}:{minutes:02d}"
            return None
        
        # Mode values (ensure valid range)
        if name == "mode" or name.startswith("cfg_mode"):
            return raw_value if 0 <= raw_value <= 2 else None
        
        if name == "season_mode":
            return raw_value if 0 <= raw_value <= 1 else None
            
        if name == "special_mode":
            return raw_value if 0 <= raw_value <= 11 else None
        
        # Boolean values (ensure 0 or 1)
        if name.endswith("_flag") or name.endswith("_off") or name in ["comfort_mode_panel"]:
            return raw_value if raw_value in [0, 1] else None
        
        # Default: return raw value with basic validation
        return raw_value if 0 <= raw_value <= 65535 else None

    async def async_write_register(self, register_name: str, value: int) -> bool:
        """Write a single holding register."""
        if register_name not in HOLDING_REGISTERS:
            _LOGGER.error("Unknown register: %s", register_name)
            return False

        address = HOLDING_REGISTERS[register_name]
        
        def _write_sync():
            client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
            try:
                if not client.connect():
                    return False

                result = client.write_register(address, value, slave=self.slave_id)
                if result.isError():
                    _LOGGER.error("Error writing register %s (0x%04X): %s", register_name, address, result)
                    return False
                
                _LOGGER.debug("Successfully wrote %s = %s to 0x%04X", register_name, value, address)
                return True

            except Exception as exc:
                _LOGGER.error("Exception writing register %s: %s", register_name, exc)
                return False
            finally:
                client.close()

        return await asyncio.get_event_loop().run_in_executor(None, _write_sync)

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
        # Clean up any resources if needed
        self._failed_registers.clear()
        self._register_groups.clear()