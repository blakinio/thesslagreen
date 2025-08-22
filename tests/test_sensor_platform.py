"""Tests for ThesslaGreen sensor platform setup."""

import asyncio
import sys
import types
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))
setattr(const, "PERCENTAGE", "%")
setattr(const, "STATE_UNAVAILABLE", "unavailable")


class UnitOfTemperature:  # pragma: no cover - enum stub
    CELSIUS = "°C"


class UnitOfVolumeFlowRate:  # pragma: no cover - enum stub
    CUBIC_METERS_PER_HOUR = "m³/h"


class UnitOfElectricPotential:  # pragma: no cover - enum stub
    VOLT = "V"


const.UnitOfTemperature = UnitOfTemperature
const.UnitOfVolumeFlowRate = UnitOfVolumeFlowRate
const.UnitOfElectricPotential = UnitOfElectricPotential

sensor_mod = types.ModuleType("homeassistant.components.sensor")


class SensorEntity:  # pragma: no cover - simple stub
    pass


class SensorDeviceClass:  # pragma: no cover - enum stubs
    TEMPERATURE = "temperature"
    VOLTAGE = "voltage"
    POWER = "power"
    ENERGY = "energy"


class SensorStateClass:  # pragma: no cover - enum stubs
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"


sensor_mod.SensorEntity = SensorEntity
sensor_mod.SensorDeviceClass = SensorDeviceClass
sensor_mod.SensorStateClass = SensorStateClass
sys.modules["homeassistant.components.sensor"] = sensor_mod

select_mod = types.ModuleType("homeassistant.components.select")


class SelectEntity:  # pragma: no cover - simple stub
    pass


select_mod.SelectEntity = SelectEntity
sys.modules["homeassistant.components.select"] = select_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")

update_coord = types.ModuleType("homeassistant.helpers.update_coordinator")


class CoordinatorEntity:  # pragma: no cover - simple stub
    def __init__(self, coordinator=None):
        self.coordinator = coordinator

    @classmethod
    def __class_getitem__(cls, item):  # pragma: no cover - allow subscripting
        return cls


class DataUpdateCoordinator:  # pragma: no cover - minimal stub
    def __init__(self, hass=None, logger=None, name=None, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval

    async def async_shutdown(self):  # pragma: no cover - stub
        return None

    @classmethod
    def __class_getitem__(cls, item):  # pragma: no cover - allow subscripting
        return cls


class UpdateFailed(Exception):  # pragma: no cover - simple stub
    pass


update_coord.CoordinatorEntity = CoordinatorEntity
update_coord.DataUpdateCoordinator = DataUpdateCoordinator
update_coord.UpdateFailed = UpdateFailed
sys.modules["homeassistant.helpers.update_coordinator"] = update_coord


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from homeassistant.const import STATE_UNAVAILABLE  # noqa: E402
from custom_components.thessla_green_modbus.const import (  # noqa: E402
    DOMAIN,
    SENSOR_UNAVAILABLE,
)
from custom_components.thessla_green_modbus.select import (  # noqa: E402
    async_setup_entry as select_async_setup_entry,
)
from custom_components.thessla_green_modbus.sensor import (  # noqa: E402
    SENSOR_DEFINITIONS,
    ThesslaGreenErrorCodesSensor,
    ThesslaGreenActiveErrorsSensor,
    ThesslaGreenSensor,
    async_setup_entry,
)


def test_async_setup_creates_all_sensors(mock_coordinator, mock_config_entry):
    """Ensure entities are created for all available sensor registers."""

    async def run_test() -> None:
        hass = MagicMock()
        hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        available = {
            "input_registers": set(),
            "holding_registers": set(),
        }
        for name, definition in SENSOR_DEFINITIONS.items():
            available.setdefault(definition["register_type"], set()).add(name)
        mock_coordinator.available_registers = available

        # Ensure DAC sensors come from holding registers
        dac_sensors = {"dac_supply", "dac_exhaust", "dac_heater", "dac_cooler"}
        assert dac_sensors <= available["holding_registers"]  # nosec B101
        assert dac_sensors.isdisjoint(available["input_registers"])  # nosec B101

        add_entities = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)

        entities = add_entities.call_args[0][0]
        assert any(isinstance(e, ThesslaGreenErrorCodesSensor) for e in entities)  # nosec B101
        assert len(entities) == len(SENSOR_DEFINITIONS) + 1  # nosec B101

    asyncio.run(run_test())


def test_sensors_have_native_units(mock_coordinator, mock_config_entry):
    """Verify sensors expose the expected native_unit_of_measurement."""

    async def run_test() -> None:
        hass = MagicMock()
        hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        available = {
            "input_registers": set(),
            "holding_registers": set(),
        }
        for name, definition in SENSOR_DEFINITIONS.items():
            available.setdefault(definition["register_type"], set()).add(name)
        mock_coordinator.available_registers = available

        add_entities = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)

        entities = add_entities.call_args[0][0]
        for entity in entities:
            if getattr(entity, "_register_name", None) == "error_codes":
                continue
            expected = SENSOR_DEFINITIONS[entity._register_name].get("unit")
            assert (
                getattr(entity, "_attr_native_unit_of_measurement", None) == expected
            )  # nosec B101

    asyncio.run(run_test())


