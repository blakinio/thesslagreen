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
    response = MagicMock()
    response.isError.return_value = False
    coordinator._transport = AsyncMock()
    coordinator._transport.is_connected.return_value = True
    coordinator._transport.read_input_registers = AsyncMock(return_value=response)
    coordinator._transport.write_registers = AsyncMock(return_value=response)

    await coordinator._read_with_retry(
        coordinator._transport.read_input_registers,
        0,
        1,
        register_type="input",
    )
    await coordinator.async_write_registers(10, [1])

    coordinator._transport.read_input_registers.assert_awaited()
    coordinator._transport.write_registers.assert_awaited()
