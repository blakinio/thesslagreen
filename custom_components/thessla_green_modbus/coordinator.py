"""Data update coordinator for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    COIL_REGISTERS,
    DEFAULT_SCAN_INTERVAL,
    DISCRETE_INPUT_REGISTERS,
    DOMAIN,
    SENSOR_UNAVAILABLE,
)
from .modbus_client import ThesslaGreenModbusClient
from .modbus_exceptions import ConnectionException, ModbusException
from .modbus_helpers import _call_modbus
from .multipliers import REGISTER_MULTIPLIERS
from .registers import HOLDING_REGISTERS, INPUT_REGISTERS

_LOGGER = logging.getLogger(__name__)

# Registers that should be interpreted as signed int16
SIGNED_REGISTERS = {
    "outside_temperature",
    "supply_temperature", 
    "exhaust_temperature",
    "fpx_temperature",
    "duct_supply_temperature",
    "gwc_temperature",
    "ambient_temperature",
    "heating_temperature",
}

# DAC registers that output voltage (0-10V scaled from 0-4095)
DAC_REGISTERS = {
    "dac_supply",
    "dac_exhaust", 
    "dac_heater",
    "dac_cooler",
}

def _to_signed_int16(value: int) -> int:
    """Convert unsigned int16 to signed int16."""
    if value > 32767:
        return value - 65536
    return value

class ThesslaGreenDataCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching data from the ThesslaGreen device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ThesslaGreenModbusClient,
        available_registers: Dict[str, Set[str]],
    ) -> None:
        """Initialize the data coordinator."""
        self.entry = entry
        self.client = client
        self.available_registers = available_registers
        self.slave_id = entry.data.get("slave_id", 10)
        self.retry = entry.data.get("retry", 3)
        
        # ... [pozostały kod __init__ bez zmian] ...
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=scan_interval),
        )

    def _process_register_value(self, register_name: str, value: int) -> Any:
        """Process register value according to its type and multiplier."""
        
        # Convert to signed int16 for temperature registers
        if register_name in SIGNED_REGISTERS:
            value = _to_signed_int16(value)
            
            # Check for sensor unavailable (0x8000 as signed = -32768)
            if value == -32768:
                _LOGGER.debug("Temperature sensor %s unavailable (0x8000)", register_name)
                return None
                
        # DAC registers are always unsigned (0-4095)
        elif register_name in DAC_REGISTERS:
            # Ensure value is in valid range
            if value > 4095:
                _LOGGER.warning("DAC register %s has invalid value: %d", register_name, value)
                return None
                
        # Check for sensor error values for other registers
        elif value == SENSOR_UNAVAILABLE:
            if "flow" in register_name.lower():
                _LOGGER.debug("Flow sensor %s unavailable", register_name)
                return None
                
        # Apply multiplier if defined
        if register_name in REGISTER_MULTIPLIERS:
            value = value * REGISTER_MULTIPLIERS[register_name]
            
        return value

    async def _read_input_registers_optimized(self) -> Dict[str, Any]:
        """Read input registers using optimized batch reading."""
        data = {}

        if self.client is None:
            try:
                await self._ensure_connection()
            except Exception as exc:
                raise ConnectionException("Modbus client is not connected") from exc
            if self.client is None:
                raise ConnectionException("Modbus client is not connected")

        if "input_registers" not in self._register_groups:
            return data

        for start_addr, count in self._register_groups["input_registers"]:
            response = await self._read_with_retry(
                self.client.read_input_registers, start_addr, count, "input"
            )
            if response is None:
                _LOGGER.debug(
                    "Failed to read input registers at 0x%04X after %d attempts",
                    start_addr,
                    self.retry,
                )
                continue

            # Process each register in the batch
            for i, value in enumerate(response.registers):
                addr = start_addr + i
                register_name = self._find_register_name(INPUT_REGISTERS, addr)
                if register_name and register_name in self.available_registers["input_registers"]:
                    processed_value = self._process_register_value(register_name, value)
                    if processed_value is not None:
                        data[register_name] = processed_value
                        self.statistics["total_registers_read"] += 1
                    else:
                        _LOGGER.debug("Register %s returned None after processing", register_name)

        return data

    async def _read_holding_registers_optimized(self) -> Dict[str, Any]:
        """Read holding registers using optimized batch reading."""
        data = {}

        if self.client is None:
            try:
                await self._ensure_connection()
            except Exception as exc:
                raise ConnectionException("Modbus client is not connected") from exc
            if self.client is None:
                raise ConnectionException("Modbus client is not connected")

        if "holding_registers" not in self._register_groups:
            return data

        for start_addr, count in self._register_groups["holding_registers"]:
            response = await self._read_with_retry(
                self.client.read_holding_registers, start_addr, count, "holding"
            )
            if response is None:
                _LOGGER.debug(
                    "Failed to read holding registers at 0x%04X after %d attempts",
                    start_addr,
                    self.retry,
                )
                continue

            # Process each register in the batch
            for i, value in enumerate(response.registers):
                addr = start_addr + i
                register_name = self._find_register_name(HOLDING_REGISTERS, addr)
                if register_name and register_name in self.available_registers["holding_registers"]:
                    processed_value = self._process_register_value(register_name, value)
                    if processed_value is not None:
                        data[register_name] = processed_value
                        self.statistics["total_registers_read"] += 1
                    else:
                        _LOGGER.debug("Register %s returned None after processing", register_name)

        return data

    # ... [pozostałe metody bez zmian] ...
