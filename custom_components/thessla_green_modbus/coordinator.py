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
                "Device scan successful. Found %d register types with capabilities: %s",
                len(self.available_registers),
                list(self.capabilities.keys())
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

                result = client.read_input_registers(chunk_start, count=count, slave=self.slave_id)
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

                result = client.read_holding_registers(chunk_start, count=count, slave=self.slave_id)
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
                return None
            # Handle signed 16-bit values
            if raw_value > 32767:
                signed_value = raw_value - 65536
            else:
                signed_value = raw_value
            # Apply correct multiplier: 0.1 according to documentation
            return round(signed_value * 0.1, 1)

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
        """Process holding register value based on register type."""
        # Temperature setpoints (×0.5°C for holding registers)
        if "temperature" in name:
            return round(raw_value * 0.5, 1)

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

        # Default: return raw value
        return raw_value

    async def async_write_register(self, key: str, value: int) -> bool:
        """Write single register value."""
        register_address = None
        
        # Find register address
        if key in HOLDING_REGISTERS:
            register_address = HOLDING_REGISTERS[key]
        else:
            _LOGGER.error("Unknown register key: %s", key)
            return False

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
        # No persistent connections to close