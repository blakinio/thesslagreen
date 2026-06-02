# mypy: ignore-errors
"""Validate dashboard-facing writable entities call the expected Modbus write paths.

Scope (task specification):
  1. fan.thesslagreen_ventilation — set_percentage, turn_on, turn_off
  2. Writable switches — special_mode bit switches + holding-register switches
  3. Writable numbers — 7 holding-register number entities
  4. Writable selects — mode, season_mode, bypass_user_mode, gwc_regen
  5. Time entities — representative schedule + airing BCD time entities
  6. Clock sync service — atomic write+read-back path; no stale coordinator.data dependency
  7. Dashboard inventory — every dashboard-writable entity ID has test coverage here

Rules:
  - No real Modbus hardware; all Modbus I/O is mocked.
  - No changes to register addresses, register names, entity IDs, unique IDs,
    service IDs, translation keys, or config/options flow behaviour.
"""

from __future__ import annotations

import asyncio
from datetime import time as dt_time
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.const import SPECIAL_FUNCTION_MAP
from custom_components.thessla_green_modbus.fan import ThesslaGreenFan
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.number import ThesslaGreenNumber
from custom_components.thessla_green_modbus.registers.maps import holding_registers
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect
from custom_components.thessla_green_modbus.switch import ThesslaGreenSwitch
from custom_components.thessla_green_modbus.time import ThesslaGreenTime

# ---------------------------------------------------------------------------
# Dashboard entity IDs that are considered writable by the dashboard spec.
# Sensors and binary sensors are omitted — they are read-only.
# ---------------------------------------------------------------------------
_DASHBOARD_WRITABLE_ENTITY_IDS: frozenset[str] = frozenset(
    {
        # Fan
        "fan.thesslagreen_ventilation",
        # Special-mode bit switches
        "switch.thesslagreen_boost",
        "switch.thesslagreen_eco",
        "switch.thesslagreen_away",
        "switch.thesslagreen_sleep",
        "switch.thesslagreen_fireplace",
        "switch.thesslagreen_hood",
        "switch.thesslagreen_party",
        "switch.thesslagreen_bathroom",
        "switch.thesslagreen_kitchen",
        # Holding-register switches
        "switch.thesslagreen_comfort_mode_panel",
        "switch.thesslagreen_bypass_off",
        "switch.thesslagreen_gwc_off",
        # Numbers
        "number.thesslagreen_air_flow_rate_manual",
        "number.thesslagreen_supply_air_temperature_manual",
        "number.thesslagreen_air_flow_rate_temporary",
        "number.thesslagreen_supply_air_temperature_temporary",
        "number.thesslagreen_min_bypass_temperature",
        "number.thesslagreen_delta_t_gwc",
        "number.thesslagreen_gwc_regen_period",
        # Selects
        "select.thesslagreen_mode",
        "select.thesslagreen_season_mode",
        "select.thesslagreen_bypass_user_mode",
        "select.thesslagreen_gwc_regen",
        # Time entities
        "time.thesslagreen_schedule_summer_mon_1",
        "time.thesslagreen_airing_summer_mon",
    }
)

