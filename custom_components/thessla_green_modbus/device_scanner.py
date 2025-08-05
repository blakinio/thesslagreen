"""Device scanner for ThesslaGreen Modbus integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Set

from pymodbus.client import ModbusTcpClient

from .const import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    INVALID_TEMPERATURE,
    INVALID_FLOW,
)

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenDeviceScanner:
    """Scanner for ThesslaGreen device capabilities and available registers."""

    def __init__(self, host: str, port: int, slave_id: int) -> None:
        """Initialize device scanner."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.available_registers: Dict[str, Set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

    async def scan_device(self) -> Dict[str, Any] | None:
        """Scan device and return available registers and capabilities."""
        def _scan_sync():
            client = ModbusTcpClient(host=self.host, port=self.port, timeout=10)
            try:
                _LOGGER.info("Connected to %s:%s, scanning capabilities...", self.host, self.port)
                
                if not client.connect():
                    raise Exception("Failed to connect to device")

                # Scan all register types
                self._scan_input_registers(client)
                self._scan_holding_registers(client)
                self._scan_coil_registers(client)
                self._scan_discrete_inputs(client)

                # Get device info
                device_info = self._get_device_info()
                capabilities = self._analyze_capabilities()

                success_rate = self._calculate_success_rate()
                _LOGGER.info(
                    "Scan completed: %d registers found, %.1f%% success rate",
                    sum(len(regs) for regs in self.available_registers.values()),
                    success_rate
                )

                return {
                    "available_registers": dict(self.available_registers),
                    "device_info": device_info,
                    "capabilities": capabilities,
                }

            except Exception as exc:
                _LOGGER.error("Device scan failed: %s", exc)
                return None
            finally:
                try:
                    client.close()
                except Exception:
                    pass

        return await asyncio.get_event_loop().run_in_executor(None, _scan_sync)

    def _scan_input_registers(self, client: ModbusTcpClient) -> None:
        """Scan input registers."""
        # Check temperature sensors (0x0010-0x0020)
        self._scan_register_range(
            client, "input_registers", INPUT_REGISTERS, 
            client.read_input_registers, batch_size=8
        )

        # Check firmware info (0x0000-0x0002)  
        firmware_regs = {
            "firmware_major": 0x0000,
            "firmware_minor": 0x0001, 
            "firmware_build": 0x0002,
        }
        self._scan_register_range(
            client, "input_registers", firmware_regs,
            client.read_input_registers, batch_size=3
        )

    def _scan_holding_registers(self, client: ModbusTcpClient) -> None:
        """Scan holding registers."""
        # Control registers (0x1000-0x1010)
        self._scan_register_range(
            client, "holding_registers", HOLDING_REGISTERS,
            client.read_holding_registers, batch_size=16
        )

    def _scan_coil_registers(self, client: ModbusTcpClient) -> None:
        """Scan coil registers."""
        # Control coils (0x0000-0x0008)
        self._scan_register_range(
            client, "coil_registers", COIL_REGISTERS,
            client.read_coils, batch_size=8
        )

    def _scan_discrete_inputs(self, client: ModbusTcpClient) -> None:
        """Scan discrete input registers."""
        # Status inputs (0x0000-0x000F)
        self._scan_register_range(
            client, "discrete_inputs", DISCRETE_INPUT_REGISTERS,
            client.read_discrete_inputs, batch_size=16
        )

    def _scan_register_range(
        self, 
        client: ModbusTcpClient,
        register_type: str,
        register_mapping: Dict[str, int],
        read_func,
        batch_size: int = 8
    ) -> None:
        """Scan a range of registers using batch reading."""
        if not register_mapping:
            return

        # Group registers by address for batch reading
        sorted_regs = sorted(register_mapping.items(), key=lambda x: x[1])
        
        for i in range(0, len(sorted_regs), batch_size):
            batch = sorted_regs[i:i + batch_size]
            start_addr = batch[0][1]
            end_addr = batch[-1][1]
            count = end_addr - start_addr + 1

            try:
                response = read_func(start_addr, count, slave=self.slave_id)
                
                if response.isError():
                    continue

                # Extract values
                if register_type in ["input_registers", "holding_registers"]:
                    values = response.registers
                else:
                    values = response.bits

                # Check each register in batch
                for name, addr in batch:
                    offset = addr - start_addr
                    if offset < len(values):
                        value = values[offset]
                        if self._is_valid_register_value(name, value):
                            self.available_registers[register_type].add(name)
                            _LOGGER.debug(
                                "Found %s %s (0x%04X) = %s",
                                register_type[:-1], name, addr, value
                            )

            except Exception as exc:
                _LOGGER.debug("Failed to read %s batch at 0x%04X: %s", register_type, start_addr, exc)
                continue

    def _is_valid_register_value(self, register_name: str, value: Any) -> bool:
        """Check if register value is valid."""
        # Temperature sensors - invalid if sensor disconnected
        if "temperature" in register_name:
            return value != INVALID_TEMPERATURE
        
        # Flow sensors - invalid if not active
        elif "flow" in register_name:
            return value != INVALID_FLOW
        
        # Other registers are valid if readable
        return True

    def _get_device_info(self) -> Dict[str, Any]:
        """Extract device information."""
        device_info = {
            "device_name": "ThesslaGreen AirPack",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
        }

        # Try to get firmware version
        if all(reg in self.available_registers["input_registers"] 
               for reg in ["firmware_major", "firmware_minor", "firmware_build"]):
            # We have firmware info available
            device_info["firmware"] = "Available"
        else:
            device_info["firmware"] = "Unknown"

        return device_info

    def _analyze_capabilities(self) -> Set[str]:
        """Analyze device capabilities based on available registers."""
        capabilities = set()

        # Basic control capability
        if "mode" in self.available_registers["holding_registers"]:
            capabilities.add("basic_control")

        # Temperature monitoring
        temp_sensors = ["outside_temperature", "supply_temperature", "exhaust_temperature"]
        if any(sensor in self.available_registers["input_registers"] for sensor in temp_sensors):
            capabilities.add("temperature_monitoring")

        # Flow control
        if "air_flow_rate_manual" in self.available_registers["holding_registers"]:
            capabilities.add("flow_control")

        # Special functions
        if "special_mode" in self.available_registers["holding_registers"]:
            capabilities.add("special_functions")

        # GWC system
        if any(reg in self.available_registers["coil_registers"] for reg in ["gwc_enable"]):
            capabilities.add("gwc_system")

        # Bypass system
        if any(reg in self.available_registers["coil_registers"] for reg in ["bypass_enable"]):
            capabilities.add("bypass_system")

        # Alarm monitoring
        if any("alarm" in reg for reg in self.available_registers["discrete_inputs"]):
            capabilities.add("alarm_monitoring")

        # Expansion module
        if "expansion" in self.available_registers["discrete_inputs"]:
            capabilities.add("expansion_module")

        return capabilities

    def _calculate_success_rate(self) -> float:
        """Calculate scan success rate."""
        total_possible = (
            len(INPUT_REGISTERS) + 
            len(HOLDING_REGISTERS) + 
            len(COIL_REGISTERS) + 
            len(DISCRETE_INPUT_REGISTERS)
        )
        
        total_found = sum(len(regs) for regs in self.available_registers.values())
        
        if total_possible == 0:
            return 0.0
            
        return (total_found / total_possible) * 100.0