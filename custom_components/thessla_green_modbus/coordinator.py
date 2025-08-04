"""Optimized data coordinator for ThesslaGreen Modbus integration - Enhanced Performance."""
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
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    DOMAIN,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    INVALID_TEMPERATURE,
    INVALID_FLOW,
)
from .device_scanner import ThesslaGreenDeviceScanner

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Optimized coordinator for ThesslaGreen Modbus communication."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        scan_interval: int,
        timeout: int,
        retry: int,
    ) -> None:
        """Initialize the coordinator."""
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
        self.available_registers: dict[str, set[str]] = {}
        self.device_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        
        # Performance optimization: pre-computed register groups
        self._register_groups: dict[str, list[tuple[int, int, dict[str, int]]]] = {}
        self._last_successful_read: dict[str, float] = {}
        self._failed_registers: set[str] = set()

    async def async_config_entry_first_refresh(self) -> None:
        """Perform initial refresh including device scanning."""
        _LOGGER.info("Starting optimized device scan...")
        
        # Scan device capabilities first
        scanner = ThesslaGreenDeviceScanner(self.host, self.port, self.slave_id)
        
        try:
            scan_result = await scanner.scan_device()
            self.available_registers = scan_result["available_registers"]
            self.device_info = scan_result["device_info"]
            self.capabilities = scan_result["capabilities"]
            
            # Pre-compute register groups for optimal reading
            self._precompute_register_groups()
            
            _LOGGER.info(
                "Optimized device scan successful. Found %d register types, pre-computed %d read groups",
                len(self.available_registers),
                sum(len(groups) for groups in self._register_groups.values())
            )
            
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise
        
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
        
        # Temperature setpoints (×0.5°C for holding registers)
        if "temperature" in name and ("manual" in name or "temporary" in name or "required" in name):
            result = round(raw_value * 0.5, 1)
            # Validate temperature setpoint range
            if 15 <= result <= 50:  # Reasonable setpoint range
                return result
            return None

        # BCD time values [HHMM]
        if any(keyword in name for keyword in ["time", "start", "stop"]) and "bcd" not in name.lower():
            if raw_value == 0xA200 or raw_value == 41472:  # Disabled
                return None
            hour = (raw_value >> 8) & 0xFF
            minute = raw_value & 0xFF
            if hour <= 23 and minute <= 59:
                return f"{hour:02d}:{minute:02d}"
            return None

        # Date/time registers
        if name == "datetime_year_month":
            year = (raw_value >> 8) & 0xFF
            month = raw_value & 0xFF
            if 1 <= month <= 12:
                return {"year": 2000 + year, "month": month}
            return None
        
        if name == "datetime_day_dow":
            day = (raw_value >> 8) & 0xFF
            dow = raw_value & 0xFF
            if 1 <= day <= 31 and 0 <= dow <= 6:
                return {"day": day, "day_of_week": dow}
            return None

        if name == "datetime_hour_minute":
            hour = (raw_value >> 8) & 0xFF
            minute = raw_value & 0xFF
            if hour <= 23 and minute <= 59:
                return {"hour": hour, "minute": minute}
            return None

        # Mode validations
        if name == "mode" and raw_value not in [0, 1, 2]:
            _LOGGER.warning("Invalid mode value: %d", raw_value)
            return 0  # Default to auto mode
            
        if name == "season_mode" and raw_value not in [0, 1]:
            return 0  # Default to summer

        # Special mode validation
        if name == "special_mode" and not (0 <= raw_value <= 11):
            return 0  # Default to no special function

        # Percentage values validation
        if "coef" in name or "intensity" in name or "percentage" in name:
            if 0 <= raw_value <= 200:  # Allow up to 200% for some coefficients
                return raw_value
            return None

        # Default: return raw value
        return raw_value

    async def async_write_register(self, key: str, value: int) -> bool:
        """Optimized register writing with retry logic."""
        if key not in HOLDING_REGISTERS:
            _LOGGER.error("Unknown register key: %s", key)
            return False

        register_address = HOLDING_REGISTERS[key]
        
        for attempt in range(self.retry):
            try:
                success = await asyncio.get_event_loop().run_in_executor(
                    None, self._write_register_sync, register_address, value
                )
                if success:
                    return True
                    
                if attempt < self.retry - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))  # Progressive delay
                    
            except Exception as exc:
                _LOGGER.debug("Write attempt %d failed for register %s: %s", attempt + 1, key, exc)
                if attempt < self.retry - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))

        _LOGGER.error("Failed to write register %s after %d attempts", key, self.retry)
        return False

    def _write_register_sync(self, address: int, value: int) -> bool:
        """Optimized synchronous register writing."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            if not client.connect():
                return False

            result = client.write_register(address, value, slave=self.slave_id)
            if result.isError():
                _LOGGER.debug("Error writing register 0x%04X: %s", address, result)
                return False

            _LOGGER.debug("Successfully wrote value %s to register 0x%04X", value, address)
            return True

        except Exception as exc:
            _LOGGER.debug("Exception writing register 0x%04X: %s", address, exc)
            return False
        finally:
            client.close()

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down optimized coordinator")
        self._register_groups.clear()
        self._failed_registers.clear()