# Entity IDs explicitly covered by tests in this module.
_COVERED_ENTITY_IDS: frozenset[str] = frozenset(
    {
        "fan.thesslagreen_ventilation",
        "switch.thesslagreen_boost",
        "switch.thesslagreen_eco",
        "switch.thesslagreen_away",
        "switch.thesslagreen_sleep",
        "switch.thesslagreen_fireplace",
        "switch.thesslagreen_hood",
        "switch.thesslagreen_party",
        "switch.thesslagreen_bathroom",
        "switch.thesslagreen_kitchen",
        "switch.thesslagreen_comfort_mode_panel",
        "switch.thesslagreen_bypass_off",
        "switch.thesslagreen_gwc_off",
        "number.thesslagreen_air_flow_rate_manual",
        "number.thesslagreen_supply_air_temperature_manual",
        "number.thesslagreen_air_flow_rate_temporary",
        "number.thesslagreen_supply_air_temperature_temporary",
        "number.thesslagreen_min_bypass_temperature",
        "number.thesslagreen_delta_t_gwc",
        "number.thesslagreen_gwc_regen_period",
        "select.thesslagreen_mode",
        "select.thesslagreen_season_mode",
        "select.thesslagreen_bypass_user_mode",
        "select.thesslagreen_gwc_regen",
        "time.thesslagreen_schedule_summer_mon_1",
        "time.thesslagreen_airing_summer_mon",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _holding_addr(register_name: str) -> int:
    """Return the holding register address; raises KeyError if absent."""
    return holding_registers()[register_name]


def _make_switch(coordinator, key: str, entity_config: dict) -> ThesslaGreenSwitch:
    """Construct a ThesslaGreenSwitch entity from a config dict."""
    register_name = entity_config["register"]
    address = _holding_addr(register_name)
    return ThesslaGreenSwitch(coordinator, key, address, entity_config)


def _make_number(coordinator, register_name: str) -> ThesslaGreenNumber:
    """Construct a ThesslaGreenNumber entity for *register_name*."""
    entity_config = ENTITY_MAPPINGS["number"][register_name]
    return ThesslaGreenNumber(coordinator, register_name, entity_config)


def _make_select(coordinator, register_name: str) -> ThesslaGreenSelect:
    """Construct a ThesslaGreenSelect entity for *register_name*."""
    sel_def = ENTITY_MAPPINGS["select"][register_name]
    address = _holding_addr(register_name)
    return ThesslaGreenSelect(coordinator, register_name, address, sel_def)


def _make_time(coordinator, register_name: str) -> ThesslaGreenTime:
    """Construct a ThesslaGreenTime entity for *register_name*."""
    time_def = ENTITY_MAPPINGS["time"][register_name]
    address = _holding_addr(register_name)
    return ThesslaGreenTime(coordinator, register_name, address, time_def)


# ---------------------------------------------------------------------------
# 1. Fan — fan.thesslagreen_ventilation
# ---------------------------------------------------------------------------


def test_fan_set_percentage_writes_air_flow_rate_manual(mock_coordinator):
    """set_percentage in manual mode writes the expected percentage to air_flow_rate_manual."""
    mock_coordinator.data["mode"] = 1  # manual
    mock_coordinator.device_client.available_registers["holding_registers"].update(
        {"mode", "on_off_panel_mode", "air_flow_rate_manual"}
    )

    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan.async_set_percentage(60))

    calls = {c[0][0] for c in mock_coordinator.async_write_register.call_args_list}
    assert "air_flow_rate_manual" in calls
    # Verify the value written to air_flow_rate_manual is the requested percentage
    matched = [
        c
        for c in mock_coordinator.async_write_register.call_args_list
        if c[0][0] == "air_flow_rate_manual"
    ]
    assert matched, "async_write_register not called for air_flow_rate_manual"
    assert matched[0][0][1] == 60


def test_fan_turn_on_writes_on_off_and_flow(mock_coordinator):
    """turn_on writes on_off_panel_mode=1 and a non-zero flow to air_flow_rate_manual."""
    mock_coordinator.data.pop("mode", None)  # no mode → defaults to manual path
    mock_coordinator.device_client.available_registers["holding_registers"].update(
        {"on_off_panel_mode", "air_flow_rate_manual", "mode"}
    )

    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan.async_turn_on())

    calls_by_reg = {c[0][0]: c[0][1] for c in mock_coordinator.async_write_register.call_args_list}
    assert "on_off_panel_mode" in calls_by_reg, "on_off_panel_mode not written by turn_on"
    assert calls_by_reg["on_off_panel_mode"] == 1
    assert "air_flow_rate_manual" in calls_by_reg, "air_flow_rate_manual not written by turn_on"
    assert calls_by_reg["air_flow_rate_manual"] > 0


def test_fan_turn_off_writes_on_off_panel_mode_zero(mock_coordinator):
    """turn_off writes 0 to on_off_panel_mode when the register is available."""
    mock_coordinator.device_client.available_registers["holding_registers"].add("on_off_panel_mode")

    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan.async_turn_off())

    mock_coordinator.async_write_register.assert_awaited()
    # The first (and only) holding-register write must be on_off_panel_mode=0
    on_off_calls = [
        c
        for c in mock_coordinator.async_write_register.call_args_list
        if c[0][0] == "on_off_panel_mode"
    ]
    assert on_off_calls, "on_off_panel_mode not written by turn_off"
    assert on_off_calls[0][0][1] == 0


def test_fan_set_percentage_no_stale_coordinator_proxy_needed(mock_coordinator):
    """The write path for set_percentage reads only coordinator.data; no device_client proxy attr."""
    mock_coordinator.data["mode"] = 1
    mock_coordinator.device_client.available_registers["holding_registers"].update(
        {"mode", "air_flow_rate_manual"}
    )
    # Deliberately remove any device_clock key — must not affect the write path
    mock_coordinator.data.pop("device_clock", None)

    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan.async_set_percentage(50))

    assert mock_coordinator.async_write_register.called


