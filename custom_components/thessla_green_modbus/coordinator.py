"""Fixed coordinator with updated pymodbus API calls - COMPATIBLE with ThesslaGreenDeviceScanner."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    DOMAIN,
    CONF_SLAVE_ID,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_RETRY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    INPUT_REGISTERS,
    HOLDING_REGISTERS,
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
)
from .device_scanner import ThesslaGreenDeviceScanner

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching data from ThesslaGreen device - COMPATIBLE with existing scanner."""

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
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        
        # Device info and capabilities
        self.device_info: Dict[str, Any] = {}
        self.capabilities: Dict[str, Any] = {}
        self.available_registers: Dict[str, set] = {}
        
        # Performance optimization: pre-computed register groups
        self._register_groups: Dict[str, List[Dict[str, Any]]] = {}
        self._last_successful_read: Dict[str, float] = {}
        self._failed_registers: set[str] = set()
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def async_config_entry_first_refresh(self) -> None:
        """Perform initial refresh including device scanning - COMPATIBLE with ThesslaGreenDeviceScanner."""
        _LOGGER.info("Starting optimized device scan...")
        
        # Scan device capabilities first using existing scanner
        scanner = ThesslaGreenDeviceScanner(self.host, self.port, self.slave_id)
        
        try:
            scan_result = await scanner.scan_device()
            self.available_registers = scan_result["available_registers"]
            self.device_info = scan_result["device_info"]
            self.capabilities = scan_result["capabilities"]
            
            # Pre-compute register groups for optimal reading
            self._precompute_register_groups()
            
            _LOGGER.info(
                "Optimized device scan successful. Found %d register types, pre-computed %d read groups",
                len(self.available_registers),
                len(self._register_groups)
            )
            
            # Perform first data refresh
            await super().async_config_entry_first_refresh()
            
        except Exception as err:
            _LOGGER.error("Device scan failed: %s", err)
            raise UpdateFailed(f"Device scan failed: {err}") from err

    def _precompute_register_groups(self) -> None:
        """Pre-compute optimized register groups for efficient reading."""
        self._register_groups = {}
        
        # Group input registers
        input_regs = self.available_registers.get("input_registers", set())
        if input_regs:
            input_addresses = {}
            for reg_name in input_regs:
                if reg_name in INPUT_REGISTERS:
                    input_addresses[reg_name] = INPUT_REGISTERS[reg_name]
            
            if input_addresses:
                self._register_groups["input"] = self._create_register_groups(input_addresses, "input")
        
        # Group holding registers
        holding_regs = self.available_registers.get("holding_registers", set())
        if holding_regs:
            holding_addresses = {}
            for reg_name in holding_regs:
                if reg_name in HOLDING_REGISTERS:
                    holding_addresses[reg_name] = HOLDING_REGISTERS[reg_name]
            
            if holding_addresses:
                self._register_groups["holding"] = self._create_register_groups(holding_addresses, "holding")
        
        # Add coils and discrete inputs
        if self.available_registers.get("coil_registers"):
            self._register_groups["coils"] = [{"type": "coil", "addresses": COIL_REGISTERS}]
            
        if self.available_registers.get("discrete_inputs"):
            self._register_groups["discrete"] = [{"type": "discrete", "addresses": DISCRETE_INPUT_REGISTERS}]

    def _create_register_groups(self, addresses: Dict[str, int], reg_type: str) -> List[Dict[str, Any]]:
        """Create optimized register groups for batch reading."""
        if not addresses:
            return []
            
        # Sort by address
        sorted_regs = sorted(addresses.items(), key=lambda x: x[1])
        groups = []
        current_group = []
        last_addr = None
        
        for name, addr in sorted_regs:
            if last_addr is None or addr - last_addr <= 10:  # Group nearby registers
                current_group.append({"name": name, "address": addr})
            else:
                if current_group:
                    groups.append({
                        "type": reg_type,
                        "start_addr": current_group[0]["address"],
                        "count": len(current_group),
                        "registers": current_group
                    })
                current_group = [{"name": name, "address": addr}]
            last_addr = addr
        
        # Add last group
        if current_group:
            groups.append({
                "type": reg_type,
                "start_addr": current_group[0]["address"],
                "count": len(current_group),
                "registers": current_group
            })
        
        return groups

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via library - FIXED API."""
        return await self.hass.async_add_executor_job(self._update_data_sync)

    def _update_data_sync(self) -> Dict[str, Any]:
        """Fetch data from device synchronously with FIXED pymodbus API."""
        data = {}
        successful_reads = 0
        total_attempts = 0
        
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            if not client.connect():
                raise UpdateFailed("Failed to connect to device")

            # Read using optimized register groups
            for group_type, groups in self._register_groups.items():
                for group in groups:
                    total_attempts += 1
                    
                    try:
                        if group["type"] == "input":
                            # FIXED: Updated API call
                            result = client.read_input_registers(
                                address=group["start_addr"],
                                count=group["count"],
                                slave=self.slave_id
                            )
                        elif group["type"] == "holding":
                            # FIXED: Updated API call
                            result = client.read_holding_registers(
                                address=group["start_addr"],
                                count=group["count"],
                                slave=self.slave_id
                            )
                        elif group["type"] == "coil":
                            # FIXED: Updated API call for coils
                            addresses = list(group["addresses"].values())
                            min_addr = min(addresses)
                            max_addr = max(addresses)
                            result = client.read_coils(
                                address=min_addr,
                                count=max_addr - min_addr + 1,
                                slave=self.slave_id
                            )
                        elif group["type"] == "discrete":
                            # FIXED: Updated API call for discrete inputs
                            addresses = list(group["addresses"].values())
                            min_addr = min(addresses)
                            max_addr = max(addresses)
                            result = client.read_discrete_inputs(
                                address=min_addr,
                                count=max_addr - min_addr + 1,
                                slave=self.slave_id
                            )
                        else:
                            continue

                        if not result.isError():
                            successful_reads += 1
                            
                            if group["type"] in ["input", "holding"]:
                                # Process register values
                                for i, reg_info in enumerate(group["registers"]):
                                    if i < len(result.registers):
                                        raw_value = result.registers[i]
                                        processed_value = self._process_register_value(
                                            reg_info["name"], raw_value
                                        )
                                        data[reg_info["name"]] = processed_value
                                        
                            elif group["type"] == "coil":
                                # Process coil values
                                addresses = group["addresses"]
                                min_addr = min(addresses.values())
                                for name, addr in addresses.items():
                                    idx = addr - min_addr
                                    if idx < len(result.bits):
                                        data[name] = result.bits[idx]
                                        
                            elif group["type"] == "discrete":
                                # Process discrete input values
                                addresses = group["addresses"]
                                min_addr = min(addresses.values())
                                for name, addr in addresses.items():
                                    idx = addr - min_addr
                                    if idx < len(result.bits):
                                        data[name] = result.bits[idx]
                                        
                    except Exception as err:
                        _LOGGER.debug("Failed to read register group %s: %s", group_type, err)
                        continue

            # Calculate success rate
            success_rate = (successful_reads / total_attempts * 100) if total_attempts > 0 else 0
            
            _LOGGER.debug(
                "Optimized data update complete: %d groups read, %.1f%% success rate",
                successful_reads, success_rate
            )
            
            return data
            
        except Exception as err:
            _LOGGER.error("Data update failed: %s", err)
            raise UpdateFailed(f"Data update failed: {err}") from err
        finally:
            client.close()

    def _process_register_value(self, name: str, raw_value: int) -> Any:
        """Process raw register value based on register type."""
        try:
            if name not in INPUT_REGISTERS and name not in HOLDING_REGISTERS:
                return raw_value

            multiplier = 1
            if name.startswith("dac_"):
                multiplier = 0.00244
            elif name in {
                "supply_air_temperature_manual",
                "supply_air_temperature_temporary",
                "min_gwc_air_temperature",
                "max_gwc_air_temperature",
                "delta_t_gwc",
                "min_bypass_temperature",
                "air_temperature_summer_free_heating",
                "air_temperature_summer_free_cooling",
                "required_temp",
            }:
                multiplier = 0.5
            elif any(temp_key in name.lower() for temp_key in ['temp', 'temperature']):
                multiplier = 0.1
            
            # Temperature processing (signed values)
            if any(temp_key in name.lower() for temp_key in ['temp', 'temperature']):
                # Handle signed 16-bit values
                if raw_value > 32767:
                    raw_value = raw_value - 65536
                return round(raw_value * multiplier, 1)
            
            # Percentage values
            elif any(perc_key in name.lower() for perc_key in ['percentage', 'percent', 'supply', 'exhaust']):
                return max(0, min(100, raw_value * multiplier))
            
            # Flow rates
            elif 'flow' in name.lower():
                return max(0, raw_value * multiplier)

            # Default processing
            else:
                return raw_value * multiplier
                
        except (ValueError, TypeError):
            _LOGGER.warning("Failed to process value for %s: %s", name, raw_value)
            return raw_value

    async def async_write_register(self, register_name: str, value: Any) -> bool:
        """Write to a device register with FIXED API."""
        return await self.hass.async_add_executor_job(
            self._write_register_sync, register_name, value
        )

    def _write_register_sync(self, register_name: str, value: Any) -> bool:
        """Write register synchronously with FIXED API."""
        # Find register in holding registers
        if register_name not in HOLDING_REGISTERS:
            _LOGGER.error("Register %s not found in holding registers", register_name)
            return False

        address = HOLDING_REGISTERS[register_name]
        
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            if not client.connect():
                _LOGGER.error("Failed to connect for write operation")
                return False

            # FIXED: Updated API call for writing
            result = client.write_register(
                address=address,
                value=int(value),
                slave=self.slave_id
            )

            if result.isError():
                _LOGGER.error("Write failed for %s: %s", register_name, result)
                return False

            _LOGGER.debug("Successfully wrote %s = %s", register_name, value)
            
            # Request data refresh after successful write
            self.async_set_updated_data(self.data)
            
            return True
            
        except Exception as err:
            _LOGGER.error("Write operation failed for %s: %s", register_name, err)
            return False
        finally:
            client.close()

    @property
    def device_status(self) -> str:
        """Determine device operational status."""
        if not self.data:
            return "unknown"
        
        # Check various indicators for device activity
        panel_mode = self.data.get("on_off_panel_mode")
        supply_perc = self.data.get("supply_percentage", 0)
        exhaust_perc = self.data.get("exhaust_percentage", 0)
        
        # Device is ON if any of these conditions are met
        if (panel_mode == 1 or 
            supply_perc > 0 or 
            exhaust_perc > 0):
            return "on"
        
        # Check if device is explicitly OFF
        if panel_mode == 0:
            return "off"
        
        return "unknown"
