"""POPRAWIONY Modbus client dla ThesslaGreen Integration - kompatybilny z pymodbus 3.x+"""
from __future__ import annotations

import asyncio
import logging
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenModbusClient:
    """ThesslaGreen Modbus TCP client z poprawnym API pymodbus 3.x+"""

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
            return await asyncio.to_thread(self._client.connect)
        except Exception as ex:
            _LOGGER.error("Failed to connect to Modbus device: %s", ex)
            return False

    async def disconnect(self) -> None:
        """Disconnect from Modbus device."""
        if self._client:
            await asyncio.to_thread(self._client.close)
            self._client = None

    async def read_holding_register(self, address: int) -> int | None:
        """POPRAWIONE: Read single holding register z nowym API."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return None

                # POPRAWIONE API: keyword arguments
                result = await asyncio.to_thread(
                    self._client.read_holding_registers,
                    address=address,
                    count=1,
                    slave=self.slave_id,
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
        """POPRAWIONE: Read multiple holding registers z nowym API."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return None

                # POPRAWIONE API: keyword arguments
                result = await asyncio.to_thread(
                    self._client.read_holding_registers,
                    address=address,
                    count=count,
                    slave=self.slave_id,
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

    async def read_input_registers(
        self, address: int, count: int
    ) -> list[int] | None:
        """POPRAWIONE: Read input registers z nowym API."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return None

                # POPRAWIONE API: keyword arguments
                result = await asyncio.to_thread(
                    self._client.read_input_registers,
                    address=address,
                    count=count,
                    slave=self.slave_id,
                )
                
                if result.isError():
                    _LOGGER.error("Error reading input registers %s-%s: %s", 
                                address, address + count - 1, result)
                    return None
                
                return result.registers
                
            except ModbusException as ex:
                _LOGGER.error("Modbus exception reading input registers %s-%s: %s", 
                            address, address + count - 1, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading input registers %s-%s: %s", 
                            address, address + count - 1, ex)
                return None

    async def read_coils(self, address: int, count: int) -> list[bool] | None:
        """POPRAWIONE: Read coils z nowym API."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return None

                # POPRAWIONE API: keyword arguments
                result = await asyncio.to_thread(
                    self._client.read_coils,
                    address=address,
                    count=count,
                    slave=self.slave_id,
                )
                
                if result.isError():
                    _LOGGER.error("Error reading coils %s-%s: %s", 
                                address, address + count - 1, result)
                    return None
                
                return result.bits[:count]  # Trim to exact count
                
            except ModbusException as ex:
                _LOGGER.error("Modbus exception reading coils %s-%s: %s", 
                            address, address + count - 1, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading coils %s-%s: %s", 
                            address, address + count - 1, ex)
                return None

    async def read_discrete_inputs(self, address: int, count: int) -> list[bool] | None:
        """POPRAWIONE: Read discrete inputs z nowym API."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return None

                # POPRAWIONE API: keyword arguments
                result = await asyncio.to_thread(
                    self._client.read_discrete_inputs,
                    address=address,
                    count=count,
                    slave=self.slave_id,
                )
                
                if result.isError():
                    _LOGGER.error("Error reading discrete inputs %s-%s: %s", 
                                address, address + count - 1, result)
                    return None
                
                return result.bits[:count]  # Trim to exact count
                
            except ModbusException as ex:
                _LOGGER.error("Modbus exception reading discrete inputs %s-%s: %s", 
                            address, address + count - 1, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading discrete inputs %s-%s: %s", 
                            address, address + count - 1, ex)
                return None

    async def write_register(self, address: int, value: int) -> bool:
        """POPRAWIONE: Write single holding register z nowym API."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return False

                # POPRAWIONE API: keyword arguments
                result = await asyncio.to_thread(
                    self._client.write_register,
                    address=address,
                    value=value,
                    slave=self.slave_id,
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
        """POPRAWIONE: Write multiple holding registers z nowym API."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return False

                # POPRAWIONE API: keyword arguments
                result = await asyncio.to_thread(
                    self._client.write_registers,
                    address=address,
                    values=values,
                    slave=self.slave_id,
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

    async def write_coil(self, address: int, value: bool) -> bool:
        """POPRAWIONE: Write single coil z nowym API."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return False

                # POPRAWIONE API: keyword arguments
                result = await asyncio.to_thread(
                    self._client.write_coil,
                    address=address,
                    value=value,
                    slave=self.slave_id,
                )
                
                if result.isError():
                    _LOGGER.error("Error writing coil %s: %s", address, result)
                    return False
                
                _LOGGER.debug("Successfully wrote value %s to coil %s", value, address)
                return True
                
            except ModbusException as ex:
                _LOGGER.error("Modbus exception writing coil %s: %s", address, ex)
                return False
            except Exception as ex:
                _LOGGER.error("Unexpected error writing coil %s: %s", address, ex)
                return False

    async def write_coils(self, address: int, values: list[bool]) -> bool:
        """POPRAWIONE: Write multiple coils z nowym API."""
        async with self._lock:
            try:
                if not self._client or not self._client.connected:
                    if not await self.connect():
                        return False

                # POPRAWIONE API: keyword arguments
                result = await asyncio.to_thread(
                    self._client.write_coils,
                    address=address,
                    values=values,
                    slave=self.slave_id,
                )
                
                if result.isError():
                    _LOGGER.error("Error writing coils %s-%s: %s", 
                                address, address + len(values) - 1, result)
                    return False
                
                _LOGGER.debug("Successfully wrote %s values to coils %s-%s", 
                            len(values), address, address + len(values) - 1)
                return True
                
            except ModbusException as ex:
                _LOGGER.error("Modbus exception writing coils %s-%s: %s", 
                            address, address + len(values) - 1, ex)
                return False
            except Exception as ex:
                _LOGGER.error("Unexpected error writing coils %s-%s: %s", 
                            address, address + len(values) - 1, ex)
                return False

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None and self._client.connected
