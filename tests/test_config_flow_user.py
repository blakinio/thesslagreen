"""Test config flow for ThesslaGreen Modbus integration."""

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.config_flow import (
    ConfigFlow,
)
from custom_components.thessla_green_modbus.const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_DEEP_SCAN,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
    DEFAULT_BAUD_RATE,
    DEFAULT_PARITY,
    DEFAULT_STOP_BITS,
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
async def test_form_user():
    """Test we get the initial form."""
    flow = ConfigFlow()
    flow.hass = None

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["errors"] == {}
    schema_keys = {
        key.schema if hasattr(key, "schema") else key for key in result["data_schema"].schema
    }
    assert CONF_CONNECTION_TYPE in schema_keys
    assert CONF_CONNECTION_MODE not in schema_keys
    assert CONF_HOST in schema_keys
    assert CONF_SERIAL_PORT not in schema_keys
    assert CONF_BAUD_RATE not in schema_keys
    assert CONF_PARITY not in schema_keys
    assert CONF_STOP_BITS not in schema_keys

@pytest.mark.asyncio
async def test_form_user_rtu_requires_serial_port():
    """Modbus RTU requires a serial port path."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(
            dict(
                DEFAULT_USER_INPUT,
                **{
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
                    CONF_SERIAL_PORT: "",
                },
            )
        )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_SERIAL_PORT: "invalid_serial_port"}
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_form_user_rtu_invalid_baud_rate():
    """Invalid RTU baud rate should be rejected."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(
            dict(
                DEFAULT_USER_INPUT,
                **{
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
                    CONF_SERIAL_PORT: "/dev/ttyUSB0",
                    CONF_BAUD_RATE: "invalid",
                },
            )
        )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_BAUD_RATE: "invalid_baud_rate"}
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_form_user_invalid_ipv6():
    """Test invalid IPv6 addresses are rejected."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(
            {
                CONF_HOST: "fe80::1::",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_form_user_valid_ipv6():
    """Test IPv6 addresses are accepted."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

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
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured"
        ),
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "fe80::1",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

@pytest.mark.asyncio
async def test_form_user_valid_domain():
    """Test domain names are accepted."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen example.com",
        "device_info": {},
        "scan_result": {},
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
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "example.com",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

@pytest.mark.asyncio
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
            "capabilities": {"expansion_module": True},
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
            dict(DEFAULT_USER_INPUT, **{CONF_DEEP_SCAN: True, CONF_MAX_REGISTERS_PER_REQUEST: 5})
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
    data = result2["data"]
    assert data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_TCP
    assert data[CONF_CONNECTION_MODE] == CONNECTION_MODE_AUTO
    assert data[CONF_HOST] == DEFAULT_USER_INPUT[CONF_HOST]
    assert data[CONF_PORT] == DEFAULT_USER_INPUT[CONF_PORT]
    assert data["slave_id"] == DEFAULT_USER_INPUT[CONF_SLAVE_ID]
    assert data[CONF_NAME] == DEFAULT_USER_INPUT[CONF_NAME]
    assert isinstance(data["capabilities"], dict)
    assert data["capabilities"]["expansion_module"] is True
    assert result2["options"][CONF_DEEP_SCAN] is True
    assert result2["options"][CONF_MAX_REGISTERS_PER_REQUEST] == 5

@pytest.mark.asyncio
async def test_form_user_rtu_success_creates_serial_entry():
    """RTU configuration should persist serial settings."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen Serial",
        "device_info": {"device_name": "Serial", "firmware": "1.0", "serial_number": "ABC"},
        "scan_result": {
            "device_info": {"device_name": "Serial", "firmware": "1.0", "serial_number": "ABC"},
            "capabilities": {"basic_control": True},
            "register_count": 3,
        },
    }

    user_input = dict(
        DEFAULT_USER_INPUT,
        **{
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOP_BITS: DEFAULT_STOP_BITS,
        },
    )

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
    ):
        result = await flow.async_step_user(user_input)
        assert result["type"] == "form"
        result2 = await flow.async_step_confirm({})

    data = result2["data"]
    assert data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_RTU
    assert data[CONF_SERIAL_PORT] == "/dev/ttyUSB0"
    assert data[CONF_BAUD_RATE] == DEFAULT_BAUD_RATE
    assert data[CONF_PARITY] == DEFAULT_PARITY
    assert data[CONF_STOP_BITS] == DEFAULT_STOP_BITS
    # Host/port remain available for diagnostics when provided
    assert data.get(CONF_HOST) == DEFAULT_USER_INPUT[CONF_HOST]
    assert data.get(CONF_PORT) == DEFAULT_USER_INPUT[CONF_PORT]

