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
        """Setup and test Modbus client connection."""
        try:
            # Clean up existing client
            if self.client:
                await self._async_close_client()

            # Create new client - pymodbus 3.5+ compatible
            self.client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=max(self.timeout, 10)  # Minimum 10s timeout for operations
            )
            
            # Connect with retries
            for attempt in range(self.retry):
                try:
                    await self.client.connect()
                    
                    if self.client.connected:
                        # Test connection with a simple read
                        test_response = await self.client.read_input_registers(
                            address=0x0000, count=1, slave=self.slave_id
                        )
                        
                        if not test_response.isError():
                            _LOGGER.debug("Modbus client connected and tested successfully")
                            self.connection_errors = 0
                            return True
                        else:
                            _LOGGER.warning("Connection test failed: %s", test_response)
                            
                except Exception as exc:
                    _LOGGER.warning("Connection attempt %d failed: %s", attempt + 1, exc)
                    if attempt < self.retry - 1:
                        await asyncio.sleep(1)
                        
            self.connection_errors += 1
            return False
            
        except Exception as exc:
            _LOGGER.error("Failed to setup Modbus client: %s", exc)
            self.connection_errors += 1
            return False

    async def _async_close_client(self) -> None:
        """Close Modbus client connection."""
        if self.client and hasattr(self.client, 'close'):
            try:
                if self.client.connected:
                    self.client.close()
            except Exception as exc:
                _LOGGER.debug("Error closing client: %s", exc)
        self.client = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the Modbus device."""
        update_start = datetime.now()
        
        try:
            # Ensure client is connected
            if not self.client or not self.client.connected:
                if not await self._async_setup_client():
                    raise UpdateFailed("Failed to connect to Modbus device")

            # If no registers were scanned yet, perform scan now
            if not any(self.available_registers.values()) and not self.force_full_register_list:
                await self._async_scan_device()

            # Read available data
            new_data = {}
            
            # Read input registers
            if self.available_registers["input"] or self.force_full_register_list:
                input_data = await self._async_read_register_type("input")
                new_data.update(input_data)

            # Read holding registers
            if self.available_registers["holding"] or self.force_full_register_list:
                holding_data = await self._async_read_register_type("holding")
                new_data.update(holding_data)

            # Read coil registers
            if self.available_registers["coil"] or self.force_full_register_list:
                coil_data = await self._async_read_register_type("coil")
                new_data.update(coil_data)

            # Read discrete inputs
            if self.available_registers["discrete"] or self.force_full_register_list:
                discrete_data = await self._async_read_register_type("discrete")
                new_data.update(discrete_data)

            # Update statistics
            self.update_duration_ms = int((datetime.now() - update_start).total_seconds() * 1000)
            self.registers_read_count = len(new_data)
            self.last_successful_update = datetime.now()
            self.consecutive_failures = 0

            _LOGGER.debug(
                "Data update successful: %d registers read in %dms",
                self.registers_read_count, self.update_duration_ms
            )

            return new_data

        except Exception as exc:
            self.consecutive_failures += 1
            self._log_error("update_failed", f"Data update failed: {exc}")
            
            # Try to reconnect on persistent failures
            if self.consecutive_failures >= 3:
                _LOGGER.warning("Multiple consecutive failures, attempting reconnect")
                await self._async_close_client()

            raise UpdateFailed(f"Failed to update data: {exc}")

    async def _async_scan_device(self) -> None:
        """Perform device scan to detect available registers."""
        _LOGGER.info("Performing device scan to detect available registers")
        
        scanner = ThesslaGreenDeviceScanner(
            host=self.host,
            port=self.port,
            slave_id=self.slave_id,
            timeout=self.timeout,
            retry=self.retry
        )
        
        try:
            scan_result = await scanner.scan_device()
            
            if scan_result:
                self.available_registers = scan_result["available_registers"]
                
                # Update capabilities
                capabilities_dict = scan_result.get("capabilities", {})
                for attr, value in capabilities_dict.items():
                    if hasattr(self.capabilities, attr):
                        setattr(self.capabilities, attr, value)
                
                # Update device info if not already set
                if not self.device_info:
                    self.device_info = scan_result["device_info"]
                
                total_registers = sum(len(regs) for regs in self.available_registers.values())
                _LOGGER.info("Device scan completed: %d registers found", total_registers)
            else:
                _LOGGER.warning("Device scan failed - using full register list")
                self.force_full_register_list = True
                
        except Exception as exc:
            _LOGGER.warning("Device scan error: %s - falling back to full register list", exc)
            self.force_full_register_list = True

    async def _async_read_register_type(self, register_type: str) -> Dict[str, Any]:
        """Read registers of specific type."""
        data = {}
        
        if not self.client or not self.client.connected:
            return data

        # Get register map and available registers
        if register_type == "input":
            register_map = INPUT_REGISTERS
            available = self.available_registers["input"] if not self.force_full_register_list else register_map
        elif register_type == "holding":
            register_map = HOLDING_REGISTERS
            available = self.available_registers["holding"] if not self.force_full_register_list else register_map
        elif register_type == "coil":
            register_map = COIL_REGISTERS
            available = self.available_registers["coil"] if not self.force_full_register_list else register_map
        elif register_type == "discrete":
            register_map = DISCRETE_INPUTS
            available = self.available_registers["discrete"] if not self.force_full_register_list else register_map
        else:
            return data

        # Read registers in optimized groups
        for reg_name, reg_address in available.items():
            if reg_name not in register_map:
                continue
                
            try:
                # Read single register - pymodbus 3.5+ compatible API with timeout
                if register_type == "input":
                    response = await asyncio.wait_for(
                        self.client.read_input_registers(address=reg_address, count=1, slave=self.slave_id),
                        timeout=self.timeout
                    )
                elif register_type == "holding":
                    response = await asyncio.wait_for(
                        self.client.read_holding_registers(address=reg_address, count=1, slave=self.slave_id),
                        timeout=self.timeout
                    )
                elif register_type == "coil":
                    response = await asyncio.wait_for(
                        self.client.read_coils(address=reg_address, count=1, slave=self.slave_id),
                        timeout=self.timeout
                    )
                elif register_type == "discrete":
                    response = await asyncio.wait_for(
                        self.client.read_discrete_inputs(address=reg_address, count=1, slave=self.slave_id),
                        timeout=self.timeout
                    )

                if response and not response.isError():
                    if hasattr(response, 'registers') and response.registers:
                        raw_value = response.registers[0]
                    elif hasattr(response, 'bits') and response.bits:
                        # For coil/discrete inputs, use first bit
                        raw_value = response.bits[0] if len(response.bits) > 0 else 0
                    else:
                        _LOGGER.debug("No valid response data for %s register %s", register_type, reg_name)
                        continue
                        
                    # Process value according to entity mapping
                    processed_value = self._process_register_value(reg_name, raw_value)
                    data[reg_name] = processed_value
                    
            except asyncio.TimeoutError:
                _LOGGER.debug("Timeout reading %s register %s", register_type, reg_name)
                continue
            except Exception as exc:
                _LOGGER.debug("Failed to read %s register %s: %s", register_type, reg_name, exc)
                continue

        return data

    def _process_register_value(self, register_name: str, raw_value: int) -> Any:
        """Process raw register value according to entity configuration."""
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
        if platform not in ENTITY_MAPPINGS:
            # Special handling for platforms not in ENTITY_MAPPINGS
            if platform == "climate":
                # Climate needs mode and temperature control registers
                climate_registers = ["mode", "supply_temperature_manual", "supply_temperature_auto", "comfort_temperature"]
                for register_name in climate_registers:
                    for register_type_regs in self.available_registers.values():
                        if register_name in register_type_regs:
                            _LOGGER.debug("Climate platform: found register %s", register_name)
                            return True
                
                # Check force full register list
                if self.force_full_register_list:
                    for register_name in climate_registers:
                        if register_name in HOLDING_REGISTERS:
                            _LOGGER.debug("Climate platform: force full - found register %s", register_name)
                            return True
                            
                return False
                
            elif platform == "fan":
                # Fan needs flow rate control registers
                fan_registers = ["air_flow_rate_manual", "air_flow_rate_auto", "supply_percentage", "air_flow_rate"]
                for register_name in fan_registers:
                    for register_type_regs in self.available_registers.values():
                        if register_name in register_type_regs:
                            _LOGGER.debug("Fan platform: found register %s", register_name)
                            return True
                
                # Check force full register list  
                if self.force_full_register_list:
                    for register_name in fan_registers[:2]:  # Only check writable ones
                        if register_name in HOLDING_REGISTERS:
                            _LOGGER.debug("Fan platform: force full - found register %s", register_name)
                            return True
                            
                return False
                
            elif platform == "switch":
                # Switch needs some control registers
                switch_registers = ["on_off_panel_mode", "boost_mode", "eco_mode", "night_mode"]
                for register_name in switch_registers:
                    if register_name in self.available_registers.get("holding", {}):
                        _LOGGER.debug("Switch platform: found register %s", register_name)
                        return True
                        
                # Check force full register list
                if self.force_full_register_list:
                    for register_name in switch_registers:
                        if register_name in HOLDING_REGISTERS:
                            _LOGGER.debug("Switch platform: force full - found register %s", register_name)
                            return True
                            
                return False
            
            return False
            
        platform_entities = ENTITY_MAPPINGS[platform]
        
        # Check if any entities for this platform are available
        for entity_name in platform_entities:
            for register_type_regs in self.available_registers.values():
                if entity_name in register_type_regs:
                    _LOGGER.debug("Platform %s: found entity %s", platform, entity_name)
                    return True
                    
        # If force full register list, check against all possible registers
        if self.force_full_register_list:
            all_registers = {**INPUT_REGISTERS, **HOLDING_REGISTERS, **COIL_REGISTERS, **DISCRETE_INPUTS}
            for entity_name in platform_entities:
                if entity_name in all_registers:
                    _LOGGER.debug("Platform %s: force full - found entity %s", platform, entity_name)
                    return True
                    
        return False

    def get_diagnostic_data(self) -> Dict[str, Any]:
        """Get diagnostic information for troubleshooting."""
        return {
            "device_info": self.device_info,
            "connection": {
                "host": self.host,
                "port": self.port,
                "slave_id": self.slave_id,
                "connected": self.client.connected if self.client else False,
                "connection_errors": self.connection_errors,
                "consecutive_failures": self.consecutive_failures,
            },
            "performance": {
                "last_update": self.last_successful_update.isoformat() if self.last_successful_update else None,
                "update_duration_ms": self.update_duration_ms,
                "registers_read_count": self.registers_read_count,
            },
            "capabilities": self.capabilities.to_dict(),
            "available_registers": {
                reg_type: list(regs.keys()) 
                for reg_type, regs in self.available_registers.items()
            },
            "register_statistics": {
                reg_type: len(regs) 
                for reg_type, regs in self.available_registers.items()
            },
            "recent_errors": self.error_log[-10:] if self.error_log else [],
            "configuration": {
                "timeout": self.timeout,
                "retry": self.retry,
                "force_full_register_list": self.force_full_register_list,
                "update_interval": str(self.update_interval),
            }
        }

    async def async_update_options(
        self,
        scan_interval: timedelta,
        timeout: int,
        retry: int,
        force_full_register_list: bool,
    ) -> None:
        """Update coordinator options."""
        _LOGGER.debug("Updating coordinator options")
        
        # Update configuration
        self.timeout = timeout
        self.retry = retry
        self.force_full_register_list = force_full_register_list
        
        # Update scan interval
        if self.update_interval != scan_interval:
            self.update_interval = scan_interval
            _LOGGER.info("Updated scan interval to %s", scan_interval)

        # Reconnect with new timeout/retry settings
        await self._async_close_client()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and cleanup resources."""
        _LOGGER.debug("Shutting down coordinator")
        await self._async_close_client()