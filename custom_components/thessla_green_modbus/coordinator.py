"""OPTIMIZED Coordinator for ThesslaGreen Modbus Integration - SILVER STANDARD.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
OPTIMIZED: Batch reading, smart error handling, enhanced diagnostics
FIX: Poprawiony import i kompatybilność z pymodbus 3.5.*+
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set, List, Tuple
import struct

import pymodbus.client.tcp as ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException
from pymodbus.pdu import ExceptionResponse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    MANUFACTURER, 
    MODEL,
    INPUT_REGISTERS,
    HOLDING_REGISTERS,
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    REGISTER_UNITS,
    REGISTER_MULTIPLIERS,
    DEVICE_CLASSES,
    STATE_CLASSES,
)
from .device_scanner import ThesslaGreenDeviceScanner, DeviceCapabilities

_LOGGER = logging.getLogger(__name__)

class ThesslaGreenModbusCoordinator(DataUpdateCoordinator):
    """Optimized data coordinator for ThesslaGreen Modbus device."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        name: str,
        scan_interval: timedelta,
        timeout: int = 10,
        retry: int = 3,
        force_full_register_list: bool = False,
        entry: Optional[Any] = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=scan_interval,
        )
        
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.device_name = name
        self.timeout = timeout
        self.retry = retry
        self.force_full_register_list = force_full_register_list
        self.entry = entry
        
        # Connection management
        self.client: Optional[ModbusTcpClient.AsyncModbusTcpClient] = None
        self._connection_lock = asyncio.Lock()
        self._last_successful_read = datetime.now()
        
        # Device info and capabilities
        self.device_info: Dict[str, Any] = {}
        self.capabilities: DeviceCapabilities = DeviceCapabilities()
        self.available_registers: Dict[str, Set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }
        
        # Optimization: Pre-computed register groups for batch reading
        self._register_groups: Dict[str, List[Tuple[int, int]]] = {}
        self._failed_registers: Set[str] = set()
        self._consecutive_failures = 0
        self._max_failures = 5
        
        # Device scan result
        self.device_scan_result: Optional[Dict[str, Any]] = None
        
        # Statistics and diagnostics
        self.statistics = {
            "successful_reads": 0,
            "failed_reads": 0,
            "connection_errors": 0,
            "timeout_errors": 0,
            "last_error": None,
            "last_successful_update": None,
            "average_response_time": 0.0,
            "total_registers_read": 0,
        }
    
    async def async_setup(self) -> bool:
        """Set up the coordinator by scanning the device."""
        _LOGGER.info("Setting up ThesslaGreen coordinator for %s:%s", self.host, self.port)
        
        try:
            if not self.force_full_register_list:
                # Scan device to detect available registers and capabilities
                _LOGGER.info("Scanning device for available registers...")
                scanner = ThesslaGreenDeviceScanner(self.host, self.port, self.slave_id, self.timeout)
                self.device_scan_result = await scanner.scan_device()
                
                self.device_info = self.device_scan_result["device_info"]
                self.capabilities = DeviceCapabilities(**self.device_scan_result["capabilities"])
                self.available_registers = self.device_scan_result["available_registers"]
                
                _LOGGER.info(
                    "Device scan completed: %d registers found, model: %s, firmware: %s",
                    self.device_scan_result["register_count"],
                    self.device_info.get("model", "Unknown"),
                    self.device_info.get("firmware", "Unknown")
                )
            else:
                # Use all registers without scanning
                _LOGGER.warning("Force full register list enabled - skipping device scan")
                self.available_registers = {
                    "input_registers": set(INPUT_REGISTERS.keys()),
                    "holding_registers": set(HOLDING_REGISTERS.keys()),
                    "coil_registers": set(COIL_REGISTERS.keys()),
                    "discrete_inputs": set(DISCRETE_INPUT_REGISTERS.keys()),
                }
                self.device_info = {"device_name": self.device_name, "model": MODEL}
                self.capabilities = DeviceCapabilities(basic_control=True)
            
            # Pre-compute register groups for optimized batch reading
            self._precompute_register_groups()
            
            # Test initial connection
            await self._test_connection()
            
            _LOGGER.info("ThesslaGreen coordinator setup completed successfully")
            return True
            
        except Exception as exc:
            _LOGGER.error("Failed to setup coordinator: %s", exc)
            raise UpdateFailed(f"Setup failed: {exc}") from exc
    
    def _precompute_register_groups(self) -> None:
        """Pre-compute register groups for efficient batch reading."""
        # Group Input Registers
        if self.available_registers["input_registers"]:
            input_addrs = [INPUT_REGISTERS[reg] for reg in self.available_registers["input_registers"]]
            self._register_groups["input"] = self._group_registers_for_batch_read(sorted(input_addrs))
        
        # Group Holding Registers  
        if self.available_registers["holding_registers"]:
            holding_addrs = [HOLDING_REGISTERS[reg] for reg in self.available_registers["holding_registers"]]
            self._register_groups["holding"] = self._group_registers_for_batch_read(sorted(holding_addrs))
        
        # Group Coil Registers
        if self.available_registers["coil_registers"]:
            coil_addrs = [COIL_REGISTERS[reg] for reg in self.available_registers["coil_registers"]]
            self._register_groups["coil"] = self._group_registers_for_batch_read(sorted(coil_addrs))
        
        # Group Discrete Input Registers
        if self.available_registers["discrete_inputs"]:
            discrete_addrs = [DISCRETE_INPUT_REGISTERS[reg] for reg in self.available_registers["discrete_inputs"]]
            self._register_groups["discrete"] = self._group_registers_for_batch_read(sorted(discrete_addrs))
        
        _LOGGER.debug("Pre-computed register groups: %s", 
                     {k: len(v) for k, v in self._register_groups.items()})
    
    def _group_registers_for_batch_read(self, addresses: List[int], max_gap: int = 10, max_batch: int = 16) -> List[Tuple[int, int]]:
        """Group consecutive registers for efficient batch reading."""
        if not addresses:
            return []
        
        groups = []
        current_start = addresses[0]
        current_end = addresses[0]
        
        for addr in addresses[1:]:
            # If gap is too large or batch too big, start new group
            if (addr - current_end > max_gap) or (current_end - current_start + 1 >= max_batch):
                groups.append((current_start, current_end - current_start + 1))
                current_start = addr
                current_end = addr
            else:
                current_end = addr
        
        # Add last group
        groups.append((current_start, current_end - current_start + 1))
        return groups
    
    async def _test_connection(self) -> None:
        """Test initial connection to the device."""
        async with self._connection_lock:
            try:
                await self._ensure_connection()
                # Try to read a basic register to verify communication
                response = await self.client.read_input_registers(0x0000, 1, slave=self.slave_id)
                if response.isError():
                    raise ConnectionException("Cannot read basic register")
                _LOGGER.debug("Connection test successful")
            except Exception as exc:
                _LOGGER.error("Connection test failed: %s", exc)
                raise
    
    async def _ensure_connection(self) -> None:
        """Ensure Modbus connection is established."""
        if self.client is None or not self.client.connected:
            try:
                self.client = ModbusTcpClient.AsyncModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout
                )
                connected = await self.client.connect()
                if not connected:
                    raise ConnectionException(f"Could not connect to {self.host}:{self.port}")
                _LOGGER.debug("Modbus connection established")
            except Exception as exc:
                self.statistics["connection_errors"] += 1
                _LOGGER.error("Failed to establish connection: %s", exc)
                raise
    
    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the device with optimized batch reading."""
        start_time = datetime.now()
        data = {}
        
        try:
            async with self._connection_lock:
                await self._ensure_connection()
                
                # Read all register types efficiently
                data.update(await self._read_input_registers_optimized())
                data.update(await self._read_holding_registers_optimized())
                data.update(await self._read_coil_registers_optimized())
                data.update(await self._read_discrete_inputs_optimized())
                
                # Update statistics
                self.statistics["successful_reads"] += 1
                self.statistics["last_successful_update"] = datetime.now()
                self._last_successful_read = datetime.now()
                self._consecutive_failures = 0
                
                # Calculate average response time
                response_time = (datetime.now() - start_time).total_seconds()
                if self.statistics["average_response_time"] == 0:
                    self.statistics["average_response_time"] = response_time
                else:
                    self.statistics["average_response_time"] = (
                        self.statistics["average_response_time"] * 0.9 + response_time * 0.1
                    )
                
                _LOGGER.debug(
                    "Update completed: %d registers, %.2fs response time",
                    len(data), response_time
                )
                
                return data
                
        except Exception as exc:
            self._consecutive_failures += 1
            self.statistics["failed_reads"] += 1
            self.statistics["last_error"] = str(exc)
            
            if isinstance(exc, (ConnectionException, TimeoutError)):
                self.statistics["connection_errors" if isinstance(exc, ConnectionException) else "timeout_errors"] += 1
            
            _LOGGER.error("Update failed (attempt %d/%d): %s", 
                         self._consecutive_failures, self._max_failures, exc)
            
            # If too many consecutive failures, disconnect and retry
            if self._consecutive_failures >= self._max_failures:
                _LOGGER.warning("Too many consecutive failures, resetting connection")
                await self._disconnect()
                self._consecutive_failures = 0
            
            raise UpdateFailed(f"Update failed: {exc}") from exc
    
    async def _read_input_registers_optimized(self) -> Dict[str, Any]:
        """Read input registers using optimized batch reading."""
        data = {}
        
        if "input" not in self._register_groups:
            return data
        
        for start_addr, count in self._register_groups["input"]:
            try:
                response = await self.client.read_input_registers(start_addr, count, slave=self.slave_id)
                if response.isError():
                    _LOGGER.debug("Failed to read input registers at 0x%04X: %s", start_addr, response)
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
                        
            except Exception as exc:
                _LOGGER.debug("Error reading input registers at 0x%04X: %s", start_addr, exc)
                continue
        
        return data
    
    async def _read_holding_registers_optimized(self) -> Dict[str, Any]:
        """Read holding registers using optimized batch reading."""
        data = {}
        
        if "holding" not in self._register_groups:
            return data
        
        for start_addr, count in self._register_groups["holding"]:
            try:
                response = await self.client.read_holding_registers(start_addr, count, slave=self.slave_id)
                if response.isError():
                    _LOGGER.debug("Failed to read holding registers at 0x%04X: %s", start_addr, response)
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
                        
            except Exception as exc:
                _LOGGER.debug("Error reading holding registers at 0x%04X: %s", start_addr, exc)
                continue
        
        return data
    
    async def _read_coil_registers_optimized(self) -> Dict[str, Any]:
        """Read coil registers using optimized batch reading."""
        data = {}
        
        if "coil" not in self._register_groups:
            return data
        
        for start_addr, count in self._register_groups["coil"]:
            try:
                response = await self.client.read_coils(start_addr, count, slave=self.slave_id)
                if response.isError():
                    _LOGGER.debug("Failed to read coil registers at 0x%04X: %s", start_addr, response)
                    continue
                
                # Process each coil in the batch
                for i, value in enumerate(response.bits):
                    addr = start_addr + i
                    register_name = self._find_register_name(COIL_REGISTERS, addr)
                    if register_name and register_name in self.available_registers["coil_registers"]:
                        data[register_name] = bool(value)
                        self.statistics["total_registers_read"] += 1
                        
            except Exception as exc:
                _LOGGER.debug("Error reading coil registers at 0x%04X: %s", start_addr, exc)
                continue
        
        return data
    
    async def _read_discrete_inputs_optimized(self) -> Dict[str, Any]:
        """Read discrete input registers using optimized batch reading."""
        data = {}
        
        if "discrete" not in self._register_groups:
            return data
        
        for start_addr, count in self._register_groups["discrete"]:
            try:
                response = await self.client.read_discrete_inputs(start_addr, count, slave=self.slave_id)
                if response.isError():
                    _LOGGER.debug("Failed to read discrete inputs at 0x%04X: %s", start_addr, response)
                    continue
                
                # Process each discrete input in the batch
                for i, value in enumerate(response.bits):
                    addr = start_addr + i
                    register_name = self._find_register_name(DISCRETE_INPUT_REGISTERS, addr)
                    if register_name and register_name in self.available_registers["discrete_inputs"]:
                        data[register_name] = bool(value)
                        self.statistics["total_registers_read"] += 1
                        
            except Exception as exc:
                _LOGGER.debug("Error reading discrete inputs at 0x%04X: %s", start_addr, exc)
                continue
        
        return data
    
    def _find_register_name(self, register_dict: Dict[str, int], address: int) -> Optional[str]:
        """Find register name by address."""
        for name, addr in register_dict.items():
            if addr == address:
                return name
        return None
    
    def _process_register_value(self, register_name: str, raw_value: int) -> Optional[Any]:
        """Process raw register value with appropriate conversion and validation."""
        # Handle special invalid values
        if "temperature" in register_name and raw_value == 0x8000:
            return None  # No sensor connected
        
        if "flow" in register_name and raw_value == 0x8000:
            return None  # No sensor connected
        
        if raw_value == 0xFFFF:
            return None  # Typical error value
        
        # Apply multiplier if defined
        multiplier = REGISTER_MULTIPLIERS.get(register_name, 1)
        if multiplier != 1:
            # Handle signed/unsigned conversion for temperature sensors
            if "temperature" in register_name and raw_value > 32767:
                raw_value = raw_value - 65536  # Convert to signed
            return round(raw_value * multiplier, 2)
        
        return raw_value
    
    async def async_write_register(self, register_name: str, value: Any) -> bool:
        """Write value to a holding register."""
        if register_name not in HOLDING_REGISTERS:
            _LOGGER.error("Register %s is not a writable holding register", register_name)
            return False
        
        address = HOLDING_REGISTERS[register_name]
        
        # Convert value if necessary
        if register_name in REGISTER_MULTIPLIERS:
            multiplier = REGISTER_MULTIPLIERS[register_name]
            value = int(value / multiplier)
        
        async with self._connection_lock:
            try:
                await self._ensure_connection()
                response = await self.client.write_register(address, value, slave=self.slave_id)
                if response.isError():
                    _LOGGER.error("Failed to write register %s: %s", register_name, response)
                    return False
                
                _LOGGER.debug("Successfully wrote %s = %s", register_name, value)
                return True
                
            except Exception as exc:
                _LOGGER.error("Error writing register %s: %s", register_name, exc)
                return False
    
    async def async_write_coil(self, coil_name: str, value: bool) -> bool:
        """Write value to a coil register."""
        if coil_name not in COIL_REGISTERS:
            _LOGGER.error("Coil %s is not a valid coil register", coil_name)
            return False
        
        address = COIL_REGISTERS[coil_name]
        
        async with self._connection_lock:
            try:
                await self._ensure_connection()
                response = await self.client.write_coil(address, value, slave=self.slave_id)
                if response.isError():
                    _LOGGER.error("Failed to write coil %s: %s", coil_name, response)
                    return False
                
                _LOGGER.debug("Successfully wrote coil %s = %s", coil_name, value)
                return True
                
            except Exception as exc:
                _LOGGER.error("Error writing coil %s: %s", coil_name, exc)
                return False
    
    async def _disconnect(self) -> None:
        """Disconnect from the Modbus device."""
        if self.client:
            try:
                self.client.close()
                self.client = None
                _LOGGER.debug("Disconnected from Modbus device")
            except Exception as exc:
                _LOGGER.debug("Error during disconnect: %s", exc)
    
    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
        await self._disconnect()
    
    @property
    def device_info_dict(self) -> DeviceInfo:
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
    
    def get_diagnostics_data(self) -> Dict[str, Any]:
        """Return diagnostic data for troubleshooting."""
        return {
            "device_info": self.device_info,
            "capabilities": self.capabilities.__dict__,
            "available_registers": {
                k: list(v) for k, v in self.available_registers.items()
            },
            "register_groups": self._register_groups,
            "statistics": self.statistics,
            "connection_status": {
                "connected": self.client.connected if self.client else False,
                "host": self.host,
                "port": self.port,
                "slave_id": self.slave_id,
                "last_successful_read": self._last_successful_read.isoformat(),
                "consecutive_failures": self._consecutive_failures,
            },
            "failed_registers": list(self._failed_registers),
            "scan_result": self.device_scan_result,
        }