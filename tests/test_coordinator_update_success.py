from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_get_client_method_fallback_noop():
    coord = _make_coordinator()
    coord.client = None
    coord._transport = None
    method = coord._get_client_method("nonexistent_method_xyz")
    assert callable(method)
    assert await method() is None


async def test_get_client_method_from_client():
    coord = _make_coordinator()
    coord._transport = None
    client = MagicMock()
    expected = AsyncMock(return_value="ok")
    client.read_holding_registers = expected
    coord.client = client
    assert coord._get_client_method("read_holding_registers") is expected


async def test_async_write_register_via_transport():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    ok_response = MagicMock()
    ok_response.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_register = AsyncMock(return_value=ok_response)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock()
    assert await coord.async_write_register("mode", 1) is True


async def test_async_write_register_coil():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    ok_response = MagicMock()
    ok_response.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=ok_response)
    coord.async_request_refresh = AsyncMock()
    assert await coord.async_write_register("bypass", 1) is True


async def test_async_write_register_refresh_type_error():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    ok_response = MagicMock()
    ok_response.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_register = AsyncMock(return_value=ok_response)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock(side_effect=TypeError("mock ctx"))
    assert await coord.async_write_register("mode", 1, refresh=True) is True


async def test_async_write_register_multi_reg_with_offset_via_transport():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 3
    mock_def.function = 3
    mock_def.address = 100
    mock_def.encode.return_value = [10, 20, 30]
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_registers = AsyncMock(return_value=ok_resp)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        assert await coord.async_write_register("some_reg", 5, offset=1) is True


async def test_async_write_registers_single_request_rtu_transport():
    from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU

    coord = _make_coordinator(connection_type=CONNECTION_TYPE_RTU)
    coord._ensure_connection = AsyncMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_registers = AsyncMock(return_value=ok_resp)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock()
    assert await coord.async_write_registers(100, [1, 2], require_single_request=True) is True


async def test_async_write_registers_single_request_tcp_call_modbus():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_registers = AsyncMock(return_value=ok_resp)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock()
    assert await coord.async_write_registers(100, [1, 2], require_single_request=True) is True


async def test_async_write_registers_batch_via_client():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    client.write_registers = AsyncMock(return_value=ok_resp)
    coord.client = client
    coord.async_request_refresh = AsyncMock()
    assert await coord.async_write_registers(100, [1, 2]) is True


async def test_async_write_registers_refresh_type_error():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    client.write_registers = AsyncMock(return_value=ok_resp)
    coord.client = client
    coord.async_request_refresh = AsyncMock(side_effect=TypeError("mock ctx"))
    assert await coord.async_write_registers(100, [1, 2], refresh=True) is True


async def test_async_write_register_encoded_non_list():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 2
    mock_def.function = 3
    mock_def.address = 100
    mock_def.encode.return_value = 999
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_registers = AsyncMock(return_value=ok_resp)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        assert await coord.async_write_register("some_reg", 5, offset=0) is True
