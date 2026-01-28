from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.modbus_transport import RtuModbusTransport


@pytest.mark.asyncio
async def test_rtu_transport_initializes_serial_client(monkeypatch):
    class DummySerialClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.connected = False

        async def connect(self):
            self.connected = True
            return True

        async def close(self):
            self.connected = False

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.modbus_transport._AsyncModbusSerialClient",
        DummySerialClient,
    )

    transport = RtuModbusTransport(
        serial_port="/dev/ttyUSB0",
        baudrate=9600,
        parity="N",
        stopbits=1,
        max_retries=2,
        base_backoff=0.1,
        max_backoff=1.0,
        timeout=2.0,
    )

    await transport.ensure_connected()

    assert transport.client is not None
    assert transport.client.kwargs["port"] == "/dev/ttyUSB0"
    assert transport.client.kwargs["baudrate"] == 9600
    assert transport.client.kwargs["parity"] == "N"
    assert transport.client.kwargs["stopbits"] == 1


@pytest.mark.asyncio
async def test_coordinator_uses_rtu_transport_for_read_write():
    hass = MagicMock()
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        connection_type=CONNECTION_TYPE_RTU,
        serial_port="/dev/ttyUSB0",
        baud_rate=9600,
        parity="n",
        stop_bits=1,
    )
    coordinator._ensure_connection = AsyncMock()
    coordinator.client = MagicMock(connected=True)
    coordinator.client.read_input_registers = AsyncMock()
    coordinator.client.write_registers = AsyncMock()
    response = MagicMock()
    response.isError.return_value = False
    coordinator._transport = AsyncMock()
    coordinator._transport.call = AsyncMock(return_value=response)

    await coordinator._call_modbus(coordinator.client.read_input_registers, 0, count=1)
    await coordinator.async_write_registers(10, [1])

    funcs = [call.args[0] for call in coordinator._transport.call.await_args_list]
    assert coordinator.client.read_input_registers in funcs
    assert coordinator.client.write_registers in funcs
