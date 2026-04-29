from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.diagnostics import async_get_config_entry_diagnostics

DOMAIN = "thessla_green_modbus"


@pytest.mark.asyncio
async def test_diagnostics_expected_keys_when_missing_scan_data():
    class DummyCoordinator:
        def __init__(self) -> None:
            self.last_scan = None
            self.device_scan_result = None
            self.data = {}
            self.device_info = {}
            self.available_registers = {}
            self.statistics = {}
            self.capabilities = SimpleNamespace(as_dict=lambda: {})
            self.deep_scan = False
            self.force_full_register_list = False
            self.effective_batch = 0

        def get_diagnostic_data(self):
            return {}

    coord = DummyCoordinator()
    entry = SimpleNamespace(entry_id="test", runtime_data=coord)
    hass = SimpleNamespace(data={DOMAIN: {entry.entry_id: coord}}, config=SimpleNamespace(language="en"))

    with patch(
        "custom_components.thessla_green_modbus.diagnostics.translation.async_get_translations",
        AsyncMock(return_value={}),
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["unknown_registers"] == {}
    assert result["failed_addresses"] == {}
    assert result["last_scan"] is None
    assert result["error_statistics"] == {"connection_errors": 0, "timeout_errors": 0}


@pytest.mark.asyncio
async def test_diagnostics_offline_active_error_formatting():
    class DummyCoordinator:
        def __init__(self) -> None:
            self.last_scan = None
            self.device_scan_result = None
            self.data = {"s_offline": True}
            self.device_info = {}
            self.available_registers = {}
            self.statistics = {}
            self.capabilities = SimpleNamespace(as_dict=lambda: {})
            self.deep_scan = False
            self.force_full_register_list = False
            self.effective_batch = 0

        def get_diagnostic_data(self):
            return {}

    coord = DummyCoordinator()
    entry = SimpleNamespace(entry_id="test", runtime_data=coord)
    hass = SimpleNamespace(data={DOMAIN: {entry.entry_id: coord}}, config=SimpleNamespace(language="en"))

    with patch(
        "custom_components.thessla_green_modbus.diagnostics.translation.async_get_translations",
        AsyncMock(return_value={"codes.s_offline": "Offline"}),
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["active_errors"] == {"s_offline": "Offline"}
