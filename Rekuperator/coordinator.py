"""Data coordinator for TeslaGreen Modbus Integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_SLAVE_ID, DEFAULT_SCAN_INTERVAL, MODBUS_REGISTERS

_LOGGER = logging.getLogger(__name__)


class TeslaGreenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for TeslaGreen Modbus data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        self.slave_id = entry.data[CONF_SLAVE_ID]
        self._client = None
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from TeslaGreen device."""
        try:
            from pymodbus.client import ModbusTcpClient
            
            if self._client is None:
                self._client = ModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=10
                )
            
            if not self._client.connect():
                raise UpdateFailed("Cannot connect to Modbus device")
            
            data = {}
            
            # Read temperature sensors
            for register_name, address in MODBUS_REGISTERS.items():
                try:
                    result = self._client.read_holding_registers(
                        address, 1, slave=self.slave_id
                    )
                    if not result.isError():
                        # Convert register value based on type
                        raw_value = result.registers[0]
                        
                        if "temp" in register_name:
                            # Temperature: divide by 10 for decimal
                            data[register_name] = raw_value / 10.0
                        elif "speed" in register_name:
                            # Fan speed: direct value
                            data[register_name] = raw_value
                        elif register_name in ["co2_level", "humidity"]:
                            # Air quality: direct value
                            data[register_name] = raw_value
                        else:
                            # Status registers: direct value
                            data[register_name] = raw_value
                            
                except Exception as ex:
                    _LOGGER.warning(f"Failed to read register {register_name}: {ex}")
                    data[register_name] = None
            
            return data
            
        except Exception as ex:
            if self._client:
                self._client.close()
                self._client = None
            raise UpdateFailed(f"Error communicating with TeslaGreen device: {ex}") from ex

    async def async_write_register(self, register_name: str, value: int) -> bool:
        """Write value to Modbus register."""
        try:
            if register_name not in MODBUS_REGISTERS:
                _LOGGER.error(f"Unknown register: {register_name}")
                return False
            
            address = MODBUS_REGISTERS[register_name]
            
            if self._client is None:
                from pymodbus.client import ModbusTcpClient
                self._client = ModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=10
                )
            
            if not self._client.connect():
                return False
            
            result = self._client.write_register(
                address, value, slave=self.slave_id
            )
            
            if result.isError():
                _LOGGER.error(f"Failed to write register {register_name}: {result}")
                return False
            
            # Trigger immediate update
            await self.async_request_refresh()
            return True
            
        except Exception as ex:
            _LOGGER.error(f"Error writing register {register_name}: {ex}")
            return False
