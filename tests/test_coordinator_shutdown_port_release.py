"""Regression tests: a shut-down RTU coordinator must not reopen its serial port."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import ClassVar

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU
from pymodbus.exceptions import ConnectionException, ModbusIOException

from tests.helpers_coordinator import make_coordinator

SERIAL_PORT = "/dev/ttyUSB0"


class ExclusiveSerialClient:
    held_ports: ClassVar[set[str]] = set()
    instances: ClassVar[list[ExclusiveSerialClient]] = []

    def __init__(self, *, port: str, **_kwargs) -> None:
        self.port = port
        self.connected = False
        self.read_started = asyncio.Event()
        self.hang_reads = False
        ExclusiveSerialClient.instances.append(self)

    async def connect(self) -> bool:
        if self.port in ExclusiveSerialClient.held_ports:
            return False
        ExclusiveSerialClient.held_ports.add(self.port)
        self.connected = True
        return True

    def close(self) -> None:
        if self.connected:
            ExclusiveSerialClient.held_ports.discard(self.port)
        self.connected = False

    async def _request(self) -> None:
        if not self.connected and not await self.connect():
            raise ConnectionException("Client cannot connect")
        self.read_started.set()
        if self.hang_reads:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError as exc:
                raise ModbusIOException("Request cancelled outside library.") from exc

    async def read_input_registers(self, address: int, *, count: int = 1, device_id: int = 1):
        await self._request()
        return SimpleNamespace(registers=[0] * count, isError=lambda: False)

    async def read_holding_registers(self, address: int, *, count: int = 1, device_id: int = 1):
        await self._request()
        return SimpleNamespace(registers=[0] * count, isError=lambda: False)

    async def write_register(self, address: int, value: int, *, device_id: int = 1):
        await self._request()
        return SimpleNamespace(isError=lambda: False)


@pytest.fixture
def rtu_coordinator(monkeypatch):
    ExclusiveSerialClient.held_ports = set()
    ExclusiveSerialClient.instances = []
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.transport.rtu._AsyncModbusSerialClient",
        ExclusiveSerialClient,
    )
    return make_coordinator(connection_type=CONNECTION_TYPE_RTU, serial_port=SERIAL_PORT)


async def test_write_queued_during_shutdown_does_not_reopen_serial_port(rtu_coordinator):
    await rtu_coordinator._ensure_connection()
    assert ExclusiveSerialClient.held_ports == {SERIAL_PORT}

    await rtu_coordinator.async_shutdown()
    assert ExclusiveSerialClient.held_ports == set()

    assert await rtu_coordinator.async_write_register("air_flow_rate_manual", 40) is False
    assert ExclusiveSerialClient.held_ports == set()
    assert len(ExclusiveSerialClient.instances) == 1


async def test_poll_cancelled_during_shutdown_does_not_reopen_serial_port(rtu_coordinator):
    await rtu_coordinator._ensure_connection()
    device_client = rtu_coordinator.device_client
    transport = device_client._transport
    transport.client.hang_reads = True

    poll = asyncio.create_task(
        device_client._read_with_retry(transport.read_input_registers, 0, 1, register_type="input")
    )
    await transport.client.read_started.wait()

    await rtu_coordinator.async_shutdown()
    poll.cancel()

    with pytest.raises(ConnectionException):
        await poll
    assert ExclusiveSerialClient.held_ports == set()
    assert len(ExclusiveSerialClient.instances) == 1