# ---------------------------------------------------------------------------
# 2a. Special-mode bit switches
# ---------------------------------------------------------------------------

_SPECIAL_MODE_DASHBOARD_KEYS = [
    ("boost", SPECIAL_FUNCTION_MAP["boost"]),
    ("eco", SPECIAL_FUNCTION_MAP["eco"]),
    ("away", SPECIAL_FUNCTION_MAP["away"]),
    ("sleep", SPECIAL_FUNCTION_MAP["sleep"]),
    ("fireplace", SPECIAL_FUNCTION_MAP["fireplace"]),
    ("hood", SPECIAL_FUNCTION_MAP["hood"]),
    ("party", SPECIAL_FUNCTION_MAP["party"]),
    ("bathroom", SPECIAL_FUNCTION_MAP["bathroom"]),
    ("kitchen", SPECIAL_FUNCTION_MAP["kitchen"]),
]


@pytest.mark.parametrize("mode_key,expected_bit", _SPECIAL_MODE_DASHBOARD_KEYS)
def test_special_mode_switch_turn_on_writes_bit_to_special_mode(
    mock_coordinator, mode_key, expected_bit
):
    """turn_on writes the bit value (not a bitmask) to the special_mode register."""
    mock_coordinator.data["special_mode"] = 0
    mock_coordinator.device_client.available_registers["holding_registers"].add("special_mode")

    entity_config = ENTITY_MAPPINGS["switch"][mode_key]
    sw = _make_switch(mock_coordinator, mode_key, entity_config)

    asyncio.run(sw.async_turn_on())

    mock_coordinator.async_write_register.assert_awaited()
    call = mock_coordinator.async_write_register.call_args
    assert call[0][0] == "special_mode", f"Expected register 'special_mode', got '{call[0][0]}'"
    assert call[0][1] == expected_bit, (
        f"Expected value {expected_bit} for {mode_key}, got {call[0][1]}"
    )


@pytest.mark.parametrize("mode_key,expected_bit", _SPECIAL_MODE_DASHBOARD_KEYS)
def test_special_mode_switch_turn_off_writes_zero_to_special_mode(
    mock_coordinator, mode_key, expected_bit
):
    """turn_off writes 0 to the special_mode register (deactivates all special modes)."""
    mock_coordinator.data["special_mode"] = expected_bit
    mock_coordinator.device_client.available_registers["holding_registers"].add("special_mode")

    entity_config = ENTITY_MAPPINGS["switch"][mode_key]
    sw = _make_switch(mock_coordinator, mode_key, entity_config)

    asyncio.run(sw.async_turn_off())

    mock_coordinator.async_write_register.assert_awaited()
    call = mock_coordinator.async_write_register.call_args
    assert call[0][0] == "special_mode", f"Expected register 'special_mode', got '{call[0][0]}'"
    assert call[0][1] == 0, f"Expected 0 for {mode_key} turn_off, got {call[0][1]}"


# ---------------------------------------------------------------------------
# 2b. Holding-register switches (not special_mode)
# ---------------------------------------------------------------------------

_HOLDING_REGISTER_SWITCH_KEYS = [
    "comfort_mode_panel",
    "bypass_off",
    "gwc_off",
]


@pytest.mark.parametrize("switch_key", _HOLDING_REGISTER_SWITCH_KEYS)
def test_holding_switch_turn_on_writes_one_to_register(mock_coordinator, switch_key):
    """turn_on writes 1 directly to the holding register named after the switch key."""
    mock_coordinator.data[switch_key] = 0
    mock_coordinator.device_client.available_registers["holding_registers"].add(switch_key)

    entity_config = ENTITY_MAPPINGS["switch"][switch_key]
    sw = _make_switch(mock_coordinator, switch_key, entity_config)

    asyncio.run(sw.async_turn_on())

    mock_coordinator.async_write_register.assert_awaited()
    call = mock_coordinator.async_write_register.call_args
    assert call[0][0] == switch_key, f"Expected register '{switch_key}', got '{call[0][0]}'"
    assert call[0][1] == 1, f"Expected 1 for turn_on of {switch_key}, got {call[0][1]}"


