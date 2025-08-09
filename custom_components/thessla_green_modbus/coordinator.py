"""Data coordinator for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
Zarządza komunikacją i danymi z urządzenia ThesslaGreen AirPack
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ModbusException, ConnectionException

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

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenModbusCoordinator(DataUpdateCoordinator):
    """Coordinator for managing ThesslaGreen Modbus device communication."""

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
            name=f"{DOMAIN}_{name}",
            update_interval=scan_interval,
        )
        
        # Connection parameters
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.device_name = name
        self.timeout = timeout
        self.retry = retry
        self.force_full_register_list = force_full_register_list
        
        # Modbus client
        self.client: Optional[AsyncModbusTcpClient] = None
        
        # Device information and capabilities
        self.device_info: Dict[str, Any] = {}
        self.capabilities = DeviceCapabilities()
        self.available_registers: Dict[str, Dict[str, int]] = {
            "input": {},
            "holding": {},
            "coil": {},
            "discrete": {}
        }
        
        # Operational data
        self.data: Dict[str, Any] = {}
        self.last_successful_update: Optional[datetime] = None
        self.connection_errors = 0
        self.consecutive_failures = 0
        
        # Performance tracking
        self.update_duration_ms = 0
        self.registers_read_count = 0
        self.error_log: List[Dict[str, Any]] = []
        
        # Initialize from entry data if provided (from config flow scan)
        if entry_data and "scan_result" in entry_data:
            self._initialize_from_scan_result(entry_data["scan_result"])
            self.device_info = entry_data.get("device_info", {})
            
        _LOGGER.debug(
            "Coordinator initialized for %s at %s:%s (slave_id=%s, scan_interval=%s)",
            name, host, port, slave_id, scan_interval
        )

    def _initialize_from_scan_result(self, scan_result: Dict[str, Any]) -> None:
        """Initialize coordinator with results from device scan."""
        if "available_registers" in scan_result:
            self.available_registers = scan_result["available_registers"]
        
        if "capabilities" in scan_result:
            capabilities_data = scan_result["capabilities"]
            self.capabilities = DeviceCapabilities(
                has_temperature_sensors=capabilities_data.get("has_temperature_sensors", False),
                has_flow_sensors=capabilities_data.get("has_flow_sensors", False),
                has_gwc=capabilities_data.get("has_gwc", False),
                has_bypass=capabilities_data.get("has_bypass", False),
                has_heating=capabilities_data.get("has_heating", False),
                has_air_quality=capabilities_data.get("has_air_quality", False),
                has_scheduling=capabilities_data.get("has_scheduling", False),
            )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from device."""
        start_time = datetime.now()
        
        try:
            data = await self._read_device_data()
            
            # Update performance metrics
            self.update_duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self.last_successful_update = datetime.now()
            self.consecutive_failures = 0
            
            _LOGGER.debug("Successfully updated data in %dms", self.update_duration_ms)
            return data
            
        except Exception as err:
            self.consecutive_failures += 1
            self._log_error("update_failed", str(err))
            _LOGGER.error("Failed to update data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def _read_device_data(self) -> Dict[str, Any]:
        """Read all available registers from device."""
        data = {}
        
        if not self.client:
            self.client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
        
        try:
            if not await self.client.connect():
                raise ConnectionError(f"Failed to connect to {self.host}:{self.port}")
            
            # Read input registers
            await self._read_register_batch(data, "input", INPUT_REGISTERS)
            
            # Read holding registers  
            await self._read_register_batch(data, "holding", HOLDING_REGISTERS)
            
            # Read coils
            await self._read_register_batch(data, "coil", COIL_REGISTERS)
            
            # Read discrete inputs
            await self._read_register_batch(data, "discrete", DISCRETE_INPUTS)
            
            self.registers_read_count = len(data)
            _LOGGER.debug("Successfully read %d registers", self.registers_read_count)
            
        finally:
            if self.client:
                self.client.close()
        
        return data

    async def _read_register_batch(self, data: Dict[str, Any], register_type: str, registers: Dict[str, int]) -> None:
        """Read a batch of registers of specified type."""
        if register_type not in self.available_registers:
            return
            
        available = self.available_registers[register_type]
        if not available and not self.force_full_register_list:
            return
        
        # Determine which registers to read
        registers_to_read = available if available else registers
        
        for reg_name, reg_addr in registers_to_read.items():
            try:
                if register_type == "input":
                    response = await self.client.read_input_registers(reg_addr, 1, slave=self.slave_id)
                elif register_type == "holding":
                    response = await self.client.read_holding_registers(reg_addr, 1, slave=self.slave_id)
                elif register_type == "coil":
                    response = await self.client.read_coils(reg_addr, 1, slave=self.slave_id)
                elif register_type == "discrete":
                    response = await self.client.read_discrete_inputs(reg_addr, 1, slave=self.slave_id)
                else:
                    continue
                
                if response.isError():
                    _LOGGER.debug("Error reading register %s: %s", reg_name, response)
                    continue
                
                # Extract value
                if register_type in ["input", "holding"]:
                    raw_value = response.registers[0] if response.registers else 0
                else:  # coil, discrete
                    raw_value = response.bits[0] if response.bits else False
                
                # Process value
                processed_value = self._process_register_value(reg_name, raw_value)
                if processed_value is not None:
                    data[reg_name] = processed_value
                    
            except Exception as err:
                _LOGGER.debug("Failed to read register %s: %s", reg_name, err)
                continue

    def _process_register_value(self, register_name: str, raw_value: Any) -> Any:
        """Process raw register value."""
        # Check for special values
        if raw_value in SPECIAL_VALUES:
            return None
            
        # Apply entity-specific processing
        for entity_type, entities in ENTITY_MAPPINGS.items():
            if register_name in entities:
                entity_config = entities[register_name]
                
                # Apply scale factor
                if "scale" in entity_config:
                    return raw_value * entity_config["scale"]
                    
                # Check for invalid values
                if "invalid_value" in entity_config and raw_value == entity_config["invalid_value"]:
                    return None
                    
                break
                
        return raw_value

    def _log_error(self, error_type: str, message: str, details: Optional[Dict] = None):
        """Log error with timestamp and details."""
        error_entry = {
            "timestamp": datetime.now(),
            "type": error_type,
            "message": message,
            "details": details or {}
        }
        self.error_log.append(error_entry)
        
        # Keep only last 50 errors
        if len(self.error_log) > 50:
            self.error_log = self.error_log[-50:]

    def get_device_info(self) -> DeviceInfo:
        """Return device information for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.host}_{self.slave_id}")},
            name=self.device_info.get("device_name", self.device_name),
            manufacturer=MANUFACTURER,
            model=self.device_info.get("model", MODEL),
            sw_version=self.device_info.get("firmware", "Unknown"),
            serial_number=self.device_info.get("serial_number"),
            configuration_url=f"http://{self.host}",
        )

    def get_register_count(self) -> int:
        """Get total number of available registers."""
        return sum(len(regs) for regs in self.available_registers.values())

    def get_capabilities_summary(self) -> List[str]:
        """Get list of detected capabilities."""
        capabilities = []
        if self.capabilities.has_temperature_sensors:
            capabilities.append("Temperature Sensors")
        if self.capabilities.has_flow_sensors:
            capabilities.append("Flow Control")
        if self.capabilities.has_gwc:
            capabilities.append("GWC")
        if self.capabilities.has_bypass:
            capabilities.append("Bypass")
        if self.capabilities.has_heating:
            capabilities.append("Heating")
        if self.capabilities.has_air_quality:
            capabilities.append("Air Quality")
        if self.capabilities.has_scheduling:
            capabilities.append("Scheduling")
        return capabilities

    def has_entities_for_platform(self, platform: str) -> bool:
        """Check if platform has any available entities."""
        platform_mappings = ENTITY_MAPPINGS.get(platform, {})
        if not platform_mappings:
            return False
        
        # Check if any register for this platform is available
        for register_name in platform_mappings:
            for reg_type, registers in self.available_registers.items():
                if register_name in registers:
                    return True
            
            # Check force full register list
            if self.force_full_register_list:
                all_registers = {**INPUT_REGISTERS, **HOLDING_REGISTERS, **COIL_REGISTERS, **DISCRETE_INPUTS}
                if register_name in all_registers:
                    return True
        
        return False

    async def async_write_register(self, register_name: str, value: Any) -> bool:
        """Write value to a register."""
        # Check if register is writable
        if register_name not in HOLDING_REGISTERS and register_name not in COIL_REGISTERS:
            _LOGGER.error("Register %s is not writable", register_name)
            return False
        
        if not self.client:
            self.client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
        
        try:
            if not await self.client.connect():
                raise ConnectionError(f"Failed to connect to {self.host}:{self.port}")
            
            if register_name in HOLDING_REGISTERS:
                reg_addr = HOLDING_REGISTERS[register_name]
                response = await self.client.write_register(reg_addr, value, slave=self.slave_id)
            elif register_name in COIL_REGISTERS:
                reg_addr = COIL_REGISTERS[register_name]
                response = await self.client.write_coil(reg_addr, bool(value), slave=self.slave_id)
            else:
                return False
            
            if response.isError():
                _LOGGER.error("Error writing to register %s: %s", register_name, response)
                return False
            
            # Request refresh to update data
            await self.async_request_refresh()
            _LOGGER.debug("Successfully wrote %s = %s", register_name, value)
            return True
            
        except Exception as err:
            _LOGGER.error("Failed to write register %s: %s", register_name, err)
            return False
        finally:
            if self.client:
                self.client.close()

    async def async_update_options(
        self,
        scan_interval: timedelta,
        timeout: int,
        retry: int,
        force_full_register_list: bool,
    ) -> None:
        """Update coordinator options."""
        self.update_interval = scan_interval
        self.timeout = timeout
        self.retry = retry
        self.force_full_register_list = force_full_register_list
        
        _LOGGER.debug("Updated coordinator options")

    async def async_shutdown(self) -> None:
        """Shutdown coordinator."""
        if self.client:
            self.client.close()
        _LOGGER.debug("Coordinator shutdown complete")

    def get_diagnostic_data(self) -> Dict[str, Any]:
        """Get diagnostic data for debugging."""
        return {
            "connection": {
                "host": self.host,
                "port": self.port,
                "slave_id": self.slave_id,
                "timeout": self.timeout,
                "retry": self.retry,
            },
            "device_info": self.device_info,
            "performance": {
                "update_duration_ms": self.update_duration_ms,
                "registers_read_count": self.registers_read_count,
                "consecutive_failures": self.consecutive_failures,
                "last_successful_update": self.last_successful_update.isoformat() if self.last_successful_update else None,
            },
            "capabilities": {
                "has_temperature_sensors": self.capabilities.has_temperature_sensors,
                "has_flow_sensors": self.capabilities.has_flow_sensors,
                "has_gwc": self.capabilities.has_gwc,
                "has_bypass": self.capabilities.has_bypass,
                "has_heating": self.capabilities.has_heating,
                "has_air_quality": self.capabilities.has_air_quality,
                "has_scheduling": self.capabilities.has_scheduling,
            },
            "available_registers": {
                reg_type: list(registers.keys()) for reg_type, registers in self.available_registers.items()
            },
            "current_data": dict(self.data),
            "recent_errors": self.error_log[-10:] if self.error_log else [],
        }