def test_error_codes_sensor_translates_active_registers(mock_coordinator, mock_config_entry):
    """Error sensor returns translated active codes."""

    async def run_test() -> None:
        hass = MagicMock()
        hass.config.language = "en"
        hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
        mock_coordinator.data["s_2"] = 1
        mock_coordinator.available_registers.setdefault("holding_registers", set()).add("s_2")
        add_entities = MagicMock()
        with patch(
            "custom_components.thessla_green_modbus.sensor.translation.async_get_translations",
            return_value={"codes.s_2": "Device status S 2"},
        ):
            await async_setup_entry(hass, mock_config_entry, add_entities)
        entities = add_entities.call_args[0][0]
        sensor = next(e for e in entities if isinstance(e, ThesslaGreenErrorCodesSensor))
        assert sensor.native_value == "Device status S 2"  # nosec B101

    asyncio.run(run_test())


def test_sensor_registers_match_definition():
    """Cross-check register_type against registers module."""

    from custom_components.thessla_green_modbus.registers import get_registers_by_function

    mapping = {
        "input_registers": {r.name for r in get_registers_by_function("04")},
        "holding_registers": {r.name for r in get_registers_by_function("03")},
    }

    for name, definition in SENSOR_DEFINITIONS.items():
        reg_type = definition["register_type"]
        assert reg_type in mapping, f"Unknown register type {reg_type}"
        assert name in mapping[reg_type], f"{name} not in {reg_type}"


def test_sensor_value_map(mock_coordinator, mock_config_entry):
    """Sensors with value_map return mapped state."""

    async def run_test() -> None:
        hass = MagicMock()
        hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        mock_coordinator.available_registers = {
            "input_registers": set(),
            "holding_registers": {"mode"},
        }
        mock_coordinator.data["mode"] = 0

        add_entities = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)
        sensor = next(
            e for e in add_entities.call_args[0][0] if getattr(e, "_register_name", "") == "mode"
        )
        assert sensor.native_value == "auto"

        mock_coordinator.data["mode"] = 2
        assert sensor.native_value == "temporary"

    asyncio.run(run_test())


def test_time_sensor_formats_value(mock_coordinator):
    """Time-based sensors should format minutes to HH:MM string."""
    register = "schedule_summer_mon_1"
    sensor_def = {
        "translation_key": register,
        "register_type": "holding_registers",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "value_map": None,
    }
    mock_coordinator.data[register] = 8 * 60 + 5
    sensor = ThesslaGreenSensor(mock_coordinator, register, sensor_def)
    assert sensor.native_value == "08:05"


def test_sensor_reports_unavailable_when_no_data():
    """Sensors return STATE_UNAVAILABLE and are marked unavailable when data missing."""
    coord = MagicMock()
    coord.host = "1.2.3.4"
    coord.port = 502
    coord.slave_id = 10
    coord.get_device_info.return_value = {}
    coord.entry = MagicMock()
    coord.entry.options = {}
    coord.data = {"outside_temperature": SENSOR_UNAVAILABLE}
    coord.last_update_success = True
    sensor_def = SENSOR_DEFINITIONS["outside_temperature"]
    sensor = ThesslaGreenSensor(coord, "outside_temperature", sensor_def)
    assert sensor.native_value == STATE_UNAVAILABLE
    assert sensor.available is False


def test_select_and_sensor_share_register(mock_coordinator, mock_config_entry):
    """Register remains available for both select and sensor entities."""

    async def run_test() -> None:
        hass = MagicMock()
        hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        mock_coordinator.available_registers = {
            "input_registers": set(),
            "holding_registers": {"mode"},
        }

        add_sensor = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_sensor)

        add_select = MagicMock()
        await select_async_setup_entry(hass, mock_config_entry, add_select)

        assert any(ent._register_name == "mode" for ent in add_sensor.call_args[0][0])
        assert any(ent._register_name == "mode" for ent in add_select.call_args[0][0])

    asyncio.run(run_test())


def test_active_errors_sensor(mock_coordinator, mock_config_entry):
    """Sensor aggregates active error and status codes with translations."""

    async def run_test() -> None:
        hass = MagicMock()
        hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
        hass.config = types.SimpleNamespace(language="en")

        mock_coordinator.available_registers = {
            "input_registers": set(),
            "holding_registers": {"e_100"},
        }
        mock_coordinator.data["e_100"] = 1

        add_entities = MagicMock()
        with patch(
            "homeassistant.helpers.translation.async_get_translations",
            return_value={"errors.e_100": "Outside temp sensor missing"},
        ):
            await async_setup_entry(hass, mock_config_entry, add_entities)
            entities = add_entities.call_args[0][0]
            assert any(isinstance(ent, ThesslaGreenActiveErrorsSensor) for ent in entities)
            sensor = next(
                ent for ent in entities if isinstance(ent, ThesslaGreenActiveErrorsSensor)
            )
            sensor.hass = hass
            await sensor.async_added_to_hass()
            assert sensor.native_value == "Outside temp sensor missing"
            assert sensor.extra_state_attributes["errors"] == {
                "e_100": "Outside temp sensor missing"
            }
            assert sensor.extra_state_attributes["codes"] == ["e_100"]

    asyncio.run(run_test())
