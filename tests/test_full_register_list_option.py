import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.thessla_green_modbus.const import (
    CONF_FORCE_FULL_REGISTER_LIST,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.const as ha_const

ha_const.STATE_UNAVAILABLE = "unavailable"

from custom_components.thessla_green_modbus import async_setup_entry, sensor

# Minimal sensor definitions for testing
SENSOR_MAP = {
    "outside_temperature": {
        "register_type": "input_registers",
        "translation_key": "outside_temperature",
    },
    "supply_temperature": {
        "register_type": "input_registers",
        "translation_key": "supply_temperature",
    },
}

# Register availability sets
PARTIAL_REGISTERS = {
    "input_registers": {"outside_temperature"},
    "holding_registers": set(),
    "coil_registers": set(),
    "discrete_inputs": set(),
    "calculated": set(),
}

FULL_REGISTERS = {
    "input_registers": {"outside_temperature", "supply_temperature"},
    "holding_registers": set(),
    "coil_registers": set(),
    "discrete_inputs": set(),
    "calculated": set(),
}


class FakeCoordinator:
    """Coordinator stub toggling available registers based on option."""

    def __init__(
        self,
        hass,
        host,
        port,
        slave_id,
        name,
        scan_interval,
        timeout,
        retry,
        force_full_register_list=False,
        scan_uart_settings=False,
        deep_scan=False,
        scan_max_block_size=0,
        entry=None,
        skip_missing_registers=False,
    ) -> None:
        self.hass = hass
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.device_name = name
        self.entry = entry
        source = FULL_REGISTERS if force_full_register_list else PARTIAL_REGISTERS
        self.available_registers = {k: set(v) for k, v in source.items()}
        self.data: dict[str, int] = {}
        self.last_update_success = True

    async def async_setup(self):
        return True

    async def async_config_entry_first_refresh(self):
        for names in self.available_registers.values():
            for name in names:
                self.data[name] = 1

    async def async_shutdown(self):
        return None

    async def async_request_refresh(self):
        return None

    def get_device_info(self):
        return {"identifiers": {(DOMAIN, "fake")}, "name": self.device_name}


async def _setup_entities(force: bool) -> set[str]:
    """Run integration setup and return created sensor register names."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *a: func(*a))

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {CONF_HOST: "host", CONF_PORT: 502, "slave_id": 1}
    entry.options = {CONF_FORCE_FULL_REGISTER_LIST: force} if force else {}
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()

    with patch(
        "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator",
        FakeCoordinator,
    ), patch(
        "custom_components.thessla_green_modbus._async_cleanup_legacy_fan_entity",
        AsyncMock(),
    ), patch(
        "custom_components.thessla_green_modbus._async_migrate_unique_ids",
        AsyncMock(),
    ), patch.dict(sensor.SENSOR_DEFINITIONS, SENSOR_MAP, clear=True), patch.dict(
        sys.modules, {"custom_components.thessla_green_modbus.loader": MagicMock()}
    ), patch(
        "custom_components.thessla_green_modbus.services.async_setup_services",
        AsyncMock(),
    ):
        await async_setup_entry(hass, entry)
        added: list = []
        await sensor.async_setup_entry(hass, entry, lambda ents, update=False: added.extend(ents))

    return {e._register_name for e in added if e._register_name in SENSOR_MAP}


@pytest.mark.asyncio
async def test_full_register_list_option_false():
    """Without forcing, only discovered registers create entities."""
    regs = await _setup_entities(force=False)
    assert regs == {"outside_temperature"}


@pytest.mark.asyncio
async def test_full_register_list_option_true():
    """Force option exposes entities for all registers."""
    regs = await _setup_entities(force=True)
    assert regs == set(SENSOR_MAP.keys())
