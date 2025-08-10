from __future__ import annotations

import logging
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Set

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)

DEFAULT_UNIT = 1
SOCKET_TIMEOUT = 6.0

@dataclass
class DeviceInfo:
    model: str = "Unknown AirPack"
    firmware: str = "Unknown"

@dataclass
class DeviceCapabilities:
    basic_control: bool = False
    temperature_sensors: Set[str] = field(default_factory=set)
    flow_sensors: Set[str] = field(default_factory=set)
    special_functions: Set[str] = field(default_factory=set)
    expansion_module: bool = False
    constant_flow: bool = False
    gwc_system: bool = False
    bypass_system: bool = False
    heating_system: bool = False
    cooling_system: bool = False
    air_quality: bool = False
    weekly_schedule: bool = False
    sensor_outside_temperature: bool = False
    sensor_supply_temperature: bool = False
    sensor_exhaust_temperature: bool = False
    sensor_fpx_temperature: bool = False
    sensor_duct_supply_temperature: bool = False
    sensor_gwc_temperature: bool = False
    sensor_ambient_temperature: bool = False
    sensor_heating_temperature: bool = False
    temperature_sensors_count: int = 0

    def as_dict(self) -> Dict:
        return asdict(self)


class ThesslaDeviceScanner:
    """Skaner rejestrów – kompatybilny z pymodbus 3.5.*+. Bez `slave` w __init__()."""

    def __init__(self, host: str, port: int, unit: int = DEFAULT_UNIT) -> None:
        self._host = host
        self._port = port
        self._unit = unit

    async def _read_input(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[int]]:
        try:
            rr = await client.read_input_registers(address, count, slave=self._unit)
            if rr.isError():
                _LOGGER.debug("Input reg error @0x%04X: %s", address, rr)
                return None
            return getattr(rr, "registers", None)
        except Exception as e:
            _LOGGER.debug("Exception input @0x%04X: %s", address, e)
            return None

    async def _read_holding(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[int]]:
        try:
            rr = await client.read_holding_registers(address, count, slave=self._unit)
            if rr.isError():
                _LOGGER.debug("Holding reg error @0x%04X: %s", address, rr)
                return None
            return getattr(rr, "registers", None)
        except Exception as e:
            _LOGGER.debug("Exception holding @0x%04X: %s", address, e)
            return None

    async def _read_coils(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[bool]]:
        try:
            rr = await client.read_coils(address, count, slave=self._unit)
            if rr.isError():
                _LOGGER.debug("Coils error @0x%04X: %s", address, rr)
                return None
            return getattr(rr, "bits", None)
        except Exception as e:
            _LOGGER.debug("Exception coils @0x%04X: %s", address, e)
            return None

    async def _read_discrete(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[bool]]:
        try:
            rr = await client.read_discrete_inputs(address, count, slave=self._unit)
            if rr.isError():
                _LOGGER.debug("Discrete error @0x%04X: %s", address, rr)
                return None
            return getattr(rr, "bits", None)
        except Exception as e:
            _LOGGER.debug("Exception discrete @0x%04X: %s", address, e)
            return None

    async def scan(self) -> Tuple[DeviceInfo, DeviceCapabilities, Dict[str, Tuple[int, int]]]:
        """Pełny skan – wykrywa obecne bloki i rejestry, zwraca device_info, capabilities i mapę dostępnych bloków."""
        _LOGGER.info("Starting comprehensive device scan for %s:%s", self._host, self._port)

        # >>> WAŻNE: bez 'slave' tutaj <<<
        client = AsyncModbusTcpClient(self._host, port=self._port, timeout=SOCKET_TIMEOUT)

        try:
            await client.connect()
            if not getattr(client, "connected", False):
                raise ConnectionError("Unable to connect")

            _LOGGER.info("Connected to ThesslaGreen device at %s:%s", self._host, self._port)

            caps = DeviceCapabilities()
            present_blocks: Dict[str, Tuple[int, int]] = {}

            # Podstawowe informacje (FW) – INPUT 0x0000..0x0016
            ver_major = await self._read_input(client, 0x0000, 1)
            ver_minor = await self._read_input(client, 0x0001, 1)
            ver_patch = await self._read_input(client, 0x0004, 1)

            fw = "Unknown"
            if ver_major and ver_minor and ver_patch:
                try:
                    fw = f"{ver_major[0]}.{ver_minor[0]}.{ver_patch[0]}"
                except Exception:
                    pass

            # Sensory temperatur (0x0010..0x0016) – obecność => capability
            t_out = await self._read_input(client, 0x0010, 1)
            t_sup = await self._read_input(client, 0x0011, 1)
            t_exh = await self._read_input(client, 0x0012, 1)
            if t_out is not None:
                caps.sensor_outside_temperature = True
                caps.temperature_sensors.add("outside")
            if t_sup is not None:
                caps.sensor_supply_temperature = True
                caps.temperature_sensors.add("supply")
            if t_exh is not None:
                caps.sensor_exhaust_temperature = True
                caps.temperature_sensors.add("exhaust")
            caps.temperature_sensors_count = len(caps.temperature_sensors)

            # Holding – tryby pracy (0x1070..)
            mode = await self._read_holding(client, 0x1070, 1)
            if mode is not None:
                caps.basic_control = True
                present_blocks["holding_core"] = (0x1070, 0x10D1)

            # Coils – bypass (0x0009) itd.
            byp = await self._read_coils(client, 0x0009, 1)
            if byp is not None:
                caps.bypass_system = True
                present_blocks["coils"] = (0x0005, 0x000F)

            # Discrete – moduły rozszerzeń
            exp = await self._read_discrete(client, 0x0001, 1)
            if exp is not None and exp[0]:
                caps.expansion_module = True
                present_blocks["discrete"] = (0x0000, 0x0015)

            info = DeviceInfo(model="AirPack Home/4", firmware=fw)

            _LOGGER.info("Detected capabilities: %s", caps)
            _LOGGER.info(
                "Device scan completed: %d blocks, %d active capabilities",
                len(present_blocks),
                sum(1 for v in caps.as_dict().values() if bool(v)),
            )

            return info, caps, present_blocks

        except Exception as e:
            _LOGGER.error("Device scan failed: %s", e)
            raise
        finally:
            try:
                client.close()
            except Exception:
                pass
            _LOGGER.debug("Disconnected from ThesslaGreen device")
