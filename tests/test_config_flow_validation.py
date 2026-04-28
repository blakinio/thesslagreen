"""Test config flow for ThesslaGreen Modbus integration."""

import asyncio
import logging
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from custom_components.thessla_green_modbus.config_flow import (
    CannotConnect,
)
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_TYPE,
    CONF_SLAVE_ID,
    CONNECTION_TYPE_TCP,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from homeassistant.const import CONF_HOST, CONF_PORT

CONF_NAME = "name"

DEFAULT_USER_INPUT = {
    CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_SLAVE_ID: 10,
    CONF_NAME: "My Device",
}


class AbortFlow(Exception):
    """Mock AbortFlow to simulate Home Assistant aborts."""

    def __init__(self, reason: str) -> None:  # pragma: no cover - simple container
        super().__init__(reason)
        self.reason = reason


@pytest.mark.asyncio

@pytest.mark.asyncio
async def test_validate_input_success():
    """Test validate_input with successful connection."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    hass = None
    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = AsyncMock()
    scanner_instance.scan_device.return_value = {
        "available_registers": {},
        "device_info": {
            "device_name": "ThesslaGreen AirPack",
            "firmware": "1.0",
            "serial_number": "123",
        },
        "capabilities": {},
    }
    scanner_instance.verify_connection = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        result = await validate_input(hass, data)

    assert result["title"] == "Test"
    assert "device_info" in result
    scanner_instance.verify_connection.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_invalid_domain():
    """Test validate_input rejects invalid domain values."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {
        CONF_HOST: "bad host",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
        ) as create_mock,
        pytest.raises(vol.Invalid) as err,
    ):
        await validate_input(None, data)
    assert err.value.error_message == "invalid_host"
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_validate_input_invalid_ipv4():
    """Test validate_input rejects invalid IPv4 addresses."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {
        CONF_HOST: "256.256.256.256",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
        ) as create_mock,
        pytest.raises(vol.Invalid) as err,
    ):
        await validate_input(None, data)
    assert err.value.error_message == "invalid_host"
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_validate_input_invalid_ipv6():
    """Test validate_input rejects invalid IPv6 addresses."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {
        CONF_HOST: "fe80::1::",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
        ) as create_mock,
        pytest.raises(vol.Invalid) as err,
    ):
        await validate_input(None, data)
    assert err.value.error_message == "invalid_host"
    create_mock.assert_not_called()