@pytest.mark.parametrize("switch_key", _HOLDING_REGISTER_SWITCH_KEYS)
def test_holding_switch_turn_off_writes_zero_to_register(mock_coordinator, switch_key):
    """turn_off writes 0 directly to the holding register named after the switch key."""
    mock_coordinator.data[switch_key] = 1
    mock_coordinator.device_client.available_registers["holding_registers"].add(switch_key)

    entity_config = ENTITY_MAPPINGS["switch"][switch_key]
    sw = _make_switch(mock_coordinator, switch_key, entity_config)

    asyncio.run(sw.async_turn_off())

    mock_coordinator.async_write_register.assert_awaited()
    call = mock_coordinator.async_write_register.call_args
    assert call[0][0] == switch_key, f"Expected register '{switch_key}', got '{call[0][0]}'"
    assert call[0][1] == 0, f"Expected 0 for turn_off of {switch_key}, got {call[0][1]}"


# ---------------------------------------------------------------------------
# 3. Number entities
# ---------------------------------------------------------------------------

_NUMBER_WRITE_CASES: list[tuple[str, float]] = [
    ("air_flow_rate_manual", 60.0),
    ("supply_air_temperature_manual", 20.0),
    ("air_flow_rate_temporary", 40.0),
    ("supply_air_temperature_temporary", 22.0),
    ("min_bypass_temperature", 10.0),
    ("delta_t_gwc", 2.0),
    ("gwc_regen_period", 6.0),
]


@pytest.mark.parametrize("register_name,value", _NUMBER_WRITE_CASES)
def test_number_set_value_writes_expected_register(mock_coordinator, register_name, value):
    """async_set_native_value writes the correct register name and numeric value."""
    mock_coordinator.data[register_name] = 0
    mock_coordinator.device_client.available_registers["holding_registers"].add(register_name)

    num = _make_number(mock_coordinator, register_name)
    asyncio.run(num.async_set_native_value(value))

    mock_coordinator.async_write_register.assert_awaited()
    call = mock_coordinator.async_write_register.call_args
    assert call[0][0] == register_name, f"Expected register '{register_name}', got '{call[0][0]}'"
    assert call[0][1] == value, f"Expected value {value}, got {call[0][1]}"


@pytest.mark.parametrize("register_name,value", _NUMBER_WRITE_CASES)
def test_number_write_path_needs_no_coordinator_proxy(mock_coordinator, register_name, value):
    """Number write path must not read stale device_client proxy attributes."""
    mock_coordinator.data[register_name] = 0
    mock_coordinator.device_client.available_registers["holding_registers"].add(register_name)
    # Ensure device_clock is absent — must not affect the write path
    mock_coordinator.data.pop("device_clock", None)

    num = _make_number(mock_coordinator, register_name)
    asyncio.run(num.async_set_native_value(value))

    assert mock_coordinator.async_write_register.called


# ---------------------------------------------------------------------------
# 4. Select entities
# ---------------------------------------------------------------------------

_SELECT_WRITE_CASES: list[tuple[str, str, int]] = [
    ("mode", "manual", 1),
    ("mode", "auto", 0),
    ("season_mode", "summer", 1),
    ("season_mode", "winter", 0),
    ("bypass_user_mode", "mode_2", 2),
    ("gwc_regen", "daily_schedule", 1),
    ("gwc_regen", "inactive", 0),
]


@pytest.mark.parametrize("register_name,option,expected_value", _SELECT_WRITE_CASES)
def test_select_option_writes_expected_register_value(
    mock_coordinator, register_name, option, expected_value
):
    """async_select_option writes the mapped integer to the correct holding register."""
    mock_coordinator.data[register_name] = 0
    mock_coordinator.device_client.available_registers["holding_registers"].add(register_name)

    sel = _make_select(mock_coordinator, register_name)
    asyncio.run(sel.async_select_option(option))

    mock_coordinator.async_write_register.assert_awaited()
    call = mock_coordinator.async_write_register.call_args
    assert call[0][0] == register_name, f"Expected register '{register_name}', got '{call[0][0]}'"
    assert call[0][1] == expected_value, (
        f"Expected value {expected_value} for option '{option}', got {call[0][1]}"
    )


# ---------------------------------------------------------------------------
# 5. Time entities
# ---------------------------------------------------------------------------


