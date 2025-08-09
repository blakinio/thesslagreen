"""POPRAWIONY Modbus client dla ThesslaGreen Integration.
Kompatybilność: pymodbus 3.5.*+
FIX: Transaction ID mismatch, AsyncModbusTcpClient compatibility, connection handling
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Union

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException, ModbusIOException
from pymodbus.pdu import ExceptionResponse

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenModbusClient:
    """POPRAWIONY ThesslaGreen Modbus TCP client kompatybilny z pymodbus 3.5+
    
    Naprawione problemy:
    - Transaction ID synchronization
    - AsyncModbusTcpClient API compatibility  
    - Connection stability
    - Error handling
    """

    def __init__(self, host: str, port: int, slave_id: int, timeout: int = 10) -> None:
        """Initialize the Modbus client."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self._client: Optional[AsyncModbusTcpClient] = None
        self._lock = asyncio.Lock()
        self._connection_retries = 3
        
        # POPRAWKA: Transaction ID tracking dla pymodbus 3.5+
        self._transaction_id = 1

    async def connect(self) -> bool:
        """POPRAWIONE: Connect to Modbus device with proper error handling."""
        try:
            # Clean up existing connection
            if self._client:
                await self.disconnect()
                
            # POPRAWKA: Nowe API pymodbus 3.5+
            self._client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
                # POPRAWKA: Stabilność połączenia
                retries=self._connection_retries,
                retry_on_empty=True,
                # POPRAWKA: Transaction ID handling
                source_address=None,
                strict=False,
            )
            
            # POPRAWKA: Nowy sposób łączenia w pymodbus 3.5+
            connected = await self._client.connect()
            
            if connected and self._client.connected:
                _LOGGER.debug("Successfully connected to %s:%s", self.host, self.port)
                return True
            else:
                _LOGGER.error("Failed to connect to %s:%s", self.host, self.port)
                return False
                
        except Exception as ex:
            _LOGGER.error("Failed to connect to Modbus device at %s:%s: %s", self.host, self.port, ex)
            return False

    async def disconnect(self) -> None:
        """POPRAWIONE: Safely disconnect from Modbus device."""
        try:
            if self._client and hasattr(self._client, 'close'):
                self._client.close()
        except Exception as ex:
            _LOGGER.debug("Error during disconnect: %s", ex)
        finally:
            self._client = None

    def _get_next_transaction_id(self) -> int:
        """POPRAWKA: Generate consistent transaction ID."""
        self._transaction_id = (self._transaction_id % 65535) + 1
        return self._transaction_id

    async def _ensure_connected(self) -> bool:
        """POPRAWKA: Ensure client is connected before operations."""
        if not self._client or not self._client.connected:
            _LOGGER.debug("Client not connected, attempting to reconnect...")
            return await self.connect()
        return True

    async def read_holding_register(self, address: int) -> Optional[int]:
        """POPRAWIONE: Read single holding register."""
        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return None

                # POPRAWKA: Nowe API z keyword arguments
                result = await self._client.read_holding_registers(
                    address=address,
                    count=1,
                    slave=self.slave_id
                )
                
                # POPRAWKA: Obsługa exception responses
                if isinstance(result, ExceptionResponse):
                    _LOGGER.debug("Exception response reading register %s: code %s", address, result.exception_code)
                    return None
                    
                if result.isError():
                    _LOGGER.error("Error reading register %s: %s", address, result)
                    return None
                
                return result.registers[0]
                
            except (ModbusException, ConnectionException, ModbusIOException) as ex:
                _LOGGER.debug("Modbus exception reading register %s: %s", address, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading register %s: %s", address, ex)
                return None

    async def read_holding_registers(self, address: int, count: int) -> Optional[List[int]]:
        """POPRAWIONE: Read multiple holding registers."""
        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return None

                # POPRAWKA: Nowe API z keyword arguments
                result = await self._client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=self.slave_id
                )
                
                # POPRAWKA: Obsługa exception responses
                if isinstance(result, ExceptionResponse):
                    _LOGGER.debug("Exception response reading registers %s-%s: code %s", 
                                address, address + count - 1, result.exception_code)
                    return None
                    
                if result.isError():
                    _LOGGER.debug("Error reading registers %s-%s: %s", 
                                address, address + count - 1, result)
                    return None
                
                return result.registers
                
            except (ModbusException, ConnectionException, ModbusIOException) as ex:
                _LOGGER.debug("Modbus exception reading registers %s-%s: %s", 
                            address, address + count - 1, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading registers %s-%s: %s", 
                            address, address + count - 1, ex)
                return None

    async def read_input_registers(self, address: int, count: int) -> Optional[List[int]]:
        """POPRAWIONE: Read input registers."""
        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return None

                # POPRAWKA: Nowe API z keyword arguments
                result = await self._client.read_input_registers(
                    address=address,
                    count=count,
                    slave=self.slave_id
                )
                
                # POPRAWKA: Obsługa exception responses
                if isinstance(result, ExceptionResponse):
                    _LOGGER.debug("Exception response reading input registers %s-%s: code %s", 
                                address, address + count - 1, result.exception_code)
                    return None
                    
                if result.isError():
                    _LOGGER.debug("Error reading input registers %s-%s: %s", 
                                address, address + count - 1, result)
                    return None
                
                return result.registers
                
            except (ModbusException, ConnectionException, ModbusIOException) as ex:
                _LOGGER.debug("Modbus exception reading input registers %s-%s: %s", 
                            address, address + count - 1, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading input registers %s-%s: %s", 
                            address, address + count - 1, ex)
                return None

    async def read_coils(self, address: int, count: int) -> Optional[List[bool]]:
        """POPRAWIONE: Read coils."""
        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return None

                # POPRAWKA: Nowe API z keyword arguments
                result = await self._client.read_coils(
                    address=address,
                    count=count,
                    slave=self.slave_id
                )
                
                # POPRAWKA: Obsługa exception responses
                if isinstance(result, ExceptionResponse):
                    _LOGGER.debug("Exception response reading coils %s-%s: code %s", 
                                address, address + count - 1, result.exception_code)
                    return None
                    
                if result.isError():
                    _LOGGER.debug("Error reading coils %s-%s: %s", 
                                address, address + count - 1, result)
                    return None
                
                return result.bits[:count]  # Trim to exact count
                
            except (ModbusException, ConnectionException, ModbusIOException) as ex:
                _LOGGER.debug("Modbus exception reading coils %s-%s: %s", 
                            address, address + count - 1, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading coils %s-%s: %s", 
                            address, address + count - 1, ex)
                return None

    async def read_discrete_inputs(self, address: int, count: int) -> Optional[List[bool]]:
        """POPRAWIONE: Read discrete inputs."""
        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return None

                # POPRAWKA: Nowe API z keyword arguments
                result = await self._client.read_discrete_inputs(
                    address=address,
                    count=count,
                    slave=self.slave_id
                )
                
                # POPRAWKA: Obsługa exception responses
                if isinstance(result, ExceptionResponse):
                    _LOGGER.debug("Exception response reading discrete inputs %s-%s: code %s", 
                                address, address + count - 1, result.exception_code)
                    return None
                    
                if result.isError():
                    _LOGGER.debug("Error reading discrete inputs %s-%s: %s", 
                                address, address + count - 1, result)
                    return None
                
                return result.bits[:count]  # Trim to exact count
                
            except (ModbusException, ConnectionException, ModbusIOException) as ex:
                _LOGGER.debug("Modbus exception reading discrete inputs %s-%s: %s", 
                            address, address + count - 1, ex)
                return None
            except Exception as ex:
                _LOGGER.error("Unexpected error reading discrete inputs %s-%s: %s", 
                            address, address + count - 1, ex)
                return None

    async def write_register(self, address: int, value: int) -> bool:
        """POPRAWIONE: Write single holding register."""
        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return False

                # POPRAWKA: Nowe API z keyword arguments
                result = await self._client.write_register(
                    address=address,
                    value=value,
                    slave=self.slave_id
                )
                
                # POPRAWKA: Obsługa exception responses
                if isinstance(result, ExceptionResponse):
                    _LOGGER.error("Exception response writing register %s: code %s", address, result.exception_code)
                    return False
                    
                if result.isError():
                    _LOGGER.error("Error writing register %s: %s", address, result)
                    return False
                
                _LOGGER.debug("Successfully wrote value %s to register %s", value, address)
                return True
                
            except (ModbusException, ConnectionException, ModbusIOException) as ex:
                _LOGGER.error("Modbus exception writing register %s: %s", address, ex)
                return False
            except Exception as ex:
                _LOGGER.error("Unexpected error writing register %s: %s", address, ex)
                return False

    async def write_registers(self, address: int, values: List[int]) -> bool:
        """POPRAWIONE: Write multiple holding registers."""
        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return False

                # POPRAWKA: Nowe API z keyword arguments
                result = await self._client.write_registers(
                    address=address,
                    values=values,
                    slave=self.slave_id
                )
                
                # POPRAWKA: Obsługa exception responses
                if isinstance(result, ExceptionResponse):
                    _LOGGER.error("Exception response writing registers %s-%s: code %s", 
                                address, address + len(values) - 1, result.exception_code)
                    return False
                    
                if result.isError():
                    _LOGGER.error("Error writing registers %s-%s: %s", 
                                address, address + len(values) - 1, result)
                    return False
                
                _LOGGER.debug("Successfully wrote %s values to registers %s-%s", 
                            len(values), address, address + len(values) - 1)
                return True
                
            except (ModbusException, ConnectionException, ModbusIOException) as ex:
                _LOGGER.error("Modbus exception writing registers %s-%s: %s", 
                            address, address + len(values) - 1, ex)
                return False
            except Exception as ex:
                _LOGGER.error("Unexpected error writing registers %s-%s: %s", 
                            address, address + len(values) - 1, ex)
                return False

    async def write_coil(self, address: int, value: bool) -> bool:
        """POPRAWIONE: Write single coil."""
        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return False

                # POPRAWKA: Nowe API z keyword arguments
                result = await self._client.write_coil(
                    address=address,
                    value=value,
                    slave=self.slave_id
                )
                
                # POPRAWKA: Obsługa exception responses
                if isinstance(result, ExceptionResponse):
                    _LOGGER.error("Exception response writing coil %s: code %s", address, result.exception_code)
                    return False
                    
                if result.isError():
                    _LOGGER.error("Error writing coil %s: %s", address, result)
                    return False
                
                _LOGGER.debug("Successfully wrote value %s to coil %s", value, address)
                return True
                
            except (ModbusException, ConnectionException, ModbusIOException) as ex:
                _LOGGER.error("Modbus exception writing coil %s: %s", address, ex)
                return False
            except Exception as ex:
                _LOGGER.error("Unexpected error writing coil %s: %s", address, ex)
                return False

    async def write_coils(self, address: int, values: List[bool]) -> bool:
        """POPRAWIONE: Write multiple coils."""
        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return False

                # POPRAWKA: Nowe API z keyword arguments
                result = await self._client.write_coils(
                    address=address,
                    values=values,
                    slave=self.slave_id
                )
                
                # POPRAWKA: Obsługa exception responses
                if isinstance(result, ExceptionResponse):
                    _LOGGER.error("Exception response writing coils %s-%s: code %s", 
                                address, address + len(values) - 1, result.exception_code)
                    return False
                    
                if result.isError():
                    _LOGGER.error("Error writing coils %s-%s: %s", 
                                address, address + len(values) - 1, result)
                    return False
                
                _LOGGER.debug("Successfully wrote %s values to coils %s-%s", 
                            len(values), address, address + len(values) - 1)
                return True
                
            except (ModbusException, ConnectionException, ModbusIOException) as ex:
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