@pytest.mark.parametrize("invalid_port", [0, 65536])
@pytest.mark.asyncio
async def test_validate_input_invalid_port(invalid_port: int):
    """Test validate_input rejects ports outside valid range."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: invalid_port,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
        ) as create_mock,
        pytest.raises(vol.Invalid) as err,
    ):
        await validate_input(None, data)

    assert err.value.error_message == "invalid_port"
    create_mock.assert_not_called()

@pytest.mark.parametrize(
    ("invalid_slave", "err_code"),
    [
        (-1, "invalid_slave_low"),
        (248, "invalid_slave_high"),
    ],
)
@pytest.mark.asyncio
async def test_validate_input_invalid_slave(invalid_slave: int, err_code: str):
    """Test validate_input rejects Device IDs outside valid range."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": invalid_slave,
        CONF_NAME: "Test",
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
        ) as create_mock,
        pytest.raises(vol.Invalid) as err,
    ):
        await validate_input(None, data)

    assert err.value.error_message == err_code
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_validate_input_valid_ipv6():
    """Test validate_input accepts IPv6 addresses."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    hass = None
    data = {
        CONF_HOST: "fe80::1",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = AsyncMock()
    scanner_instance.scan_device.return_value = {
        "available_registers": {},
        "device_info": {},
        "capabilities": {},
    }
    scanner_instance.verify_connection = AsyncMock()
    scanner_instance.close = AsyncMock()

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        result = await validate_input(hass, data)

    assert result["title"] == "Test"
    scanner_instance.verify_connection.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_valid_domain():
    """Test validate_input accepts domain names."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    hass = None
    data = {
        CONF_HOST: "example.com",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = AsyncMock()
    scanner_instance.scan_device.return_value = {
        "available_registers": {},
        "device_info": {},
        "capabilities": {},
    }
    scanner_instance.verify_connection = AsyncMock()
    scanner_instance.close = AsyncMock()

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        result = await validate_input(hass, data)

    assert result["title"] == "Test"
    scanner_instance.verify_connection.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_no_data():
    """Test validate_input with no device data."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    hass = None
    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = AsyncMock()
    scanner_instance.scan_device.return_value = None
    scanner_instance.verify_connection = AsyncMock()
    scanner_instance.close = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(hass, data)

    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_modbus_exception():
    """Test validate_input with Modbus exception."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    hass = None
    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = AsyncMock()
    scanner_instance.scan_device.side_effect = ModbusException("error")
    scanner_instance.verify_connection = AsyncMock()
    scanner_instance.close = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(hass, data)

    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_scanner_closed_on_exception():
    """Ensure scanner is closed when scan_device raises an exception."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = AsyncMock()
    scanner_instance.scan_device.side_effect = ModbusException("error")
    scanner_instance.verify_connection = AsyncMock()
    scanner_instance.close = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert str(err.value) == "modbus_error"

    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_attribute_error():
    """AttributeError during validation should be reported as missing_method."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    # Scanner missing verify_connection will trigger AttributeError
    scanner_instance = SimpleNamespace(
        scan_device=AsyncMock(return_value={}),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "missing_method"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_uses_scan_device_and_closes():
    """Test validate_input uses scan_device when available and closes scanner."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scan_result = {
        "device_info": {"device_name": "Device"},
        "available_registers": {},
        "capabilities": {},
    }

    scanner_instance = SimpleNamespace(
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
        verify_connection=AsyncMock(),
    )

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        result = await validate_input(None, data)

    assert isinstance(result["scan_result"], dict)
    assert isinstance(result["scan_result"].get("capabilities"), dict)
    scanner_instance.verify_connection.assert_awaited_once()
    scanner_instance.scan_device.assert_awaited_once()
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_serializes_device_capabilities():
    """DeviceCapabilities from scanner should be converted to a dict."""
    from custom_components.thessla_green_modbus.config_flow import validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scan_result = {
        "device_info": {},
        "available_registers": {},
        "capabilities": DeviceCapabilities(expansion_module=True),
    }

    scanner_instance = SimpleNamespace(
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
        verify_connection=AsyncMock(),
    )

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        result = await validate_input(None, data)

    caps = result["scan_result"]["capabilities"]
    assert isinstance(caps, dict)
    assert caps["expansion_module"] is True
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_verify_connection_failure():
    """Connection errors during verify_connection should raise CannotConnect."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(side_effect=ConnectionException("fail")),
        scan_device=AsyncMock(),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "cannot_connect"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_invalid_capabilities():
    """Non-dict capabilities should abort the flow."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scan_result = {
        "device_info": {},
        "available_registers": {},
        "capabilities": [],  # invalid type
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(),
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert str(err.value) == "invalid_capabilities"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_invalid_scan_result_format():
    """Non-dict scan result should raise invalid_format."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(),
        scan_device=AsyncMock(return_value=[]),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert str(err.value) == "invalid_format"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_dataclass_capabilities_serialization():
    """Dataclass capabilities without mapping should serialize correctly."""
    from dataclasses import dataclass

    from custom_components.thessla_green_modbus.config_flow import validate_input

    @dataclass
    class SimpleCaps:
        expansion_module: bool = False

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scan_result = {
        "device_info": {},
        "available_registers": {},
        "capabilities": SimpleCaps(expansion_module=True),
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(),
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
    )

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        result = await validate_input(None, data)

    caps = result["scan_result"]["capabilities"]
    assert caps["expansion_module"] is True
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_missing_capabilities():
    """Missing capabilities should raise CannotConnect."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scan_result = {
        "device_info": {},
        "available_registers": {},
        # capabilities key missing
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(),
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert str(err.value) == "invalid_capabilities"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_capabilities_missing_fields():
    """Missing dataclass fields should raise CannotConnect."""
    import dataclasses

    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    caps = DeviceCapabilities()

    scan_result = {
        "device_info": {},
        "available_registers": {},
        "capabilities": caps,
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(),
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
    )

    orig_asdict = dataclasses.asdict

    def _missing_basic_control(obj):
        data = orig_asdict(obj)
        data.pop("basic_control", None)
        return data

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner_device_info.dataclasses.asdict",
            side_effect=_missing_basic_control,
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert str(err.value) == "invalid_capabilities"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_slotted_capabilities_missing_fields():
    """Slotted DeviceCapabilities object missing fields should raise CannotConnect."""
    from dataclasses import dataclass

    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    @dataclass(slots=True)
    class SlotCaps:
        basic_control: bool = False
        bypass_system: bool = False

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    caps = SlotCaps()
    delattr(caps, "basic_control")

    scan_result = {
        "device_info": {},
        "available_registers": {},
        "capabilities": caps,
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(),
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner.core.DeviceCapabilities",
            SlotCaps,
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert str(err.value) == "invalid_capabilities"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_scan_device_connection_exception():
    """ConnectionException during scan_device should raise CannotConnect."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(),
        scan_device=AsyncMock(side_effect=ConnectionException("fail")),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "cannot_connect"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_scan_device_modbus_exception():
    """ModbusException during scan_device should raise CannotConnect."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(),
        scan_device=AsyncMock(side_effect=ModbusException("fail")),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "modbus_error"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_scan_device_attribute_error():
    """AttributeError during scan_device should raise CannotConnect."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(),
        scan_device=AsyncMock(side_effect=AttributeError),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "missing_method"
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_retries_transient_failures():
    """Transient failures during setup should be retried with backoff."""
    from custom_components.thessla_green_modbus.config_flow import validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scan_result = {
        "device_info": {},
        "available_registers": {},
        "capabilities": DeviceCapabilities(),
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(side_effect=[ConnectionException("fail"), None]),
        scan_device=AsyncMock(side_effect=[ConnectionException("fail"), scan_result]),
        close=AsyncMock(),
    )

    create_mock = AsyncMock(side_effect=[ConnectionException("fail"), scanner_instance])
    sleep_mock = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            create_mock,
        ),
        patch("asyncio.sleep", sleep_mock),
    ):
        result = await validate_input(None, data)

    assert result["scan_result"] == scan_result
    assert create_mock.await_count == 2
    assert scanner_instance.verify_connection.await_count == 2
    assert scanner_instance.scan_device.await_count == 2
    assert [call.args[0] for call in sleep_mock.await_args_list] == [
        0.1,
        0.1,
        0.1,
    ]

