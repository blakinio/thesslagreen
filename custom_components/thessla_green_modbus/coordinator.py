"""POPRAWIONY Data coordinator for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
FIX: Connection stability, error handling, transaction management
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    INPUT_REGISTERS,
    HOLDING_REGISTERS,
    COIL_REGISTERS,
    DISCRETE_INPUTS,
    ENTITY_MAPPINGS,
    SPECIAL_VALUES,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    CONF_RETRY,
    CONF_FORCE_FULL_REGISTER_LIST,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
)
from .device_scanner import ThesslaGreenDeviceScanner, DeviceCapabilities
from .modbus_client import ThesslaGreenModbusClient

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenModbusCoordinator(DataUpdateCoordinator):
    """POPRAWIONY Coordinator for managing ThesslaGreen Modbus device communication.
    
    Naprawione problemy:
    - Connection stability and error handling
    - Transaction ID management
    - Proper async/await patterns
    - Better diagnostics
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        name: str,
        scan_interval: timedelta,
        timeout: int = DEFAULT_TIMEOUT,
        retry: int = DEFAULT_RETRY,
        force_full_register_list: bool = False,
        entry_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}_{slave_id}",
            update_interval=scan_interval,
        )
        
        # Connection parameters
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        self.force_full_register_list = force_full_register_list
        
        # POPRAWKA: Używaj nowego client
        self.client: Optional[ThesslaGreenModbusClient] = None
        
        # Device info
        self.device_name = name
        self.device_info_data: Dict[str, Any] = {}
        
        # Register management
        self.available_registers: Dict[str, Dict[str, int]] = {
            "input": {},
            "holding": {},
            "coil": {},
            "discrete": {}
        }
        
        # Capabilities
        self.capabilities = DeviceCapabilities()
        
        # Connection tracking
        self.connection_errors = 0
        self.last_successful_read = None
        self.is_online = False
        
        # POPRAWKA: Initialize from scan result if available
        if entry_data:
            self._initialize_from_scan_result(entry_data)

    def _initialize_from_scan_result(self, entry_data: Dict[str, Any]) -> None:
        """POPRAWIONE: Initialize coordinator from scan result."""
        scan_result = entry_data.get("scan_result", {})
        device_info = entry_data.get("device_info", {})
        
        # Store device info
        self.device_info_data = device_info
        
        # Load available registers
        self.available_registers = scan_result.get("available_registers", {})
        
        # Convert capabilities dict back to object
        capabilities_dict = scan_result.get("capabilities", {})
        self.capabilities = DeviceCapabilities()
        for attr, value in capabilities_dict.items():
            if hasattr(self.capabilities, attr):
                setattr(self.capabilities, attr, value)
                
        _LOGGER.info(
            "Initialized from scan result: %d registers across %d types, %d capabilities",
            sum(len(regs) for regs in self.available_registers.values()),
            sum(1 for regs in self.available_registers.values() if regs),
            len([attr for attr in dir(self.capabilities) if not attr.startswith('_') and getattr(self.capabilities, attr)])
        )

    async def _async_setup_client(self) -> bool:
        """POPRAWIONE: Setup and test Modbus client connection."""
        try:
            # Clean up existing client
            if self.client:
                await self._async_close_client()

            # POPRAWKA: Użyj nowego client API
            self.client = ThesslaGreenModbusClient(
                host=self.host,
                port=self.port,
                slave_id=self.slave_id,
                timeout=max(self.timeout, 10)  # Minimum 10s timeout for operations
            )
            
            # Test connection
            if await self.client.connect():
                # Test with a simple read
                test_result = await self.client.read_input_registers(0x0000, 1)
                
                if test_result is not None:
                    _LOGGER.debug("Modbus client connected and tested successfully")
                    self.connection_errors = 0
                    self.is_online = True
                    return True
                else:
                    _LOGGER.warning("Connection test failed")
                    
            self.connection_errors += 1
            self.is_online = False
            return False
            
        except Exception as exc:
            _LOGGER.error("Failed to setup Modbus client: %s", exc)
            self.connection_errors += 1
            self.is_online = False
            return False

    async def _async_close_client(self) -> None:
        """POPRAWIONE: Close Modbus client connection."""
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as exc:
                _LOGGER.debug("Error closing client: %s", exc)
        self.client = None
        self.is_online = False

    async def _async_update_data(self) -> Dict[str, Any]:
        """POPRAWIONE: Fetch data from the Modbus device."""
        if not self.client or not self.client.is_connected:
            if not await self._async_setup_client():
                raise UpdateFailed(f"Could not connect to device at {self.host}:{self.port}")
        
        try:
            # POPRAWKA: Synchronous execution in executor
            data = await self.hass.async_add_executor_job(self._update_data_sync)
            
            if data:
                self.last_successful_read = datetime.now()
                self.connection_errors = 0
                self.is_online = True
                return data
            else:
                raise UpdateFailed("No data received from device")
                
        except Exception as exc:
            self.connection_errors += 1
            self.is_online = False
            
            if self.connection_errors > 3:
                # Try to reconnect after multiple failures
                await self._async_close_client()
                
            raise UpdateFailed(f"Error reading from device: {exc}")

    def _update_data_sync(self) -> Dict[str, Any]:
        """POPRAWIONE: Synchronous data update for executor."""
        data = {}
        
        try:
            # Read input registers
            for name, address in self.available_registers.get("input", {}).items():
                try:
                    result = asyncio.run_coroutine_threadsafe(
                        self.client.read_input_registers(address, 1),
                        self.hass.loop
                    ).result(timeout=self.timeout)
                    
                    if result is not None and len(result) > 0:
                        raw_value = result[0]
                        # Apply transformations based on register type
                        data[name] = self._transform_value(name, raw_value)
                        
                except Exception as exc:
                    _LOGGER.debug("Failed to read input register %s: %s", name, exc)
            
            # Read holding registers
            for name, address in self.available_registers.get("holding", {}).items():
                try:
                    result = asyncio.run_coroutine_threadsafe(
                        self.client.read_holding_registers(address, 1),
                        self.hass.loop
                    ).result(timeout=self.timeout)
                    
                    if result is not None and len(result) > 0:
                        raw_value = result[0]
                        data[name] = self._transform_value(name, raw_value)
                        
                except Exception as exc:
                    _LOGGER.debug("Failed to read holding register %s: %s", name, exc)
            
            # Read coils
            for name, address in self.available_registers.get("coil", {}).items():
                try:
                    result = asyncio.run_coroutine_threadsafe(
                        self.client.read_coils(address, 1),
                        self.hass.loop
                    ).result(timeout=self.timeout)
                    
                    if result is not None and len(result) > 0:
                        data[name] = bool(result[0])
                        
                except Exception as exc:
                    _LOGGER.debug("Failed to read coil %s: %s", name, exc)
            
            # Read discrete inputs
            for name, address in self.available_registers.get("discrete", {}).items():
                try:
                    result = asyncio.run_coroutine_threadsafe(
                        self.client.read_discrete_inputs(address, 1),
                        self.hass.loop
                    ).result(timeout=self.timeout)
                    
                    if result is not None and len(result) > 0:
                        data[name] = bool(result[0])
                        
                except Exception as exc:
                    _LOGGER.debug("Failed to read discrete input %s: %s", name, exc)
            
            _LOGGER.debug("Successfully read %d registers", len(data))
            return data
            
        except Exception as exc:
            _LOGGER.error("Error in synchronous data update: %s", exc)
            raise

    def _transform_value(self, register_name: str, raw_value: int) -> Union[int, float, str]:
        """POPRAWIONE: Transform raw register value to proper type."""
        try:
            # Check for special value mappings
            if register_name in SPECIAL_VALUES:
                special_map = SPECIAL_VALUES[register_name]
                if raw_value in special_map:
                    return special_map[raw_value]
            
            # Temperature transformations (typically need division by 10)
            if "temperature" in register_name:
                # Handle signed values for temperatures
                if raw_value > 32767:  # Handle signed 16-bit
                    raw_value = raw_value - 65536
                return raw_value / 10.0
            
            # Percentage values
            if "percentage" in register_name or "efficiency" in register_name:
                return raw_value
            
            # Flow rates (may need division)
            if "flowrate" in register_name:
                return raw_value
            
            # Default: return as integer
            return raw_value
            
        except Exception as exc:
            _LOGGER.debug("Error transforming value for %s: %s", register_name, exc)
            return raw_value

    async def async_write_register(self, register_name: str, value: Union[int, float, bool]) -> bool:
        """POPRAWIONE: Write value to register."""
        if not self.client or not self.client.is_connected:
            if not await self._async_setup_client():
                _LOGGER.error("Cannot write register %s: device not connected", register_name)
                return False
        
        try:
            # Find register address
            register_address = None
            register_type = None
            
            for reg_type, registers in self.available_registers.items():
                if register_name in registers:
                    register_address = registers[register_name]
                    register_type = reg_type
                    break
            
            if register_address is None:
                _LOGGER.error("Register %s not found in available registers", register_name)
                return False
            
            # Write based on register type
            if register_type == "holding":
                # Transform value if needed
                if isinstance(value, float) and "temperature" in register_name:
                    value = int(value * 10)  # Convert back to raw value
                elif isinstance(value, bool):
                    value = 1 if value else 0
                
                success = await self.client.write_register(register_address, int(value))
                
            elif register_type == "coil":
                success = await self.client.write_coil(register_address, bool(value))
                
            else:
                _LOGGER.error("Cannot write to %s register type", register_type)
                return False
            
            if success:
                _LOGGER.debug("Successfully wrote %s to register %s", value, register_name)
                # Trigger immediate update to reflect change
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to write %s to register %s", value, register_name)
                
            return success
            
        except Exception as exc:
            _LOGGER.error("Error writing register %s: %s", register_name, exc)
            return False

    async def async_write_multiple_registers(self, register_values: Dict[str, Union[int, float, bool]]) -> bool:
        """POPRAWIONE: Write multiple register values."""
        success_count = 0
        
        for register_name, value in register_values.items():
            if await self.async_write_register(register_name, value):
                success_count += 1
        
        return success_count == len(register_values)

    @property
    def device_info(self) -> DeviceInfo:
        """POPRAWIONE: Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.host}_{self.slave_id}")},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=self.device_info_data.get("model", MODEL),
            sw_version=self.device_info_data.get("firmware_version", "Unknown"),
            serial_number=self.device_info_data.get("serial_number"),
            configuration_url=f"http://{self.host}",
        )

    def get_entity_registry_data(self) -> Dict[str, Any]:
        """POPRAWIONE: Get data for entity registry."""
        return {
            "available_registers": self.available_registers,
            "capabilities": self.capabilities.to_dict(),
            "device_info": self.device_info_data,
            "connection_status": {
                "is_online": self.is_online,
                "connection_errors": self.connection_errors,
                "last_successful_read": self.last_successful_read.isoformat() if self.last_successful_read else None,
            }
        }

    async def async_shutdown(self) -> None:
        """POPRAWIONE: Shutdown coordinator and cleanup resources."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
        await self._async_close_client()