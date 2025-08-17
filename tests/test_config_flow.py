"""Test config flow for ThesslaGreen Modbus integration."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.thessla_green_modbus.config_flow import (
    CannotConnect,
    ConfigFlow,
    InvalidAuth,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)

CONF_NAME = "name"

pytestmark = pytest.mark.asyncio


class AbortFlow(Exception):
    """Mock AbortFlow to simulate Home Assistant aborts."""

    def __init__(self, reason: str) -> None:  # pragma: no cover - simple container
        super().__init__(reason)
        self.reason = reason


async def test_form_user():
    """Test we get the initial form."""
    flow = ConfigFlow()
    flow.hass = None

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["errors"] == {}


async def test_form_user_success():
    """Test successful configuration with confirm step."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    translations = {
        "auto_detected_note_success": "Auto-detection successful!",
        "auto_detected_note_limited": "Limited auto-detection - some registers may be missing.",
    }

    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {
            "device_name": "ThesslaGreen AirPack",
            "firmware": "1.0",
            "serial_number": "123",
        },
        "scan_result": {
            "device_info": {
                "device_name": "ThesslaGreen AirPack",
                "firmware": "1.0",
                "serial_number": "123",
            },
            "capabilities": {"fan": True},
            "register_count": 5,
        },
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured"
        ),
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value=translations),
        ),
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert (
        result["description_placeholders"]["auto_detected_note"]
        == translations["auto_detected_note_success"]
    )

    result2 = await flow.async_step_confirm({})
    assert result2["type"] == "create_entry"
    assert result2["title"] == "My Device"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        "unit": 10,
        CONF_NAME: "My Device",
    }


async def test_duplicate_entry_aborts():
    """Attempting to add a duplicate entry should abort the flow."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {"title": "ThesslaGreen 192.168.1.100", "device_info": {}, "scan_result": {}}

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow._abort_if_unique_id_configured",
            side_effect=[None, AbortFlow("already_configured")],
        ),
    ):
        await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

        with pytest.raises(AbortFlow):
            await flow.async_step_confirm({})


@pytest.mark.parametrize(
    "registers,expected_note",
    [
        ("holding", "auto_detected_note_success"),
        (None, "auto_detected_note_limited"),
    ],
)
async def test_async_step_confirm_auto_detected_note(registers, expected_note):
    """Test confirm step auto detected note for different register counts."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "My Device",
    }
    flow._device_info = {
        "device_name": "ThesslaGreen AirPack",
        "firmware": "1.0",
        "serial_number": "123",
    }
    available_registers = {registers: [1]} if registers else {}
    flow._scan_result = {"available_registers": available_registers, "capabilities": {}}

    translations = {
        "auto_detected_note_success": "Auto-detection successful!",
        "auto_detected_note_limited": "Limited auto-detection - some registers may be missing.",
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value=translations),
    ):
        result = await flow.async_step_confirm()

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["auto_detected_note"] == translations[expected_note]


