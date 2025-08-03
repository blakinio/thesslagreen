"""Modbus client for ThesslaGreen Integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenModbusClient:
    """ThesslaGreen Modbus TCP client."""

    def __init__(self, host: str, port: int, slave_id: int, timeout: int = 10) -> None:
        """Initialize the Modbus client."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self._client: ModbusTcpClient | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to Modbus device."""
        try:
            self._client = ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
            )
            return self._client.connect()
        except Exception as ex:
            _LOGGER.error("Failed to connect to Modbus device: %s", ex)
            return False

    async def disconnect(self) -> None:
        """Disconnect from Modbus device."""
        if self._client:
            self._client.close()
            self._client = None

    async def read_holding_register(self, address: int) -> int | None:
        """Read single holding register."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return None

                result = self._client.read_holding_registers(
                    address, 1, slave=self.slave_id
                )
                
                if result.isError():
                    _LOGGER.error("Error reading register %s: %s", address, result)
                    return None
                
                return result.registers[0]
                
            except ModbusException as ex:
                _LOGGER.error("Modbus exception reading register %s: %s", address, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading register %s: %s", address, ex)
                return None

    async def read_holding_registers(
        self, address: int, count: int
    ) -> list[int] | None:
        """Read multiple holding registers."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return None

                result = self._client.read_holding_registers(
                    address, count, slave=self.slave_id
                )
                
                if result.isError():
                    _LOGGER.error("Error reading registers %s-%s: %s", 
                                address, address + count - 1, result)
                    return None
                
                return result.registers
                
            except ModbusException as ex:
                _LOGGER.error("Modbus exception reading registers %s-%s: %s", 
                            address, address + count - 1, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading registers %s-%s: %s", 
                            address, address + count - 1, ex)
                return None

    async def write_register(self, address: int, value: int) -> bool:
        """Write single holding register."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return False

                result = self._client.write_register(
                    address, value, slave=self.slave_id
                )
                
                if result.isError():
                    _LOGGER.error("Error writing register %s: %s", address, result)
                    return False
                
                _LOGGER.debug("Successfully wrote value %s to register %s", value, address)
                return True
                
            except ModbusException as ex:
                _LOGGER.error("Modbus exception writing register %s: %s", address, ex)
                return False
            except Exception as ex:
                _LOGGER.error("Unexpected error writing register %s: %s", address, ex)
                return False

    async def write_registers(self, address: int, values: list[int]) -> bool:
        """Write multiple holding registers."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return False

                result = self._client.write_registers(
                    address, values, slave=self.slave_id
                )
                
                if result.isError():
                    _LOGGER.error("Error writing registers %s-%s: %s", 
                                address, address + len(values) - 1, result)
                    return False
                
                _LOGGER.debug("Successfully wrote %s values to registers %s-%s", 
                            len(values), address, address + len(values) - 1)
                return True
                
            except ModbusException as ex:
                _LOGGER.error("Modbus exception writing registers %s-%s: %s", 
                            address, address + len(values) - 1, ex)
                return False
            except Exception as ex:
                _LOGGER.error("Unexpected error writing registers %s-%s: %s", 
                            address, address + len(values) - 1, ex)
                return False