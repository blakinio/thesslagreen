"""Service interaction tests for optimized integration."""

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_services_registration():
    """Integration actions are registered globally from async_setup."""
    from custom_components.thessla_green_modbus import async_setup

    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.services = MagicMock()

    assert await async_setup(hass, {}) is True

    service_calls = hass.services.async_register.call_args_list
    service_names = [call[0][1] for call in service_calls]

    expected_services = ["set_mode", "set_intensity", "set_special_function"]
    for service in expected_services:
        assert service in service_names
