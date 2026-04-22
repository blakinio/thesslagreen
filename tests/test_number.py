"""Tests for ThesslaGreenNumber entity."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException

from tests.platform_stubs import install_number_stubs

install_number_stubs()

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.mappings import (
    SENSOR_ENTITY_MAPPINGS,
)
from custom_components.thessla_green_modbus.number import (
    ENTITY_MAPPINGS,
    ThesslaGreenNumber,
    async_setup_entry,
)


def test_number_creation_and_state(mock_coordinator):
    """Test creation and state changes of number entity."""
    mock_coordinator.data["air_flow_rate_manual"] = 50
    entity_config = ENTITY_MAPPINGS["number"]["air_flow_rate_manual"]
    number = ThesslaGreenNumber(mock_coordinator, "air_flow_rate_manual", entity_config)
    assert number.native_value == 50
    assert "scale_factor" not in number.extra_state_attributes

    mock_coordinator.data["air_flow_rate_manual"] = 75
    assert number.native_value == 75


def test_number_handles_missing_or_invalid_values(mock_coordinator):
    """Native value should be None when data is missing or non-numeric."""

    entity_config = ENTITY_MAPPINGS["number"]["air_flow_rate_manual"]
    number = ThesslaGreenNumber(mock_coordinator, "air_flow_rate_manual", entity_config)

    mock_coordinator.data.pop("air_flow_rate_manual", None)
    assert number.native_value is None

    mock_coordinator.data["air_flow_rate_manual"] = None
    assert number.native_value is None

    mock_coordinator.data["air_flow_rate_manual"] = "invalid"
    assert number.native_value is None


def test_number_set_value(mock_coordinator):
    """Test setting a new value on the number entity."""
    mock_coordinator.data["supply_air_temperature_manual"] = 20
    entity_config = ENTITY_MAPPINGS["number"]["supply_air_temperature_manual"]
    number = ThesslaGreenNumber(mock_coordinator, "supply_air_temperature_manual", entity_config)

    asyncio.run(number.async_set_native_value(22))
    mock_coordinator.async_write_register.assert_awaited_with(
        "supply_air_temperature_manual", 22, refresh=False, offset=0
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()


def test_number_set_value_modbus_failure(mock_coordinator):
    """Ensure Modbus errors are surfaced when setting the number."""
    mock_coordinator.data["supply_air_temperature_manual"] = 20
    entity_config = ENTITY_MAPPINGS["number"]["supply_air_temperature_manual"]
    number = ThesslaGreenNumber(mock_coordinator, "supply_air_temperature_manual", entity_config)

    mock_coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("fail"))
    with pytest.raises(ConnectionException):
        asyncio.run(number.async_set_native_value(22))
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_number_set_value_write_failure(mock_coordinator):
    """Ensure failures to write registers raise RuntimeError."""
    mock_coordinator.data["supply_air_temperature_manual"] = 20
    entity_config = ENTITY_MAPPINGS["number"]["supply_air_temperature_manual"]
    number = ThesslaGreenNumber(mock_coordinator, "supply_air_temperature_manual", entity_config)

    mock_coordinator.async_write_register = AsyncMock(return_value=False)
    with pytest.raises(RuntimeError):
        asyncio.run(number.async_set_native_value(22))
    mock_coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.parametrize("exc_cls", [ValueError, OSError])
def test_number_set_value_other_errors(mock_coordinator, exc_cls):
    """Ensure ValueError and OSError propagate when setting the number."""
    mock_coordinator.data["supply_air_temperature_manual"] = 20
    entity_config = ENTITY_MAPPINGS["number"]["supply_air_temperature_manual"]
    number = ThesslaGreenNumber(mock_coordinator, "supply_air_temperature_manual", entity_config)

    mock_coordinator.async_write_register = AsyncMock(side_effect=exc_cls("fail"))
    with pytest.raises(exc_cls):
        asyncio.run(number.async_set_native_value(22))
    mock_coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.parametrize(
    "register,value",
    [
        ("max_supply_air_flow_rate", 250),
        ("min_bypass_temperature", 10),
    ],
)
def test_new_number_entities(mock_coordinator, register, value):
    """Test number entities for newly added registers."""
    mock_coordinator.data[register] = value
    entity_config = ENTITY_MAPPINGS["number"][register]
    number = ThesslaGreenNumber(mock_coordinator, register, entity_config)
    assert number.native_value == value


@pytest.mark.asyncio
async def test_async_setup_creates_new_numbers(mock_coordinator, mock_config_entry):
    """Ensure setup creates number entities for new registers."""
    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    mock_config_entry.runtime_data = mock_coordinator

    mock_coordinator.available_registers.setdefault("holding_registers", set()).update(
        {"max_supply_air_flow_rate", "min_bypass_temperature"}
    )

    add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)
    entities = add_entities.call_args[0][0]
    names = {entity.register_name for entity in entities}
    assert {"max_supply_air_flow_rate", "min_bypass_temperature"} <= names


@pytest.mark.asyncio
async def test_async_setup_skips_missing_numbers(mock_coordinator, mock_config_entry):
    """Ensure no number entities are created when registers aren't detected."""
    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    mock_config_entry.runtime_data = mock_coordinator

    mock_coordinator.available_registers = {"holding_registers": set()}

    add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)
    add_entities.assert_not_called()