async def test_unique_id_sanitized():
    """Ensure unique ID replaces colons in host with hyphens."""
    flow = ConfigFlow()
    flow.hass = None

    validation_result = {
        "title": "ThesslaGreen fe80::1",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured",
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"
        ) as mock_set_unique_id,
    ):
        await flow.async_step_user(
            {
                CONF_HOST: "fe80::1",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    mock_set_unique_id.assert_called_once_with("fe80--1:502:10")


async def test_duplicate_configuration_aborts():
    """Test configuring same host/port/slave twice aborts the flow."""
    flow = ConfigFlow()
    flow.hass = None
async def test_confirm_step_aborts_on_existing_entry():
    """Ensure confirming a second flow aborts if unique ID already configured."""

    flow = ConfigFlow()
    flow.hass = None

    user_input = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "My Device",
    }

    validation_result = {"title": "Device", "device_info": {}, "scan_result": {}}

    # First pass through user step to store data
    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {},
        "scan_result": {},
    }

    class AbortFlow(Exception):
        def __init__(self, reason: str) -> None:
            self.reason = reason

    entries: set[str] = set()

    async def async_set_unique_id(self, unique_id: str, **_: Any) -> None:
        self._unique_id = unique_id

    def abort_if_unique_id_configured(self) -> None:
        if getattr(self, "_unique_id", None) in entries:
            raise AbortFlow("already_configured")


    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(

            "custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id",
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured",
        ),
    ):
        await flow.async_step_user(user_input)

    # Attempt to confirm after a duplicate has been configured elsewhere
    with patch(
        "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
        "_abort_if_unique_id_configured",
        side_effect=RuntimeError("already_configured"),
    ):
        with pytest.raises(RuntimeError):
            await flow.async_step_confirm({})

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value={}),
        ),
        patch.object(ConfigFlow, "async_set_unique_id", async_set_unique_id),
        patch.object(
            ConfigFlow, "_abort_if_unique_id_configured", abort_if_unique_id_configured
        ),
    ):
        flow1 = ConfigFlow()
        flow1.hass = SimpleNamespace(config=SimpleNamespace(language="en"))
        flow2 = ConfigFlow()
        flow2.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

        await flow1.async_step_user(user_input)
        await flow2.async_step_user(user_input)

        result1 = await flow1.async_step_confirm({})
        assert result1["type"] == "create_entry"
        entries.add(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input['slave_id']}")

        with pytest.raises(AbortFlow) as err:
            await flow2.async_step_confirm({})
        assert err.value.reason == "already_configured"



async def test_form_user_cannot_connect():
    """Test we handle cannot connect error."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_user_modbus_exception():
    """Test Modbus communication error during user step."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=ModbusException("error"),
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_user_connection_exception():
    """Test Modbus connection error during user step."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=ConnectionException,
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_user_invalid_auth():
    """Test we handle invalid auth error."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_user_invalid_value():
    """Test we handle invalid value error."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=ValueError,
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_input"}


async def test_form_user_missing_key():
    """Test we handle missing key error."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=KeyError("test"),
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_input"}


async def test_form_user_unexpected_exception():
    """Test unexpected exceptions are raised."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=RuntimeError,
    ):
        with pytest.raises(RuntimeError):
            await flow.async_step_user(
                {
                    CONF_HOST: "192.168.1.100",
                    CONF_PORT: 502,
                    "slave_id": 10,
                    CONF_NAME: "My Device",
                }
            )


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
    with patch(
        "custom_components.thessla_green_modbus.config_flow.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        result = await validate_input(hass, data)

    assert result["title"] == "Test"
    assert "device_info" in result


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

    with patch(
        "custom_components.thessla_green_modbus.device_scanner."
        "ThesslaGreenDeviceScanner.scan_device",
        return_value=None,
    ):
        with pytest.raises(CannotConnect):
            await validate_input(hass, data)


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

    with patch(
        "custom_components.thessla_green_modbus.device_scanner."
        "ThesslaGreenDeviceScanner.scan_device",
        side_effect=ModbusException("error"),
    ):
        with pytest.raises(CannotConnect):
            await validate_input(hass, data)


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
    scanner_instance.close = AsyncMock()

    with patch(
        "custom_components.thessla_green_modbus.config_flow.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        with pytest.raises(CannotConnect):
            await validate_input(None, data)

    scanner_instance.close.assert_awaited_once()


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
    )

    with patch(
        "custom_components.thessla_green_modbus.config_flow.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        result = await validate_input(None, data)

    assert result["scan_result"] == scan_result
    scanner_instance.scan_device.assert_awaited_once()
    scanner_instance.close.assert_awaited_once()


async def test_validate_input_fallback_to_scan_without_close():
    """Test validate_input falls back to scan() when scan_device is unavailable."""
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
        scan=AsyncMock(return_value=scan_result)
    )

    with patch(
        "custom_components.thessla_green_modbus.config_flow.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        result = await validate_input(None, data)

    assert result["scan_result"] == scan_result
    scanner_instance.scan.assert_awaited_once()