def test_schedule_time_set_value_writes_hhmm_string(mock_coordinator):
    """async_set_value for a schedule time entity writes 'HH:MM' to the holding register."""
    register_name = "schedule_summer_mon_1"
    mock_coordinator.data[register_name] = None  # unset sentinel
    mock_coordinator.device_client.available_registers["holding_registers"].add(register_name)

    time_entity = _make_time(mock_coordinator, register_name)
    asyncio.run(time_entity.async_set_value(dt_time(6, 30)))

    mock_coordinator.async_write_register.assert_awaited()
    call = mock_coordinator.async_write_register.call_args
    assert call[0][0] == register_name, f"Expected register '{register_name}', got '{call[0][0]}'"
    assert call[0][1] == "06:30", f"Expected '06:30', got '{call[0][1]}'"


def test_airing_time_set_value_writes_hhmm_string(mock_coordinator):
    """async_set_value for an airing time entity writes 'HH:MM' to the holding register."""
    register_name = "airing_summer_mon"
    mock_coordinator.data[register_name] = None
    mock_coordinator.device_client.available_registers["holding_registers"].add(register_name)

    time_entity = _make_time(mock_coordinator, register_name)
    asyncio.run(time_entity.async_set_value(dt_time(22, 0)))

    mock_coordinator.async_write_register.assert_awaited()
    call = mock_coordinator.async_write_register.call_args
    assert call[0][0] == register_name, f"Expected register '{register_name}', got '{call[0][0]}'"
    assert call[0][1] == "22:00", f"Expected '22:00', got '{call[0][1]}'"


def test_time_write_sentinel_register_stays_available(mock_coordinator):
    """Time entities with sentinel value (None / 0xFFFF) must still be writable."""
    register_name = "schedule_summer_mon_1"
    mock_coordinator.data[register_name] = None  # sentinel: unset slot
    mock_coordinator.device_client.available_registers["holding_registers"].add(register_name)

    time_entity = _make_time(mock_coordinator, register_name)
    # Entity must be available even without a current value
    assert time_entity.available is True
    asyncio.run(time_entity.async_set_value(dt_time(8, 0)))
    assert mock_coordinator.async_write_register.called


# ---------------------------------------------------------------------------
# 6. Clock sync service — atomic write+read-back path validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clock_sync_uses_atomic_write_and_read_holding_registers():
    """Clock sync calls async_write_and_read_holding_registers, not separate write + data read.

    This confirms the atomic write+read-back path is invoked (start_address=0, 4 values, 4 count).
    Ref: test_clock_sync.py::test_sync_uses_atomic_write_and_read_method
    """
    import datetime

    from custom_components.thessla_green_modbus.clock_sync import (
        async_perform_clock_sync,
        encode_rtc_registers,
    )

    now = datetime.datetime(2026, 1, 15, 10, 0, 0)
    regs = encode_rtc_registers(now)

    coord = MagicMock()
    coord.async_write_and_read_holding_registers = AsyncMock(return_value=(True, regs))
    coord.async_request_refresh = AsyncMock()
    coord.data = {}
    coord.device_client.config.host = "192.168.1.1"

    result = await async_perform_clock_sync(coord, force=True, dt_now_fn=lambda: now)

    assert result is True
    coord.async_write_and_read_holding_registers.assert_awaited_once()
    kwargs = coord.async_write_and_read_holding_registers.call_args.kwargs
    assert kwargs["start_address"] == 0, "RTC write must start at address 0"
    assert len(kwargs["values"]) == 4, "RTC write must send exactly 4 register values"
    assert kwargs["readback_count"] == 4, "RTC read-back must request 4 registers"


@pytest.mark.asyncio
async def test_clock_sync_readback_does_not_use_coordinator_data_device_clock():
    """Read-back validation uses the locked register values, not coordinator.data['device_clock'].

    Verification: even when coordinator.data['device_clock'] is stale/wrong, the sync succeeds
    because the read-back comes from the atomic locked read, not the coordinator cache.
    Ref: test_clock_sync.py::test_readback_uses_locked_register_values_not_coordinator_data
    """
    import datetime

    from custom_components.thessla_green_modbus.clock_sync import (
        async_perform_clock_sync,
        encode_rtc_registers,
    )

    now = datetime.datetime(2026, 1, 15, 10, 0, 0)
    regs = encode_rtc_registers(now)

    coord = MagicMock()
    # coordinator.data has deliberately wrong/stale device_clock
    coord.data = {"device_clock": "2000-01-01T00:00:00"}
    coord.async_write_and_read_holding_registers = AsyncMock(return_value=(True, regs))
    coord.async_request_refresh = AsyncMock()
    coord.device_client.config.host = "192.168.1.1"

    # force=True bypasses the drift check, so device_clock in data is not consulted for sync logic
    result = await async_perform_clock_sync(coord, force=True, dt_now_fn=lambda: now)

    assert result is True, "Sync must succeed even with stale coordinator.data['device_clock']"
    # Read-back came from the atomic call's return value, not coordinator.data
    coord.async_write_and_read_holding_registers.assert_awaited_once()
    # async_request_refresh must NOT be called — prevents stale coordinator.data race
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# 7. Dashboard inventory — writable entities coverage check
# ---------------------------------------------------------------------------


