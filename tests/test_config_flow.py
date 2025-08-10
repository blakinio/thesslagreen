"""Test config flow for ThesslaGreen Modbus integration."""
import pytest
from unittest.mock import AsyncMock, patch

import pytest

pytest.skip("Requires Home Assistant environment", allow_module_level=True)

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType

from custom_components.thessla_green_modbus.config_flow import ConfigFlow, CannotConnect
from custom_components.thessla_green_modbus.const import DOMAIN


async def test_form_user():
    """Test we get the form."""
    flow = ConfigFlow()
    flow.hass = None
    
    result = await flow.async_step_user()
    
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_user_success():
    """Test successful configuration."""
    flow = ConfigFlow()
    flow.hass = None
    
    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        return_value={"title": "ThesslaGreen 192.168.1.100"},
    ), patch(
        "custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"
    ), patch(
        "custom_components.thessla_green_modbus.config_flow.ConfigFlow._abort_if_unique_id_configured"
    ):
        result = await flow.async_step_user({
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 502,
            "slave_id": 10,
        })
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "ThesslaGreen 192.168.1.100"
        assert result["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 502,
            "slave_id": 10,
        }


async def test_form_user_cannot_connect():
    """Test we handle cannot connect error."""
    flow = ConfigFlow()
    flow.hass = None
    
    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await flow.async_step_user({
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 502,
            "slave_id": 10,
        })
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_user_unexpected_exception():
    """Test we handle unexpected exception."""
    flow = ConfigFlow()
    flow.hass = None
    
    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await flow.async_step_user({
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 502,
            "slave_id": 10,
        })
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_validate_input_success():
    """Test validate_input with successful connection."""
    from custom_components.thessla_green_modbus.config_flow import validate_input
    
    hass = None
    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
    }
    
    with patch(
        "custom_components.thessla_green_modbus.device_scanner.ThesslaGreenDeviceScanner.scan_device",
        return_value={
            "available_registers": {},
            "device_info": {"device_name": "ThesslaGreen AirPack"},
            "capabilities": {},
        }
    ):
        result = await validate_input(hass, data)
        
        assert result["title"] == "ThesslaGreen 192.168.1.100"
        assert "device_info" in result


async def test_validate_input_no_data():
    """Test validate_input with no device data."""
    from custom_components.thessla_green_modbus.config_flow import validate_input
    
    hass = None
    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
    }
    
    with patch(
        "custom_components.thessla_green_modbus.device_scanner.ThesslaGreenDeviceScanner.scan_device",
        return_value=None
    ):
        with pytest.raises(CannotConnect):
            await validate_input(hass, data)