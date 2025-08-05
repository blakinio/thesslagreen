"""Coordinator for ThesslaGreen Modbus integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COIL_REGISTERS,
    DISCRETE_INPUTS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
)
from .modbus_client import ThesslaGreenModbusClient

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate data updates for ThesslaGreen devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        scan_interval: int = 30,
        timeout: int = 10,
        retry: int = 3,
        available_registers: dict[str, set[str]] | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        self.available_registers = available_registers or {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }
        self.device_scan_result: dict[str, Any] | None = None
        self.device_info: dict[str, Any] = {}

        self._client = ThesslaGreenModbusClient(
            host=self.host,
            port=self.port,
            slave_id=self.slave_id,
            timeout=self.timeout,
        )

        super().__init__(
            hass,
            _LOGGER,
            name="ThesslaGreen Modbus",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        data: dict[str, Any] = {}

        try:
            # Input registers
            for key in self.available_registers.get("input_registers", []):
                address = INPUT_REGISTERS.get(key)
                if address is None:
                    continue
                result = await self._client.read_input_registers(address, 1)
                data[key] = result[0] if result else None

            # Holding registers
            for key in self.available_registers.get("holding_registers", []):
                address = HOLDING_REGISTERS.get(key)
                if address is None:
                    continue
                value = await self._client.read_holding_register(address)
                data[key] = value

            # Coil registers
            for key in self.available_registers.get("coil_registers", []):
                address = COIL_REGISTERS.get(key)
                if address is None:
                    continue
                result = await self._client.read_coils(address, 1)
                data[key] = result[0] if result else None

            # Discrete inputs
            for key in self.available_registers.get("discrete_inputs", []):
                address = DISCRETE_INPUTS.get(key)
                if address is None:
                    continue
                result = await self._client.read_discrete_inputs(address, 1)
                data[key] = result[0] if result else None

            if self.device_scan_result:
                data["device_info"] = self.device_scan_result.get("device_info", {})
                self.device_info = data["device_info"]

            return data
        except Exception as err:  # pragma: no cover - log and raise to coordinator
            raise UpdateFailed(f"Failed to fetch data: {err}") from err

    async def async_write_register(self, register: str, value: Any) -> bool:
        """Write a value to the device and refresh data on success."""
        if register in HOLDING_REGISTERS:
            address = HOLDING_REGISTERS[register]
            success = await self._client.write_register(address, int(value))
        elif register in COIL_REGISTERS:
            address = COIL_REGISTERS[register]
            success = await self._client.write_coil(address, bool(value))
        else:
            _LOGGER.error("Unknown register: %s", register)
            return False

        if success:
            await self.async_request_refresh()
        return success


# Backwards compatibility for tests importing the old class name
ThesslaGreenDataCoordinator = ThesslaGreenCoordinator
