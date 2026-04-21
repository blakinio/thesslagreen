import sys
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.thessla_green_modbus import async_setup_entry
from custom_components.thessla_green_modbus.const import CONF_FORCE_FULL_REGISTER_LIST, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from tests.platform_stubs import install_binary_sensor_stubs

install_binary_sensor_stubs()

from homeassistant import const as ha_const

ha_const.STATE_UNAVAILABLE = "unavailable"

from custom_components.thessla_green_modbus import binary_sensor, sensor

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
        config,
        *,
        entry=None,
        **_kwargs,
    ) -> None:
        class _Capabilities:
            def __getattr__(self, _name: str) -> bool:
                return True

        self.hass = hass
        self.host = config.host
        self.port = config.port
        self.slave_id = config.slave_id
        self.device_name = config.name
        self.entry = entry
        self.force_full_register_list = config.force_full_register_list
        self.connection_type = config.connection_type
        self.connection_mode = config.connection_mode
        self.serial_port = config.serial_port
        self.baud_rate = config.baud_rate
        self.parity = config.parity
        self.stop_bits = config.stop_bits
        self.backoff = config.backoff
        self.backoff_jitter = config.backoff_jitter
        self.safe_scan = config.safe_scan
        self.scan_uart_settings = config.scan_uart_settings
        self.deep_scan = config.deep_scan
        self.max_registers_per_request = config.max_registers_per_request
        self.skip_missing_registers = config.skip_missing_registers
        source = FULL_REGISTERS if config.force_full_register_list else PARTIAL_REGISTERS
        self.available_registers = {k: set(v) for k, v in source.items()}
        self.data: dict[str, int] = {}
        self.last_update_success = True
        self.capabilities = _Capabilities()

    async def async_setup(self):  # pragma: no cover - simple stub
        return True

    async def async_config_entry_first_refresh(self):
        for names in self.available_registers.values():
            for name in names:
                self.data[name] = 1

    async def async_shutdown(self):  # pragma: no cover - simple stub
        return None

    def get_register_map(self, register_type: str) -> dict[str, int]:
        combined = {**SENSOR_MAP, **BINARY_MAP}
        return {
            name: idx + 1
            for idx, (name, cfg) in enumerate(combined.items())
            if cfg.get("register_type") == register_type
        }

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
