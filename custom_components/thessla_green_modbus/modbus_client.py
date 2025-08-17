"""Thin wrapper around the pymodbus AsyncModbusTcpClient."""

from __future__ import annotations

from pymodbus.client import AsyncModbusTcpClient


class ThesslaGreenModbusClient(AsyncModbusTcpClient):
    """Async Modbus TCP client used by the coordinator."""

    def __init__(self, host: str, port: int, timeout: int) -> None:
        super().__init__(host, port=port, timeout=timeout)