def test_number_invalid_register_raises(mock_coordinator):
    """Ensure unknown registers raise KeyError."""
    with pytest.raises(KeyError):
        ThesslaGreenNumber(mock_coordinator, "invalid_register", {})


def test_number_mappings_include_writable_registers():
    """Writable holding registers should expose number controls."""

    number_keys = ENTITY_MAPPINGS["number"]

    # Writable registers exposed only as numbers (not duplicated as sensors).
    assert "hood_exhaust_coef" in number_keys
    assert "hood_exhaust_coef" not in SENSOR_ENTITY_MAPPINGS
    assert "hood_supply_coef" in number_keys
    assert "fan_speed_1_coef" in number_keys

    # Read-only sensor registers must not expose number controls.
    assert "dac_supply" in SENSOR_ENTITY_MAPPINGS
    assert "dac_supply" not in number_keys


@pytest.mark.asyncio
@patch.dict(ENTITY_MAPPINGS["number"], {"invalid_register": {}}, clear=False)
async def test_async_setup_skips_unknown_register(mock_coordinator, mock_config_entry):
    """Ensure setup skips registers missing from HOLDING_REGISTERS."""
    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    mock_config_entry.runtime_data = mock_coordinator

    mock_coordinator.available_registers["holding_registers"] = {"invalid_register"}

    add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)
    add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_force_full_register_list_adds_missing_number(mock_coordinator, mock_config_entry):
    """Number entities are created from register map when forcing full list."""

    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    mock_config_entry.runtime_data = mock_coordinator

    mock_coordinator.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
        "calculated": set(),
    }
    mock_coordinator.force_full_register_list = True

    number_map = {"max_supply_air_flow_rate": {"translation_key": "max"}}

    with (
        patch.dict(ENTITY_MAPPINGS["number"], number_map, clear=True),
        patch.dict(
            mock_coordinator._register_maps["holding_registers"],
            {"max_supply_air_flow_rate": 1},
            clear=True,
        ),
    ):
        add_entities = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)
        created = {entity.register_name for entity in add_entities.call_args[0][0]}
        assert created == {"max_supply_air_flow_rate"}  # nosec B101


# ---------------------------------------------------------------------------
# Icon branch coverage tests (lines 164, 166, 168 of number.py)
# ---------------------------------------------------------------------------


def _make_number(mock_coordinator, register_name):
    """Helper: inject a fake register and return a ThesslaGreenNumber instance."""
    current_map = dict(mock_coordinator.get_register_map("holding_registers"))
    current_map[register_name] = 9990
    mock_coordinator.get_register_map = lambda register_type: (
        current_map if register_type == "holding_registers" else {}
    )
    return ThesslaGreenNumber(mock_coordinator, register_name, {})


def test_number_icon_duration(mock_coordinator):
    """Register name containing 'duration' gets mdi:timer icon (line 165)."""
    number = _make_number(mock_coordinator, "boost_duration")
    assert number._attr_icon == "mdi:timer"  # nosec B101


def test_number_icon_intensity(mock_coordinator):
    """Register name containing 'intensity' gets mdi:gauge icon (line 167)."""
    number = _make_number(mock_coordinator, "uv_intensity")
    assert number._attr_icon == "mdi:gauge"  # nosec B101


def test_number_icon_coef(mock_coordinator):
    """Register name containing 'coef' gets mdi:percent icon (line 169)."""
    number = _make_number(mock_coordinator, "hood_exhaust_coef")
    assert number._attr_icon == "mdi:percent"  # nosec B101


def test_number_icon_percentage(mock_coordinator):
    """Register name containing 'percentage' gets mdi:percent icon (line 169)."""
    number = _make_number(mock_coordinator, "min_percentage")
    assert number._attr_icon == "mdi:percent"  # nosec B101