@pytest.mark.asyncio
async def test_form_user_tcp_rtu_success_creates_tcp_rtu_entry():
    """TCP RTU configuration should normalize to TCP with TCP RTU mode."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen TCP RTU",
        "device_info": {"device_name": "TCP RTU", "firmware": "1.0", "serial_number": "XYZ"},
        "scan_result": {
            "device_info": {"device_name": "TCP RTU", "firmware": "1.0", "serial_number": "XYZ"},
            "capabilities": {"basic_control": True},
            "register_count": 2,
        },
    }

    user_input = dict(
        DEFAULT_USER_INPUT,
        **{
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP_RTU,
        },
    )

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
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await flow.async_step_user(user_input)
        assert result["type"] == "form"
        result2 = await flow.async_step_confirm({})

    data = result2["data"]
    assert data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_TCP
    assert data[CONF_CONNECTION_MODE] == CONNECTION_MODE_TCP_RTU
    assert data[CONF_HOST] == DEFAULT_USER_INPUT[CONF_HOST]
    assert data[CONF_PORT] == DEFAULT_USER_INPUT[CONF_PORT]

@pytest.mark.asyncio
async def test_duplicate_entry_aborts():
    """Attempting to add a duplicate entry should abort the flow."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured",
            side_effect=[None, AbortFlow("already_configured")],
        ),
    ):
        await flow.async_step_user(DEFAULT_USER_INPUT)

        with pytest.raises(AbortFlow):
            await flow.async_step_confirm({})

@pytest.mark.asyncio
async def test_user_step_duplicate_entry_aborts_silently(caplog):
    """Duplicate device during user step should abort without logging errors."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured",
            side_effect=AbortFlow("already_configured"),
        ),
        caplog.at_level(logging.ERROR),
        pytest.raises(AbortFlow) as err,
    ):
        await flow.async_step_user(DEFAULT_USER_INPUT)

    assert err.value.reason == "already_configured"
    assert not caplog.records

@pytest.mark.parametrize(
    "registers,expected_note",
    [
        ("holding", "auto_detected_note_success"),
        (None, "auto_detected_note_limited"),
    ],
)
@pytest.mark.asyncio
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
    flow._scan_result = {
        "available_registers": available_registers,
        "capabilities": {},
    }

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

@pytest.mark.asyncio
async def test_async_step_confirm_capabilities_only_bool():
    """Ensure capabilities list includes only boolean fields."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "My Device",
    }
    flow._device_info = {}
    flow._scan_result = {
        "available_registers": {},
        "capabilities": {
            "temperature_sensors": {"t1"},
            "expansion_module": True,
            "temperature_sensors_count": 1,
        },
        "register_count": 1,
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    placeholders = result["description_placeholders"]
    assert "Expansion Module" in placeholders["capabilities_list"]
    assert "Temperature Sensors" not in placeholders["capabilities_list"]
    assert placeholders["capabilities_count"] == "1"

@pytest.mark.asyncio
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

@pytest.mark.asyncio
async def test_duplicate_configuration_aborts():
    """Test configuring same host/port/slave twice aborts the flow."""
    flow = ConfigFlow()
    flow.hass = None

@pytest.mark.asyncio
async def test_confirm_step_aborts_on_existing_entry():
    """Ensure confirming a second flow aborts if unique ID already configured."""

    flow = ConfigFlow()
    flow.hass = None

    user_input = dict(DEFAULT_USER_INPUT)

    validation_result = {
        "title": "Device",
        "device_info": {},
        "scan_result": {},
    }

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
    with (
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured",
            side_effect=RuntimeError("already_configured"),
        ),
        pytest.raises(RuntimeError),
    ):
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
            ConfigFlow,
            "_abort_if_unique_id_configured",
            abort_if_unique_id_configured,
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