@pytest.mark.parametrize(
    "exc,err_key", [(asyncio.TimeoutError, "timeout"), (ModbusIOException, "io_error")]
)
@pytest.mark.asyncio
async def test_validate_input_timeout_errors(exc, err_key):
    """Timeout and IO errors should map to appropriate UI errors."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(side_effect=exc),
        scan_device=AsyncMock(return_value={"capabilities": DeviceCapabilities()}),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        patch("asyncio.sleep", AsyncMock()),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == err_key
    scanner_instance.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_input_cancelled_timeout_suppresses_traceback(caplog):
    """Cancelled request timeout should not emit traceback debug logs."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(side_effect=TimeoutError("Modbus request cancelled")),
        scan_device=AsyncMock(return_value={"capabilities": DeviceCapabilities()}),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.DEBUG),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "timeout"
    assert "Timeout during device validation: Modbus request cancelled" in caplog.text
    assert "Traceback:" not in caplog.text

@pytest.mark.asyncio
async def test_validate_input_cancelled_modbus_io_suppresses_traceback(caplog):
    """Cancelled ModbusIOException should not emit traceback debug logs."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(
            side_effect=ModbusIOException("Request cancelled outside pymodbus.")
        ),
        scan_device=AsyncMock(return_value={"capabilities": DeviceCapabilities()}),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.DEBUG),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "timeout"
    assert "Timeout during device validation: Modbus request cancelled" in caplog.text
    assert "Traceback:" not in caplog.text

@pytest.mark.asyncio
async def test_validate_input_dns_failure():
    """DNS resolution failures should raise a specific error."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "example.com",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(side_effect=socket.gaierror()),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "dns_failure"

@pytest.mark.asyncio
async def test_validate_input_connection_refused():
    """Connection refused errors should raise a specific error."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
            AsyncMock(side_effect=ConnectionRefusedError()),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "connection_refused"

def test_device_capabilities_serialization():
    """DeviceCapabilities.as_dict returns a JSON-serializable dict."""
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    caps = DeviceCapabilities(
        basic_control=True,
        bypass_system=True,
        temperature_sensors={"t2", "t1"},
    )

    serialized = caps.as_dict()
    assert serialized["basic_control"] is True
    assert serialized["bypass_system"] is True
    # sets should be sorted lists for JSON serialization
    assert serialized["temperature_sensors"] == ["t1", "t2"]

    # Iteration helpers should delegate to as_dict
    # __iter__ should yield keys
    assert list(caps) == list(serialized.keys())
    assert list(caps.keys()) == list(serialized.keys())
    assert list(caps.items()) == list(serialized.items())
    assert list(caps.values()) == list(serialized.values())