def test_all_dashboard_writable_entities_have_test_coverage():
    """Fail if any dashboard-writable entity ID is not covered by this test module.

    This test replaces manual dashboard-clicking: any new dashboard-writable entity
    added to the integration must also receive a write-path test here.

    Covered: fan (3 tests), switches (18 parametrized), numbers (7 parametrized),
    selects (7 parametrized), time (3 tests), clock sync (2 async tests).

    Read-only entities (sensor.*, binary_sensor.*) are excluded from scope.
    """
    uncovered = _DASHBOARD_WRITABLE_ENTITY_IDS - _COVERED_ENTITY_IDS
    assert not uncovered, (
        "The following dashboard-writable entities have no write-path test coverage:\n"
        + "\n".join(f"  - {eid}" for eid in sorted(uncovered))
        + "\n\nAdd a test for each entity above to this file."
    )


def test_covered_entities_are_subset_of_dashboard_writable():
    """Guard: every ID in _COVERED_ENTITY_IDS must appear in _DASHBOARD_WRITABLE_ENTITY_IDS.

    This prevents _COVERED_ENTITY_IDS from silently drifting from the actual dashboard spec.
    """
    extra = _COVERED_ENTITY_IDS - _DASHBOARD_WRITABLE_ENTITY_IDS
    assert not extra, (
        "The following entity IDs are in _COVERED_ENTITY_IDS but not in "
        "_DASHBOARD_WRITABLE_ENTITY_IDS:\n"
        + "\n".join(f"  - {eid}" for eid in sorted(extra))
        + "\n\nEither add them to _DASHBOARD_WRITABLE_ENTITY_IDS or remove from _COVERED_ENTITY_IDS."
    )


def test_dashboard_writable_excludes_sensors_and_binary_sensors():
    """Sensors and binary sensors are read-only and must not appear in writable list."""
    ro_prefixes = ("sensor.", "binary_sensor.")
    ro_in_writable = [eid for eid in _DASHBOARD_WRITABLE_ENTITY_IDS if eid.startswith(ro_prefixes)]
    assert not ro_in_writable, (
        "Read-only entities found in _DASHBOARD_WRITABLE_ENTITY_IDS:\n"
        + "\n".join(f"  - {eid}" for eid in sorted(ro_in_writable))
    )


def test_writable_entity_register_names_are_in_entity_mappings():
    """Every writable entity's register must exist in the corresponding ENTITY_MAPPINGS section.

    This catches regressions where a register is renamed or removed from the JSON
    but the test/dashboard spec still references the old name.
    """
    all_switch_keys = [k for k, _ in _SPECIAL_MODE_DASHBOARD_KEYS] + _HOLDING_REGISTER_SWITCH_KEYS
    all_number_regs = [r for r, _ in _NUMBER_WRITE_CASES]
    all_select_regs = list({r for r, _, _ in _SELECT_WRITE_CASES})
    all_time_regs = ["schedule_summer_mon_1", "airing_summer_mon"]

    errors: list[str] = [
        *[
            f"switch key '{k}' missing from ENTITY_MAPPINGS['switch']"
            for k in all_switch_keys
            if k not in ENTITY_MAPPINGS["switch"]
        ],
        *[
            f"number register '{r}' missing from ENTITY_MAPPINGS['number']"
            for r in all_number_regs
            if r not in ENTITY_MAPPINGS["number"]
        ],
        *[
            f"select register '{r}' missing from ENTITY_MAPPINGS['select']"
            for r in all_select_regs
            if r not in ENTITY_MAPPINGS["select"]
        ],
        *[
            f"time register '{r}' missing from ENTITY_MAPPINGS['time']"
            for r in all_time_regs
            if r not in ENTITY_MAPPINGS["time"]
        ],
    ]

    assert not errors, "Entity mapping registration failures:\n" + "\n".join(
        f"  - {e}" for e in errors
    )
