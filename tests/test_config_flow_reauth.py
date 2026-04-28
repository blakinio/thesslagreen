"""Test config flow for ThesslaGreen Modbus integration."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.config_flow import (
    ConfigFlow,
    InvalidAuth,
)
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_TYPE,
    CONF_DEEP_SCAN,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_SLAVE_ID,
    CONNECTION_TYPE_TCP,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
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
async def test_reauth_flow_success():
    """Successful reauthentication should update the existing entry."""
    flow = ConfigFlow()

    entry = SimpleNamespace(
        entry_id="entry1",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 502,
            CONF_SLAVE_ID: 10,
            CONF_NAME: "Existing Device",
        },
        options={
            CONF_DEEP_SCAN: False,
            CONF_MAX_REGISTERS_PER_REQUEST: DEFAULT_MAX_REGISTERS_PER_REQUEST,
        },
    )

    class ConfigEntriesManager:
        def __init__(self) -> None:
            self.updated_data: dict[str, Any] | None = None
            self.updated_options: dict[str, Any] | None = None
            self.reload_calls = 0

        def async_get_entry(self, entry_id: str):
            return entry if entry_id == entry.entry_id else None

        def async_update_entry(
            self, entry_to_update, *, data: dict[str, Any] | None = None, options=None
        ) -> None:
            self.updated_data = data
            self.updated_options = options
            entry_to_update.data = data or {}
            entry_to_update.options = options or {}

        async def async_reload(self, entry_id: str) -> None:
            assert entry_id == entry.entry_id
            self.reload_calls += 1

    manager = ConfigEntriesManager()
    hass = SimpleNamespace(
        config=SimpleNamespace(language="en"),
        config_entries=manager,
    )
    flow.hass = hass
    flow.context = {"entry_id": entry.entry_id}

    validation_result = {
        "title": "Updated Device",
        "device_info": {"device_name": "Device", "firmware": "1.0", "serial_number": "123"},
        "scan_result": {
            "capabilities": {"expansion_module": True},
            "available_registers": {"holding": [1, 2]},
            "register_count": 2,
        },
    }

    translations = {
        "component.thessla_green_modbus.auto_detected_note_success": "Auto-detection successful!",
        "component.thessla_green_modbus.auto_detected_note_limited": (
            "Limited auto-detection - some registers may be missing."
        ),
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value=translations),
        ),
    ):
        initial = await flow.async_step_reauth(entry.data)

        assert initial["type"] == "form"
        assert initial["step_id"] == "reauth"

        user_result = await flow.async_step_reauth(
            {
                CONF_HOST: "192.168.1.200",
                CONF_PORT: 503,
                CONF_SLAVE_ID: 11,
                CONF_NAME: "Updated Device",
                CONF_DEEP_SCAN: True,
                CONF_MAX_REGISTERS_PER_REQUEST: 5,
            }
        )

        assert user_result["type"] == "form"
        assert user_result["step_id"] == "reauth_confirm"

        confirm_result = await flow.async_step_reauth_confirm({})

    assert confirm_result["type"] == "abort"
    assert confirm_result["reason"] == "reauth_successful"
    assert manager.updated_data is not None
    assert manager.updated_data[CONF_HOST] == "192.168.1.200"
    assert manager.updated_data[CONF_PORT] == 503
    assert manager.updated_data[CONF_SLAVE_ID] == 11
    assert manager.updated_options is not None
    assert manager.updated_options[CONF_DEEP_SCAN] is True
    assert manager.updated_options[CONF_MAX_REGISTERS_PER_REQUEST] == 5
    assert manager.reload_calls == 1

@pytest.mark.asyncio
async def test_reauth_flow_missing_entry_aborts():
    """Missing config entry during reauth confirm should abort."""
    flow = ConfigFlow()

    class ConfigEntriesManager:
        def async_get_entry(self, entry_id: str):
            return None

        def async_update_entry(self, *args, **kwargs):  # pragma: no cover - defensive
            raise AssertionError("Should not update entry when missing")

        async def async_reload(self, entry_id: str):  # pragma: no cover - defensive
            raise AssertionError("Should not reload when missing")

    hass = SimpleNamespace(
        config=SimpleNamespace(language="en"),
        config_entries=ConfigEntriesManager(),
    )
    flow.hass = hass
    flow.context = {"entry_id": "missing"}
    flow._tg_reauth_entry_id = "missing"

    flow._data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        CONF_SLAVE_ID: 10,
        CONF_NAME: "Device",
    }
    flow._scan_result = {"capabilities": {}, "available_registers": {}}
    flow._device_info = {}

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_reauth_confirm({})

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_entry_missing"

@pytest.mark.asyncio
async def test_reauth_flow_invalid_auth_error():
    """Invalid auth during reauth should show error on the form."""
    flow = ConfigFlow()

    entry = SimpleNamespace(
        entry_id="entry1",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 502,
            CONF_SLAVE_ID: 10,
            CONF_NAME: "Existing Device",
        },
        options={},
    )

    class ConfigEntriesManager:
        def async_get_entry(self, entry_id: str):
            return entry if entry_id == entry.entry_id else None

    hass = SimpleNamespace(
        config=SimpleNamespace(language="en"),
        config_entries=ConfigEntriesManager(),
    )
    flow.hass = hass
    flow.context = {"entry_id": entry.entry_id}

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        initial = await flow.async_step_reauth(entry.data)
        assert initial["step_id"] == "reauth"

        result = await flow.async_step_reauth(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                CONF_SLAVE_ID: 10,
                CONF_NAME: "Existing Device",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth"
    assert result["errors"] == {"base": "invalid_auth"}

