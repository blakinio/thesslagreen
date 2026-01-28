import sys
from unittest.mock import AsyncMock, MagicMock, patch

import homeassistant.const as ha_const
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.thessla_green_modbus import async_setup_entry
from custom_components.thessla_green_modbus.const import CONF_FORCE_FULL_REGISTER_LIST, DOMAIN

binary_sensor_mod = sys.modules.setdefault(
    "homeassistant.components.binary_sensor", type(ha_const)("binary_sensor")
)
if not hasattr(binary_sensor_mod, "BinarySensorEntity"):

    class BinarySensorEntity:  # pragma: no cover - simple stub
        pass

    binary_sensor_mod.BinarySensorEntity = BinarySensorEntity

ha_const.STATE_UNAVAILABLE = "unavailable"

from custom_components.thessla_green_modbus import binary_sensor, sensor  # noqa: E402

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

BINARY_MAP = {
    "expansion": {
        "register_type": "discrete_inputs",
        "translation_key": "expansion",
    },
    "contamination_sensor": {
        "register_type": "discrete_inputs",
        "translation_key": "contamination_sensor",
    },
}

PARTIAL_REGISTERS = {
    "input_registers": {"outside_temperature"},
    "holding_registers": set(),
    "coil_registers": set(),
    "discrete_inputs": {"expansion"},
    "calculated": set(),
}

FULL_REGISTERS = {
    "input_registers": {"outside_temperature", "supply_temperature"},
    "holding_registers": set(),
    "coil_registers": set(),
    "discrete_inputs": {"expansion", "contamination_sensor"},
    "calculated": set(),
}


class FakeCoordinator:
    """Minimal coordinator to simulate register availability."""

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
        safe_scan=False,
        deep_scan=False,
        max_registers_per_request=0,
        entry=None,
        skip_missing_registers=False,
    ) -> None:
        self.hass = hass
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.device_name = name
        self.entry = entry
        self.force_full_register_list = force_full_register_list
        source = FULL_REGISTERS if force_full_register_list else PARTIAL_REGISTERS
        self.available_registers = {k: set(v) for k, v in source.items()}
        self.data: dict[str, int] = {}
        self.last_update_success = True
        self.capabilities_valid = True

    async def async_setup(self):  # pragma: no cover - simple stub
        return True

    async def async_config_entry_first_refresh(self):
        for names in self.available_registers.values():
            for name in names:
                self.data[name] = 1

    async def async_shutdown(self):  # pragma: no cover - simple stub
        return None

    async def async_request_refresh(self):  # pragma: no cover - simple stub
        return None

    def get_device_info(self):  # pragma: no cover - simple stub
        return {"identifiers": {(DOMAIN, "fake")}, "name": self.device_name}


def test_force_full_register_list_integration():
    """Verify full register list option exposes all entities."""

    async def run() -> None:
        hass = MagicMock()
        hass.data = {}
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *a: func(*a))

        # --------------------------------------------------------------
        # Baseline without forcing full register list
        # --------------------------------------------------------------
        entry = MagicMock()
        entry.entry_id = "base"
        entry.data = {CONF_HOST: "host", CONF_PORT: 502, "slave_id": 1}
        entry.options = {}
        entry.add_update_listener = MagicMock()
        entry.async_on_unload = MagicMock()

        with (
            patch(
                "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator",
                FakeCoordinator,
            ),
            patch(
                "custom_components.thessla_green_modbus._async_cleanup_legacy_fan_entity",
                AsyncMock(),
            ),
            patch(
                "custom_components.thessla_green_modbus._async_migrate_unique_ids",
                AsyncMock(),
            ),
            patch.dict(sensor.SENSOR_DEFINITIONS, SENSOR_MAP, clear=True),
            patch.dict(binary_sensor.BINARY_SENSOR_DEFINITIONS, BINARY_MAP, clear=True),
            patch.dict(
                sys.modules,
                {"custom_components.thessla_green_modbus.registers.loader": MagicMock()},
            ),
            patch(
                "custom_components.thessla_green_modbus.services.async_setup_services",
                AsyncMock(),
            ),
        ):
            await async_setup_entry(hass, entry)

            added_sensors: list = []
            added_binary: list = []
            await sensor.async_setup_entry(
                hass, entry, lambda ents, update=False: added_sensors.extend(ents)
            )
            await binary_sensor.async_setup_entry(
                hass, entry, lambda ents, update=False: added_binary.extend(ents)
            )

        sensor_regs = {e._register_name for e in added_sensors if e._register_name in SENSOR_MAP}
        binary_regs = {e._register_name for e in added_binary}
        assert sensor_regs == {"outside_temperature"}
        assert binary_regs == {"expansion"}

        # --------------------------------------------------------------
        # With force_full_register_list enabled
        # --------------------------------------------------------------
        entry_force = MagicMock()
        entry_force.entry_id = "forced"
        entry_force.data = {CONF_HOST: "host", CONF_PORT: 502, "slave_id": 1}
        entry_force.options = {CONF_FORCE_FULL_REGISTER_LIST: True}
        entry_force.add_update_listener = MagicMock()
        entry_force.async_on_unload = MagicMock()

        with (
            patch(
                "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator",
                FakeCoordinator,
            ),
            patch(
                "custom_components.thessla_green_modbus._async_cleanup_legacy_fan_entity",
                AsyncMock(),
            ),
            patch(
                "custom_components.thessla_green_modbus._async_migrate_unique_ids",
                AsyncMock(),
            ),
            patch.dict(sensor.SENSOR_DEFINITIONS, SENSOR_MAP, clear=True),
            patch.dict(binary_sensor.BINARY_SENSOR_DEFINITIONS, BINARY_MAP, clear=True),
            patch.dict(
                sys.modules,
                {"custom_components.thessla_green_modbus.registers.loader": MagicMock()},
            ),
            patch(
                "custom_components.thessla_green_modbus.services.async_setup_services",
                AsyncMock(),
            ),
        ):
            await async_setup_entry(hass, entry_force)

            added_sensors_force: list = []
            added_binary_force: list = []
            await sensor.async_setup_entry(
                hass,
                entry_force,
                lambda ents, update=False: added_sensors_force.extend(ents),
            )
            await binary_sensor.async_setup_entry(
                hass,
                entry_force,
                lambda ents, update=False: added_binary_force.extend(ents),
            )

        sensor_regs_force = {
            e._register_name for e in added_sensors_force if e._register_name in SENSOR_MAP
        }
        binary_regs_force = {e._register_name for e in added_binary_force}

        assert sensor_regs_force == set(SENSOR_MAP.keys())
        assert binary_regs_force == set(BINARY_MAP.keys())
        assert "supply_temperature" in sensor_regs_force and "supply_temperature" not in sensor_regs
        assert (
            "contamination_sensor" in binary_regs_force
            and "contamination_sensor" not in binary_regs
        )

    import asyncio

    asyncio.run(run())
