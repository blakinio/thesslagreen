"""Data coordinator for ThesslaGreen Modbus integration."""
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
    OPERATING_MODES,
)
from .device_registry import ThesslaGreenDeviceScanner

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for ThesslaGreen Modbus communication."""

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

    async def async_config_entry_first_refresh(self) -> None:
        """Perform initial refresh including device scanning."""
        _LOGGER.info("Starting initial device scan...")
        
        # Scan device capabilities first
        scanner = ThesslaGreenDeviceScanner(self.host, self.port, self.slave_id)
        
        try:
            scan_result = await scanner.scan_device()
            self.available_registers = scan_result["available_registers"]
            self.device_info = scan_result["device_info"]
            self.capabilities = scan_result["capabilities"]
            
            _LOGGER.info(
                "Device scan successful. Found %d register types",
                len(self.available_registers)
            )
            
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise
        
        # Perform initial data refresh
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._update_data_sync
        )

    def _update_data_sync(self) -> dict[str, Any]:
        """Synchronously fetch data from the device."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        data: dict[str, Any] = {}

        try:
            if not client.connect():
                raise UpdateFailed("Failed to connect to device")

            # Read available input registers
            if "input_registers" in self.available_registers:
                input_data = self._read_input_registers(client)
                data.update(input_data)

            # Read available holding registers
            if "holding_registers" in self.available_registers:
                holding_data = self._read_holding_registers(client)
                data.update(holding_data)

            # Read available coil registers
            if "coil_registers" in self.available_registers:
                coil_data = self._read_coil_registers(client)
                data.update(coil_data)

            # Read available discrete input registers
            if "discrete_inputs" in self.available_registers:
                discrete_data = self._read_discrete_inputs(client)
                data.update(discrete_data)

            # Add debug info about device status
            self._debug_device_status(data)

            return data

        except Exception as exc:
            _LOGGER.error("Error updating data: %s", exc)
            raise UpdateFailed(f"Error communicating with device: {exc}") from exc
        finally:
            client.close()

    def _debug_device_status(self, data: dict) -> None:
        """Debug all possible device status indicators."""
        
        status_indicators = []
        
        # Check 1: Official panel mode
        panel_mode = data.get("on_off_panel_mode")
        if panel_mode is not None:
            status_indicators.append(f"Panel mode: {panel_mode} ({'ON' if panel_mode else 'OFF'})")
        else:
            status_indicators.append("Panel mode: NOT AVAILABLE")
        
        # Check 2: Fan power coil
        fan_power = data.get("power_supply_fans")
        if fan_power is not None:
            status_indicators.append(f"Fan power coil: {fan_power} ({'ON' if fan_power else 'OFF'})")
        else:
            status_indicators.append("Fan power coil: NOT AVAILABLE")
        
        # Check 3: Ventilation percentages
        supply_pct = data.get("supply_percentage")
        exhaust_pct = data.get("exhaust_percentage")
        status_indicators.append(f"Ventilation: supply={supply_pct}%, exhaust={exhaust_pct}%")
        
        # Check 4: Air flows
        supply_flow = data.get("supply_flowrate")
        exhaust_flow = data.get("exhaust_flowrate")
        status_indicators.append(f"Air flows: supply={supply_flow}m³/h, exhaust={exhaust_flow}m³/h")
        
        # Check 5: DAC voltages
        dac_supply = data.get("dac_supply")
        dac_exhaust = data.get("dac_exhaust")
        status_indicators.append(f"DAC voltages: supply={dac_supply}V, exhaust={dac_exhaust}V")
        
        # Check 6: Operating mode
        mode = data.get("mode")
        mode_names = {0: "AUTO", 1: "MANUAL", 2: "TEMPORARY"}
        mode_name = mode_names.get(mode, f"UNKNOWN({mode})")
        status_indicators.append(f"Operating mode: {mode} ({mode_name})")
        
        # Log all indicators
        _LOGGER.warning("=== DEVICE STATUS INVESTIGATION ===")
        for indicator in status_indicators:
            _LOGGER.warning("  %s", indicator)
        
        # Make a decision
        device_on_indicators = []
        
        if panel_mode == 1:
            device_on_indicators.append("Panel mode ON")
        if fan_power:
            device_on_indicators.append("Fans powered")
        if supply_pct and supply_pct > 0:
            device_on_indicators.append(f"Ventilation active ({supply_pct}%)")
        if (supply_flow and supply_flow > 0) or (exhaust_flow and exhaust_flow > 0):
            device_on_indicators.append("Air flow detected")
        if (dac_supply and dac_supply > 0.5) or (dac_exhaust and dac_exhaust > 0.5):
            device_on_indicators.append("Fan voltages present")
        
        if device_on_indicators:
            _LOGGER.warning("  DECISION: Device appears ON based on: %s", ", ".join(device_on_indicators))
        else:
            _LOGGER.warning("  DECISION: Device appears OFF - no activity detected")
        
        _LOGGER.warning("=== END INVESTIGATION ===")

    def _read_input_registers(self, client: ModbusTcpClient) -> dict[str, Any]:
        """Read input registers efficiently."""
        data = {}
        available_regs = self.available_registers.get("input_registers", set())
        
        if not available_regs:
            return data

        # Group registers by address ranges for efficient reading
        register_chunks = self._group_registers_by_range(
            {name: addr for name, addr in INPUT_REGISTERS.items() if name in available_regs}
        )

        for chunk_start, chunk_registers in register_chunks.items():
            try:
                max_addr = max(addr for addr in chunk_registers.values())
                count = max_addr - chunk_start + 1
                
                if count > 125:  # Modbus limit
                    continue

                result = client.read_input_registers(chunk_start, count=count, slave=self.slave_id)
                if result.isError():
                    _LOGGER.warning("Error reading input registers at 0x%04X", chunk_start)
                    continue

                for name, address in chunk_registers.items():
                    idx = address - chunk_start
                    if idx < len(result.registers):
                        raw_value = result.registers[idx]
                        processed_value = self._process_input_register_value(name, raw_value)
                        if processed_value is not None:
                            data[name] = processed_value

            except Exception as exc:
                _LOGGER.warning(
                    "Failed to read input register chunk at 0x%04X: %s", chunk_start, exc
                )

        return data

    def _read_holding_registers(self, client: ModbusTcpClient) -> dict[str, Any]:
        """Read holding registers efficiently with enhanced debugging."""
        data = {}
        available_regs = self.available_registers.get("holding_registers", set())
        
        if not available_regs:
            _LOGGER.debug("No holding registers available for reading")
            return data

        # Special handling for critical device status registers
        critical_registers = {
            "on_off_panel_mode": 0x1123,
            "mode": 0x1070,
        }
        
        # Try to read critical registers individually first
        for reg_name, address in critical_registers.items():
            if address is not None and reg_name in available_regs:
                try:
                    result = client.read_holding_registers(address, count=1, slave=self.slave_id)
                    if not result.isError():
                        raw_value = result.registers[0]
                        processed_value = self._process_holding_register_value(reg_name, raw_value)
                        data[reg_name] = processed_value
                        _LOGGER.info(
                            "Critical register %s (0x%04X): raw=%d, processed=%s", 
                            reg_name, address, raw_value, processed_value
                        )
                    else:
                        _LOGGER.warning("Failed to read critical register %s (0x%04X): %s", reg_name, address, result)
                except Exception as exc:
                    _LOGGER.error("Exception reading critical register %s: %s", reg_name, exc)

        # Group remaining registers by address ranges for efficient reading
        remaining_regs = {
            name: addr for name, addr in HOLDING_REGISTERS.items() 
            if name in available_regs and name not in critical_registers
        }
        
        register_chunks = self._group_registers_by_range(remaining_regs)

        for chunk_start, chunk_registers in register_chunks.items():
            try:
                max_addr = max(addr for addr in chunk_registers.values())
                count = max_addr - chunk_start + 1
                
                if count > 125:  # Modbus limit
                    _LOGGER.warning("Chunk too large (%d registers), skipping chunk at 0x%04X", count, chunk_start)
                    continue

                result = client.read_holding_registers(chunk_start, count=count, slave=self.slave_id)
                if result.isError():
                    _LOGGER.warning("Error reading holding register chunk at 0x%04X: %s", chunk_start, result)
                    continue

                for name, address in chunk_registers.items():
                    idx = address - chunk_start
                    if idx < len(result.registers):
                        raw_value = result.registers[idx]
                        processed_value = self._process_holding_register_value(name, raw_value)
                        if processed_value is not None:
                            data[name] = processed_value

            except Exception as exc:
                _LOGGER.warning(
                    "Failed to read holding register chunk at 0x%04X: %s", chunk_start, exc
                )

        _LOGGER.debug("Successfully read %d holding registers", len(data))
        return data

    def _read_coil_registers(self, client: ModbusTcpClient) -> dict[str, Any]:
        """Read coil registers."""
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
        except Exception as exc:
            _LOGGER.warning("Failed to read coils: %s", exc)

        return data

    def _read_discrete_inputs(self, client: ModbusTcpClient) -> dict[str, Any]:
        """Read discrete input registers."""
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
        except Exception as exc:
            _LOGGER.warning("Failed to read discrete inputs: %s", exc)

        return data

    def _group_registers_by_range(self, registers: dict[str, int], max_gap: int = 10) -> dict[int, dict[str, int]]:
        """Group registers by address ranges to minimize Modbus requests."""
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
            elif addr - current_start <= max_gap and len(current_chunk) < 100:
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
        """Process input register value based on register type."""
        # Temperature registers (×0.1°C, 0x8000 = invalid)
        if "temperature" in name:
            if raw_value == INVALID_TEMPERATURE:
                _LOGGER.debug("Temperature %s: Invalid value (sensor disconnected)", name)
                return None
            
            # Handle signed 16-bit values
            if raw_value > 32767:
                signed_value = raw_value - 65536
            else:
                signed_value = raw_value
            
            # Apply correct multiplier: 0.1 according to documentation
            final_temp = round(signed_value * 0.1, 1)
            
            # Validation - reasonable temperature range for HVAC (-50°C to +80°C)
            if final_temp < -50 or final_temp > 80:
                _LOGGER.warning(
                    "Temperature %s: Unreasonable value %.1f°C (raw: %d/0x%04X), possible sensor error", 
                    name, final_temp, raw_value, raw_value
                )
                return None
            
            return final_temp

        # Air flow values
        if "air_flow" in name or "flowrate" in name:
            if raw_value == INVALID_FLOW:
                return None
            return raw_value

        # Percentage values
        if "percentage" in name:
            return raw_value

        # DAC outputs (0-10V) - multiplier 0.00244
        if "dac_" in name:
            return round(raw_value * 0.00244, 2)

        # Default: return raw value
        return raw_value

    def _process_holding_register_value(self, name: str, raw_value: int) -> Any:
        """Process holding register value based on register type with enhanced logging."""
        
        # Special debug logging for critical device status registers
        if name in ["on_off_panel_mode", "mode"]:
            _LOGGER.warning(
                "CRITICAL REGISTER %s: raw_value=%d (0x%04X), bool=%s", 
                name, raw_value, raw_value, bool(raw_value)
            )
        
        # Temperature setpoints (×0.5°C for holding registers)
        if "temperature" in name:
            result = round(raw_value * 0.5, 1)
            if name in ["supply_air_temperature_manual", "supply_air_temperature_temporary", "required_temp"]:
                _LOGGER.debug("Temperature register %s: raw=%d -> %.1f°C", name, raw_value, result)
            return result

        # Time values in BCD format [GGMM]
        if "time" in name and any(x in name for x in ["summer", "winter", "airing", "start", "stop"]):
            if raw_value == 0xA200 or raw_value == 41472:  # Disabled
                return None
            hour = (raw_value >> 8) & 0xFF
            minute = raw_value & 0xFF
            return f"{hour:02d}:{minute:02d}"

        # Setting registers [AATT] - airflow% and temperature
        if "setting" in name and ("summer" in name or "winter" in name):
            airflow = (raw_value >> 8) & 0xFF
            temp_raw = raw_value & 0xFF
            temperature = temp_raw * 0.5
            return {"airflow": airflow, "temperature": temperature}

        # Date/time registers
        if name == "datetime_year_month":
            year = (raw_value >> 8) & 0xFF
            month = raw_value & 0xFF
            return {"year": 2000 + year, "month": month}
        
        if name == "datetime_day_dow":
            day = (raw_value >> 8) & 0xFF
            dow = raw_value & 0xFF
            return {"day": day, "day_of_week": dow}

        if name == "datetime_hour_minute":
            hour = (raw_value >> 8) & 0xFF
            minute = raw_value & 0xFF
            return {"hour": hour, "minute": minute}

        # Default: return raw value
        return raw_value

    async def async_write_register(self, key: str, value: int) -> bool:
        """Write single register value."""
        if key not in HOLDING_REGISTERS:
            _LOGGER.error("Unknown register key: %s", key)
            return False

        register_address = HOLDING_REGISTERS[key]
        return await asyncio.get_event_loop().run_in_executor(
            None, self._write_register_sync, register_address, value
        )

    def _write_register_sync(self, address: int, value: int) -> bool:
        """Synchronously write register value."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            if not client.connect():
                _LOGGER.error("Failed to connect for writing register 0x%04X", address)
                return False

            result = client.write_register(address, value, slave=self.slave_id)
            if result.isError():
                _LOGGER.error("Error writing register 0x%04X: %s", address, result)
                return False

            _LOGGER.debug("Successfully wrote value %s to register 0x%04X", value, address)
            return True

        except Exception as exc:
            _LOGGER.error("Exception writing register 0x%04X: %s", address, exc)
            return False
        finally:
            client.close()

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down coordinator")