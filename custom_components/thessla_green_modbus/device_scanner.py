"""Poprawiony device scanner z kompatybilnością pymodbus 3.x+"""

import logging
from typing import Dict, Set, Any, List, Tuple
from pymodbus.client import ModbusTcpClient

_LOGGER = logging.getLogger(__name__)

class ThesslaGreenDeviceScanner:
    """Skanowanie urządzenia ThesslaGreen z poprawnym API pymodbus 3.x"""
    
    def __init__(self, host: str, port: int, slave_id: int):
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self._scan_stats = {
            "total_attempts": 0,
            "successful_reads": 0,
            "failed_reads": 0
        }

    def _scan_coil_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """POPRAWIONE: Skanowanie rejestrów coil z nowym API"""
        available = set()
        
        # Przykładowe rejestry coil - dostosuj do swojego urządzenia
        COIL_REGISTERS = {
            "manual_mode": 0x0000,
            "fan_boost": 0x0001,
            "bypass_enable": 0x0002,
            "gwc_enable": 0x0003,
        }
        
        if not COIL_REGISTERS:
            return available
        
        min_addr = min(COIL_REGISTERS.values())
        max_addr = max(COIL_REGISTERS.values())
        count = max_addr - min_addr + 1
        
        try:
            # POPRAWIONE API: użyj address= i count= jako keyword arguments
            result = client.read_coils(
                address=min_addr,
                count=count,
                slave=self.slave_id
            )
            self._scan_stats["total_attempts"] += 1
            
            if not result.isError():
                self._scan_stats["successful_reads"] += 1
                for name, address in COIL_REGISTERS.items():
                    idx = address - min_addr
                    if idx < len(result.bits):
                        available.add(name)
                        _LOGGER.debug("Found coil %s (0x%04X) = %s", name, address, result.bits[idx])
            else:
                self._scan_stats["failed_reads"] += 1
                
        except Exception as exc:
            self._scan_stats["failed_reads"] += 1
            _LOGGER.debug("Failed to read coils: %s", exc)
        
        return available

    def _scan_discrete_inputs_batch(self, client: ModbusTcpClient) -> Set[str]:
        """POPRAWIONE: Skanowanie discrete inputs z nowym API"""
        available = set()
        
        # Przykładowe rejestry discrete input 
        DISCRETE_INPUT_REGISTERS = {
            "filter_alarm": 0x0000,
            "frost_protection": 0x0001,
            "summer_mode": 0x0002,
            "fireplace": 0x000E,
            "fire_alarm": 0x000F,
        }
        
        if not DISCRETE_INPUT_REGISTERS:
            return available
        
        min_addr = min(DISCRETE_INPUT_REGISTERS.values())
        max_addr = max(DISCRETE_INPUT_REGISTERS.values())
        count = max_addr - min_addr + 1
        
        try:
            # POPRAWIONE API: keyword arguments
            result = client.read_discrete_inputs(
                address=min_addr,
                count=count,
                slave=self.slave_id
            )
            self._scan_stats["total_attempts"] += 1
            
            if not result.isError():
                self._scan_stats["successful_reads"] += 1
                for name, address in DISCRETE_INPUT_REGISTERS.items():
                    idx = address - min_addr
                    if idx < len(result.bits):
                        available.add(name)
                        _LOGGER.debug("Found discrete input %s (0x%04X) = %s", name, address, result.bits[idx])
            else:
                self._scan_stats["failed_reads"] += 1
                
        except Exception as exc:
            self._scan_stats["failed_reads"] += 1
            _LOGGER.debug("Failed to read discrete inputs: %s", exc)
        
        return available

    def _scan_input_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """POPRAWIONE: Skanowanie input registers z batch reading"""
        available = set()
        
        # Grupowanie rejestrów po zakresach dla efektywności
        register_groups = [
            # Temperatury (0x0010-0x0016)
            {
                "start": 0x0010,
                "count": 7,
                "registers": {
                    "outside_temperature": 0x0010,
                    "supply_temperature": 0x0011,
                    "exhaust_temperature": 0x0012,
                    "fpx_temperature": 0x0013,
                    "duct_supply_temperature": 0x0014,
                    "gwc_temperature": 0x0015,
                    "ambient_temperature": 0x0016,
                }
            },
            # Firmware info (0x0000-0x0002)
            {
                "start": 0x0000,
                "count": 3,
                "registers": {
                    "firmware_major": 0x0000,
                    "firmware_minor": 0x0001,
                    "firmware_build": 0x0002,
                }
            }
        ]
        
        for group in register_groups:
            try:
                # POPRAWIONE API: keyword arguments
                result = client.read_input_registers(
                    address=group["start"],
                    count=group["count"],
                    slave=self.slave_id
                )
                self._scan_stats["total_attempts"] += 1
                
                if not result.isError():
                    self._scan_stats["successful_reads"] += 1
                    
                    for name, address in group["registers"].items():
                        idx = address - group["start"]
                        if idx < len(result.registers):
                            value = result.registers[idx]
                            if self._is_valid_register_value(name, value):
                                available.add(name)
                                _LOGGER.debug("Found input register %s (0x%04X) = %s", name, address, value)
                else:
                    self._scan_stats["failed_reads"] += 1
                    
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug("Failed to read input register group %s: %s", group["start"], exc)
        
        return available

    def _scan_holding_registers_batch(self, client: ModbusTcpClient) -> Set[str]:
        """POPRAWIONE: Skanowanie holding registers z nowym API"""
        available = set()
        
        register_groups = [
            # Kontrola podstawowa (0x1000-0x1010)
            {
                "start": 0x1000,
                "count": 16,
                "registers": {
                    "mode": 0x1000,
                    "season_mode": 0x1001,
                    "special_mode": 0x1002,
                    "air_flow_rate_manual": 0x1003,
                    "air_flow_rate_override": 0x1004,
                }
            }
        ]
        
        for group in register_groups:
            try:
                # POPRAWIONE API: keyword arguments
                result = client.read_holding_registers(
                    address=group["start"],
                    count=group["count"],
                    slave=self.slave_id
                )
                self._scan_stats["total_attempts"] += 1
                
                if not result.isError():
                    self._scan_stats["successful_reads"] += 1
                    
                    for name, address in group["registers"].items():
                        idx = address - group["start"]
                        if idx < len(result.registers):
                            value = result.registers[idx]
                            if self._is_valid_register_value(name, value):
                                available.add(name)
                                _LOGGER.debug("Found holding register %s (0x%04X) = %s", name, address, value)
                else:
                    self._scan_stats["failed_reads"] += 1
                    
            except Exception as exc:
                self._scan_stats["failed_reads"] += 1
                _LOGGER.debug("Failed to read holding register group %s: %s", group["start"], exc)
        
        return available

    def _is_valid_register_value(self, name: str, value: int) -> bool:
        """Walidacja wartości rejestru"""
        # Temperatury nie powinny być 0x8000 (invalid)
        if "temperature" in name:
            return value != 0x8000 and value != 32768
        
        # Przepływy nie powinny być 65535 (invalid)
        if "flowrate" in name or "air_flow" in name:
            return value != 65535
        
        # Wartości procentowe powinny być rozsądne
        if "percentage" in name or "coef" in name:
            return 0 <= value <= 200  # Pozwalamy do 200% dla boost
        
        # Tryby powinny być w oczekiwanym zakresie
        if name in ["mode", "season_mode"]:
            return 0 <= value <= 2
        
        if name == "special_mode":
            return 0 <= value <= 11
        
        # Domyślnie: akceptuj każdą wartość nie-zero jako valid
        return True

    def _extract_device_info(self, client: ModbusTcpClient) -> Dict[str, Any]:
        """Wyciągnij informacje o urządzeniu z firmware registers"""
        device_info = {
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "firmware": "Unknown",
            "serial_number": "Unknown"
        }
        
        try:
            # POPRAWIONE API dla firmware
            result = client.read_input_registers(
                address=0x0000,
                count=3,
                slave=self.slave_id
            )
            
            if not result.isError() and len(result.registers) >= 3:
                major = result.registers[0]
                minor = result.registers[1] 
                build = result.registers[2]
                device_info["firmware"] = f"{major}.{minor}.{build}"
                
                # Określ model na podstawie firmware
                if major >= 4:
                    device_info["model"] = "AirPack Home Energy+"
                    
        except Exception as exc:
            _LOGGER.debug("Failed to read firmware: %s", exc)
        
        return device_info

    async def scan_device(self) -> Dict[str, Any]:
        """Główna funkcja skanowania urządzenia"""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self._scan_device_sync)
    
    def _scan_device_sync(self) -> Dict[str, Any]:
        """Synchroniczne skanowanie urządzenia"""
        client = ModbusTcpClient(host=self.host, port=self.port, timeout=5)
        
        result = {
            "available_registers": {
                "input_registers": set(),
                "holding_registers": set(), 
                "coil_registers": set(),
                "discrete_inputs": set()
            },
            "device_info": {},
            "capabilities": set(),
            "scan_stats": {}
        }
        
        try:
            if not client.connect():
                raise Exception("Failed to connect to device")
            
            _LOGGER.info("Connected to %s:%s, scanning capabilities...", self.host, self.port)
            
            # Skanuj wszystkie typy rejestrów
            result["available_registers"]["input_registers"] = self._scan_input_registers_batch(client)
            result["available_registers"]["holding_registers"] = self._scan_holding_registers_batch(client)
            result["available_registers"]["coil_registers"] = self._scan_coil_registers_batch(client)
            result["available_registers"]["discrete_inputs"] = self._scan_discrete_inputs_batch(client)
            
            # Wyciągnij info o urządzeniu
            result["device_info"] = self._extract_device_info(client)
            
            # Oblicz statystyki
            total_found = sum(len(regs) for regs in result["available_registers"].values())
            success_rate = (self._scan_stats["successful_reads"] / max(self._scan_stats["total_attempts"], 1)) * 100
            
            result["scan_stats"] = {
                **self._scan_stats,
                "total_registers_found": total_found,
                "success_rate": success_rate
            }
            
            _LOGGER.info(
                "Scan completed: %d registers found, %.1f%% success rate",
                total_found, success_rate
            )
            
        except Exception as exc:
            _LOGGER.error("Device scan failed: %s", exc)
            raise
        finally:
            client.close()
        
        return result