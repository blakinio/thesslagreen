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
)
from .device_scanner import ThesslaGreenDeviceScanner

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
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        
        self.available_registers: dict[str, set[str]] = {}
        self.device_info: dict[str, Any] = {}
        self.capabilities: dict[str, bool] = {}
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh and device scanning."""
        _LOGGER.debug("Performing initial device scan...")
        
        # First scan the device to determine available registers
        scanner = ThesslaGreenDeviceScanner(self.host, self.port, self.slave_id)
        try:
            scan_result = await scanner.scan_device()
            self.available_registers = scan_result["available_registers"]
            self.device_info = scan_result["device_info"]
            self.capabilities = scan_result["capabilities"]
            
            _LOGGER.info(
                "Device scan complete. Found %d total registers, device: %s",
                sum(len(regs) for regs in self.available_registers.values()),
                self.device_info.get("device_name", "Unknown"),
            )
        except Exception as exc:
            _LOGGER.error("Device scanning failed: %s", exc)
            # Continue without scanning - use all registers
            self.available_registers = {
                "input_registers": set(INPUT_REGISTERS.keys()),
                "holding_registers": set(HOLDING_REGISTERS.keys()),
                "coil_registers": set(COIL_REGISTERS.keys()),
                "discrete_inputs": set(DISCRETE_INPUT_REGISTERS.keys()),
            }
            self.capabilities = {}

        # Now perform the first data refresh
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

            # Add device info to data
            data["device_info"] = self.device_info
            data["capabilities"] = self.capabilities

            return data

        except Exception as exc:
            _LOGGER.error("Error updating data: %s", exc)
            raise UpdateFailed(f"Error communicating with device: {exc}") from exc
        finally:
            client.close()

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

                result = client.read_input_registers(chunk_start, count, slave=self.slave_id)
                if result.isError():
                    _LOGGER.warning("Error reading input registers at 0x%04X", chunk_start)
                    continue

                for name, address in chunk_registers.items():
                    idx = address - chunk_start
                    if idx < len(result.registers):
                        raw_value = result.registers[idx]
                        data[name] = self._process_input_register_value(name, raw_value)

            except Exception as exc:
                _LOGGER.warning(
                    "Failed to read input register chunk at 0x%04X: %s", chunk_start, exc
                )

        return data

    def _read_holding_registers(self, client: ModbusTcpClient) -> dict[str, Any]:
        """Read holding registers efficiently."""
        data = {}
        available_regs = self.available_registers.get("holding_registers", set())
        
        if not available_regs:
            return data

        # Group registers by address ranges for efficient reading
        register_chunks = self._group_registers_by_range(
            {name: addr for name, addr in HOLDING_REGISTERS.items() if name in available_regs}
        )

        for chunk_start, chunk_registers in register_chunks.items():
            try:
                max_addr = max(addr for addr in chunk_registers.values())
                count = max_addr - chunk_start + 1
                
                if count > 125:  # Modbus limit
                    continue

                result = client.read_holding_registers(chunk_start, count, slave=self.slave_id)
                if result.isError():
                    _LOGGER.warning("Error reading holding registers at 0x%04X", chunk_start)
                    continue

                for name, address in chunk_registers.items():
                    idx = address - chunk_start
                    if idx < len(result.registers):
                        raw_value = result.registers[idx]
                        data[name] = self._process_holding_register_value(name, raw_value)

            except Exception as exc:
                _LOGGER.warning(
                    "Failed to read holding register chunk at 0x%04X: %s", chunk_start, exc
                )

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
            result = client.read_coils(min_addr, count, slave=self.slave_id)
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
            result = client.read_discrete_inputs(min_addr, count, slave=self.slave_id)
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
        # Temperature registers (x0.1°C, 0x8000 = invalid)
        if "temperature" in name:
            if raw_value == INVALID_TEMPERATURE:
                return None
            return raw_value * 0.1 if raw_value < INVALID_TEMPERATURE else raw_value * 0.1 - 6553.6

        # Flow registers
        if "flowrate" in name or "air_flow" in name:
            if raw_value == INVALID_FLOW:
                return None
            return raw_value

        # Percentage registers
        if "percentage" in name:
            return raw_value

        # Version registers
        if name in ["firmware_major", "firmware_minor", "firmware_patch"]:
            return raw_value

        # DAC registers (voltage)
        if name.startswith("dac_"):
            return raw_value * 0.00244  # 0-4095 -> 0-10V

        # Default
        return raw_value

    def _process_holding_register_value(self, name: str, raw_value: int) -> Any:
        """Process holding register value based on register type."""
        # Temperature registers (x0.5°C)
        if any(temp_key in name for temp_key in ["temperature", "temp"]):
            return raw_value * 0.5

        # BCD time registers [GGMM]
        if "time" in name and ("summer" in name or "winter" in name or "airing" in name):
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

        # Default
        return raw_value

    async def async_write_register(self, register_name: str, value: Any) -> bool:
        """Write to a holding register."""
        if register_name not in HOLDING_REGISTERS:
            _LOGGER.error("Unknown register: %s", register_name)
            return False

        address = HOLDING_REGISTERS[register_name]
        processed_value = self._process_write_value(register_name, value)

        return await asyncio.get_event_loop().run_in_executor(
            None, self._write_register_sync, address, processed_value
        )

    def _write_register_sync(self, address: int, value: int) -> bool:
        """Synchronously write to a register."""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            if not client.connect():
                return False

            result = client.write_register(address, value, slave=self.slave_id)
            return not result.isError()

        except Exception as exc:
            _LOGGER.error("Error writing register 0x%04X: %s", address, exc)
            return False
        finally:
            client.close()

    def _process_write_value(self, register_name: str, value: Any) -> int:
        """Process value for writing based on register type."""
        # Temperature registers (x0.5°C)
        if any(temp_key in register_name for temp_key in ["temperature", "temp"]):
            return int(value * 2)

        # Time registers [GGMM]
        if "time" in register_name and isinstance(value, str):
            if ":" in value:
                hour, minute = map(int, value.split(":"))
                return (hour << 8) | minute

        # Direct integer values
        return int(value)

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")