"""Simplified data coordinator used for tests."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Set

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, HOLDING_REGISTERS
from .modbus_client import ThesslaGreenModbusClient
from .modbus_helpers import _call_modbus
from .registers import get_register_definition

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenModbusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Minimal coordinator used in unit tests."""

    def __init__(
        self,
        hass,
        host: str,
        port: int,
        slave_id: int,
        name: str,
        scan_interval: int | timedelta,
        timeout: int,
        retry: int,
        **_: Any,
    ) -> None:
        update_interval = (
            scan_interval if isinstance(scan_interval, timedelta) else timedelta(seconds=scan_interval)
        )
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{name}", update_interval=update_interval)
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        self.client: ThesslaGreenModbusClient | None = None
        self._connection_lock = asyncio.Lock()
        self.available_registers: dict[str, Set[str]] = {
            "holding_registers": set(),
            "input_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

    async def _ensure_connection(self) -> None:  # pragma: no cover - trivial
        if self.client is None:
            self.client = ThesslaGreenModbusClient(self.host, self.port, self.timeout)

    async def async_write_register(self, register_name: str, value: Any, refresh: bool = True) -> bool:
        """Write a holding register and optionally refresh."""

        if register_name not in HOLDING_REGISTERS:
            return False

        async with self._connection_lock:
            await self._ensure_connection()
            assert self.client is not None
            address = HOLDING_REGISTERS[register_name]
            definition = get_register_definition(register_name)
            if definition is not None:
                value = definition.encode(value)
            response = await _call_modbus(
                self.client.write_register,
                address,
                value,
                unit=self.slave_id,
            )
            if response is None or response.isError():
                return False

        if refresh:
            await self.async_request_refresh()
        return True
