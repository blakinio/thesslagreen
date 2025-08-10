from __future__ import annotations

import logging
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Set, Callable, Any

from pymodbus.client import AsyncModbusTcpClient

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

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ThesslaDeviceScanner:
    """Skaner rejestrów – HA 2025.*, pymodbus 3.5.*+ (bez 'slave' w __init__)."""

    def __init__(self, host: str, port: int, unit: int = DEFAULT_UNIT, **kwargs) -> None:
        # legacy aliasy i zbędne parametry
        unit = int(kwargs.get("slave_id", kwargs.get("slave", unit)))
        # retry/timeout z legacy – ignorujemy na wejściu; timeout ustawiamy lokalnie
        self._host = host
        self._port = int(port)
        self._unit = int(unit)

    async def _call(
        self,
        func: Callable[..., Any],
        *,
        address: int,
        count: int,
        attr: str,
    ):
        """Wywołanie kompatybilne – najpierw unit=, fallback slave=."""
        try:
            resp = await func(address=address, count=count, unit=self._unit)
        except TypeError:
            resp = await func(address=address, count=count, slave=self._unit)
        if getattr(resp, "isError", lambda: False)():
            return None
        return getattr(resp, attr, None)

    async def _read_input(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[int]]:
        try:
            return await self._call(client.read_input_registers, address=address, count=count, attr="registers")
        except Exception as e:
            _LOGGER.debug("Error reading input @0x%04X: %s", address, e)
            return None

    async def _read_holding(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[int]]:
        try:
            return await self._call(client.read_holding_registers, address=address, count=count, attr="registers")
        except Exception as e:
            _LOGGER.debug("Error reading holding @0x%04X: %s", address, e)
            return None

    async def _read_coils(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[bool]]:
        try:
            return await self._call(client.read_coils, address=address, count=count, attr="bits")
        except Exception as e:
            _LOGGER.debug("Error reading coils @0x%04X: %s", address, e)
            return None

    async def _read_discrete(self, client: AsyncModbusTcpClient, address: int, count: int) -> Optional[List[bool]]:
        try:
            return await self._call(client.read_discrete_inputs, address=address, count=count, attr="bits")
        except Exception as e:
            _LOGGER.debug("Error reading discrete @0x%04X: %s", address, e)
            return None

    async def scan(self) -> Tuple[DeviceInfo, DeviceCapabilities, Dict[str, Tuple[int, int]]]:
        _LOGGER.info("Starting comprehensive device scan for %s:%s", self._host, self._port)

        client = AsyncModbusTcpClient(host=self._host, port=self._port, timeout=SOCKET_TIMEOUT)
        try:
            ok = await client.connect()
            if not (ok or getattr(client, "connected", False)):
                raise ConnectionError("Unable to connect")

            caps = DeviceCapabilities()
            present_blocks: Dict[str, Tuple[int, int]] = {}

            ver_major = await self._read_input(client, 0x0000, 1)
            ver_minor = await self._read_input(client, 0x0001, 1)
            ver_patch = await self._read_input(client, 0x0004, 1)
            fw = "Unknown"
            if ver_major and ver_minor and ver_patch:
                try:
                    fw = f"{ver_major[0]}.{ver_minor[0]}.{ver_patch[0]}"
                except Exception:
                    pass

            if await self._read_input(client, 0x0010, 1) is not None:
                caps.sensor_outside_temperature = True
                caps.temperature_sensors.add("outside")
            if await self._read_input(client, 0x0011, 1) is not None:
                caps.sensor_supply_temperature = True
                caps.temperature_sensors.add("supply")
            if await self._read_input(client, 0x0012, 1) is not None:
                caps.sensor_exhaust_temperature = True
                caps.temperature_sensors.add("exhaust")
            caps.temperature_sensors_count = len(caps.temperature_sensors)

            if await self._read_holding(client, 0x1070, 1) is not None:
                caps.basic_control = True
                present_blocks["holding_core"] = (0x1070, 0x10D1)

            if await self._read_coils(client, 0x0009, 1) is not None:
                caps.bypass_system = True
                present_blocks["coils"] = (0x0005, 0x000F)

            di = await self._read_discrete(client, 0x0001, 1)
            if di is not None and di and di[0]:
                caps.expansion_module = True
                present_blocks["discrete"] = (0x0000, 0x0015)

            info = DeviceInfo(model="AirPack Home/4", firmware=fw)

            _LOGGER.info(
                "Device scan completed: blocks=%d, active_caps=%d",
                len(present_blocks),
                sum(1 for v in caps.as_dict().values() if bool(v)),
            )
            return info, caps, present_blocks

        except Exception as e:
            _LOGGER.error("Device scan failed: %s", e)
            raise
        finally:
            try:
                await client.close()
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass
            _LOGGER.debug("Disconnected from ThesslaGreen device")


# Alias legacy
ThesslaGreenDeviceScanner = ThesslaDeviceScanner
