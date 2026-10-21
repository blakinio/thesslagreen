"""Regression contracts from supplied Home 06.2021.01 / AirPack4 08.2022.01.

These tests run original runtime code, mocking only HA/transport boundaries.
No physical connection or write is permitted by this module.
"""

from __future__ import annotations

import asyncio
from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus import mappings as entity_mappings
from custom_components.thessla_green_modbus.const import (
    LEGACY_SPECIAL_SWITCH_IDENTITIES,
    SPECIAL_FUNCTION_MAP,
)
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.coordinator import update as update_mod
from custom_components.thessla_green_modbus.core.schedule_values import complete_schedule_value
from custom_components.thessla_green_modbus.core.write_path import encode_write_value
from custom_components.thessla_green_modbus.device_profile import validate_filter_command
from custom_components.thessla_green_modbus.register_defs_cache import get_register_definitions
from custom_components.thessla_green_modbus.registers.special_modes import SPECIAL_MODES
from custom_components.thessla_green_modbus.services.handlers_maintenance import (
    _filter_replacement_commands,
)
from custom_components.thessla_green_modbus.services.handlers_parameters import (
    _bypass_steps,
    _gwc_steps,
)
from custom_components.thessla_green_modbus.services.handlers_schedule import (
    register_schedule_services,
)
from custom_components.thessla_green_modbus.utils import decode_bcd_time
from homeassistant.exceptions import ServiceValidationError


@pytest.fixture(scope="module", autouse=True)
def initialize_entity_mappings():
    """Exercise the real setup path even under --noconftest on current HA."""
    from custom_components.thessla_green_modbus.mappings import _run_build_entity_mappings

    _run_build_entity_mappings()


@pytest.fixture
def regs():
    return get_register_definitions()


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("none", 0),
        ("hood", 1),
        ("fireplace", 2),
        ("airing_doorbell", 3),
        ("airing_switch", 4),
        ("airing_hygrostat", 5),
        ("airing_air_quality", 6),
        ("airing_manual", 7),
        ("airing_auto", 8),
        ("airing_manual_timed", 9),
        ("open_windows", 10),
        ("empty_house", 11),
    ],
)
def test_vendor_special_mode_value(name, code, regs):
    """Both PDFs p.11: protocol enum must not depend on UI option order."""
    assert SPECIAL_MODES[name] == SPECIAL_FUNCTION_MAP[name] == code
    assert regs["special_mode"].encode(name) == code
    assert regs["special_mode"].decode(code) == name


def test_legacy_switch_identity_is_not_protocol_command():
    mappings = entity_mappings.ENTITY_MAPPINGS["switch"]
    assert mappings["hood"]["bit"] == LEGACY_SPECIAL_SWITCH_IDENTITIES["hood"] == 6
    assert mappings["hood"]["protocol_value"] == 1
    assert mappings["fireplace"]["bit"] == 5
    assert mappings["fireplace"]["protocol_value"] == 2
    assert mappings["boost"]["protocol_value"] == 7
    assert mappings["away"]["protocol_value"] == 11
    for name in ("eco", "sleep", "party", "bathroom", "kitchen", "summer", "winter"):
        assert mappings[name]["protocol_value"] is None


def test_season_select_matches_manufacturer():
    assert entity_mappings.ENTITY_MAPPINGS["select"]["season_mode"]["states"] == {
        "summer": 0,
        "winter": 1,
    }


@pytest.mark.parametrize("name", ["supply_air_flow", "exhaust_air_flow"])
def test_cf_inactive_is_not_numeric_flow(name, regs):
    assert regs[name].decode(65535) is None
    assert regs[name].decode(0) == 0
    assert regs[name].decode(99) == 99


@pytest.mark.parametrize(
    ("raw", "expected"), [(238, -18), (255, -1), (129, -127), (127, 127), (0, 0)]
)
def test_rtc_signed_8_bit_roundtrip(raw, expected, regs):
    assert regs["rtc_cal"].decode(raw) == expected
    assert regs["rtc_cal"].encode(expected) == raw


@pytest.mark.parametrize("value", [-128, 128, 238, 0.5, True, float("nan"), float("inf")])
def test_rtc_invalid_write_rejected(value, regs):
    with pytest.raises((ValueError, OverflowError)):
        regs["rtc_cal"].encode(value)


@pytest.mark.parametrize(
    ("name", "raw", "expected"), [("cf_version", 13, "0.13"), ("exp_version", 0x010D, "1.13")]
)
def test_module_version_bytes(name, raw, expected, regs):
    assert regs[name].decode(raw) == expected


def test_filter_date_vendor_example(regs):
    assert regs["filter_supply_date_limit_get"].decode(0x2D62) == "2022-11-02"
    assert regs["filter_supply_date_limit_get"].decode(0) is None


@pytest.mark.parametrize("name", ["airing_summer_mon", "manual_airing_time_to_start"])
def test_disabled_airing_is_not_midnight(name, regs):
    assert regs[name].decode(0x2400) is None
    assert regs[name].decode(0) == "00:00"
    assert regs[name].encode("disabled") == 0x2400
    assert regs[name].encode("00:00") == 0


def test_disabled_schedule_contract(regs):
    assert regs["schedule_summer_mon_1"].decode(0xA200) is None
    assert regs["schedule_summer_mon_1"].encode("disabled") == 0xA200
    assert decode_bcd_time(0x0630) == "06:30"


def test_aatt_vendor_example_and_preservation(regs):
    reg = regs["setting_summer_mon_1"]
    assert reg.decode(0x142C) == {"airflow_pct": 20, "temp_c": 22.0}
    assert reg.encode({"airflow_pct": 20, "temp_c": 22}) == 0x142C
    completed = complete_schedule_value(30, reg.decode(0x142C))
    assert reg.encode(completed) == 0x1E2C
    with pytest.raises(ValueError):
        complete_schedule_value(30, None)
    with pytest.raises(ValueError):
        reg.encode(30)
    with pytest.raises(ValueError):
        reg.encode(0x1E2C)


@pytest.mark.parametrize(
    "value",
    [
        {"airflow_pct": 30, "temp_c": 0},
        {"airflow_pct": 151, "temp_c": 22},
        {"airflow_pct": 30, "temp_c": 22.25},
        {"airflow_pct": 30, "temp_c": float("nan")},
    ],
)
def test_invalid_aatt_has_no_silent_wrapping(value, regs):
    with pytest.raises(ValueError):
        regs["setting_summer_mon_1"].encode(value)


def test_encoded_words_cannot_overflow():
    reg = SimpleNamespace(length=1, encode=lambda _: 0x1E0C00)
    with pytest.raises(ValueError):
        encode_write_value("test", reg, 0, 0)


@pytest.mark.asyncio
async def test_cancel_waiting_lock_does_not_poison_following_poll(monkeypatch):
    lock = asyncio.Lock()
    await lock.acquire()
    client = SimpleNamespace(_update_in_progress=False, _write_lock=lock)
    coord = SimpleNamespace(
        device_client=client, data={"cached": True}, _shutting_down=False, _disconnect=AsyncMock()
    )
    fresh = AsyncMock(return_value={"fresh": True})
    monkeypatch.setattr(update_mod, "run_update_cycle", fresh)
    task = asyncio.create_task(update_mod.async_update_data(coord))
    await asyncio.sleep(0)
    assert client._update_in_progress
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not client._update_in_progress
    coord._disconnect.assert_not_awaited()  # the other writer still owns transport
    lock.release()
    assert await update_mod.async_update_data(coord) == {"fresh": True}
    fresh.assert_awaited_once()


def test_reauth_callback_not_wrapped_in_task():
    entry = SimpleNamespace(async_start_reauth=MagicMock(return_value=None))
    hass = SimpleNamespace(async_create_task=MagicMock())
    coord = SimpleNamespace(
        _reauth_scheduled=False,
        entry=entry,
        hass=hass,
        _device_client=SimpleNamespace(_device_name="test"),
    )
    ThesslaGreenModbusCoordinator._trigger_reauth(coord, "invalid_auth")
    entry.async_start_reauth.assert_called_once_with(hass)
    hass.async_create_task.assert_not_called()


@pytest.mark.parametrize(
    "name", ["required_temperature", "bypass_mode", "gwc_mode", "supply_air_flow"]
)
def test_readonly_is_rejected_before_connection(name):
    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(), host="localhost", port=502, slave_id=10, name="test"
    )
    assert coord._resolve_write_definition(name) is None


@pytest.mark.parametrize(
    ("family", "value"),
    [("airpack_home", 1), ("airpack_home", 4), ("airpack4", 17), ("airpack4", 33)],
)
def test_family_filter_command_allowed(family, value):
    validate_filter_command(family, value)


@pytest.mark.parametrize(
    ("family", "value"),
    [("unspecified", 1), ("airpack_home", 17), ("airpack4", 4), ("airpack4", 1)],
)
def test_wrong_family_filter_command_blocked(family, value):
    with pytest.raises(ValueError):
        validate_filter_command(family, value)


def test_home_presostat_reset_rejected_without_write():
    coord = SimpleNamespace(
        entry=SimpleNamespace(options={"device_family": "airpack_home"}), data={"filter_change": 1}
    )
    with pytest.raises(ServiceValidationError, match="presostat"):
        _filter_replacement_commands(
            coord, {"filter_type": "cleanpad_pure"}, SimpleNamespace(normalize_option=lambda v: v)
        )


def test_ap4_replacement_has_direction_and_confirmation():
    coord = SimpleNamespace(
        entry=MagicMock(options={"device_family": "airpack4"}, data={}, entry_id="test"), data={}
    )
    assert _filter_replacement_commands(
        coord, {"direction": "both", "confirm_without_afc": True}, None
    ) == [17, 33]
    with pytest.raises(ServiceValidationError):
        _filter_replacement_commands(coord, {"direction": "both"}, None)


def test_bypass_and_gwc_target_control_not_status():
    deps = SimpleNamespace(normalize_option=lambda v: v)
    assert _bypass_steps(SimpleNamespace(data={"mode": "auto"}), deps)[0][:2] == ("bypass_off", 0)
    assert _bypass_steps(SimpleNamespace(data={"mode": "closed"}), deps)[0][:2] == ("bypass_off", 1)
    assert _gwc_steps(SimpleNamespace(data={"mode": "off"}), deps)[0][:2] == ("gwc_off", 1)
    with pytest.raises(ServiceValidationError):
        _bypass_steps(SimpleNamespace(data={"mode": "open"}), deps)
    with pytest.raises(ServiceValidationError):
        _gwc_steps(SimpleNamespace(data={"mode": "forced"}), deps)


@pytest.mark.asyncio
async def test_schedule_service_encodes_once(regs):
    handlers = {}
    hass = SimpleNamespace(
        services=SimpleNamespace(async_register=lambda d, n, h, s: handlers.update({n: h}))
    )
    coord = SimpleNamespace(
        device_client=SimpleNamespace(available_registers={"holding_registers": set(regs)}),
        async_request_refresh=AsyncMock(),
    )
    writes = []

    async def write(c, name, value, *args):
        encoded = regs[name].encode(value)
        writes.append((name, encoded))
        return True

    deps = SimpleNamespace(
        domain="test",
        normalize_option=lambda v: v,
        day_to_device_key={"monday": "mon"},
        iter_target_coordinators=AsyncMock(return_value=[("climate.test", coord)]),
        write_register=write,
        logger=MagicMock(),
    )
    register_schedule_services(hass, deps)
    await handlers["set_airflow_schedule"](
        SimpleNamespace(
            data={
                "day": "monday",
                "period": 1,
                "start_time": time(6, 30),
                "airflow_rate": 30,
                "temperature": 22.0,
            }
        )
    )
    assert writes == [("setting_summer_mon_1", 0x1E2C), ("schedule_summer_mon_1", 0x0630)]
    writes.clear()
    await handlers["set_airflow_schedule"](
        SimpleNamespace(data={"day": "monday", "period": 1, "enabled": False})
    )
    assert writes == [("schedule_summer_mon_1", 0xA200)]


@pytest.mark.parametrize(
    ("start", "values"),
    [
        (8190, [22]),
        (4330, [1]),
        (4263, [2]),
        (10, [1]),
        (4400, [2, 65536, 1]),
        (4400, [2, -1, 1]),
        (65535, [1, 2]),
    ],
)
def test_raw_multireg_write_gate_rejects_unknown_readonly_or_overflow(start, values, regs):
    from custom_components.thessla_green_modbus.core.write_path import validate_holding_write_span

    with pytest.raises(ValueError):
        validate_holding_write_span(start, values, regs.values())


def test_raw_atomic_blocks_allowed(regs):
    from custom_components.thessla_green_modbus.core.write_path import validate_holding_write_span

    validate_holding_write_span(4400, [2, 30, 1], regs.values())
    validate_holding_write_span(4403, [2, 44, 1], regs.values())
    validate_holding_write_span(0, [0x2610, 0x2102, 0x1230, 0], regs.values())


@pytest.mark.asyncio
async def test_partial_aatt_reads_current_temperature_under_write_lock(monkeypatch):
    import custom_components.thessla_green_modbus.coordinator.schedule as schedule

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(), host="localhost", port=502, slave_id=10, name="test"
    )
    coordinator.data = {"setting_summer_mon_1": {"airflow_pct": 50, "temp_c": 18.0}}
    coordinator._ensure_connection = AsyncMock()
    coordinator._assert_write_connection_ready = MagicMock()
    captured = []

    async def read_current(address, count):
        assert coordinator.device_client._write_lock.locked()
        assert address == 72 and count == 1
        return [0x142C]  # device has 22 C, unlike the stale coordinator snapshot

    async def write(c, definition, plan, refresh):
        assert c.device_client._write_lock.locked()
        captured.append(plan.scalar_value)
        return True, False

    coordinator._locked_read_holding_registers = read_current
    monkeypatch.setattr(schedule, "run_single_write_attempts", write)
    assert await coordinator.async_write_register("setting_summer_mon_1", 30, refresh=False)
    assert captured == [0x1E2C]


@pytest.mark.asyncio
async def test_partial_aatt_failed_read_never_writes(monkeypatch):
    import custom_components.thessla_green_modbus.coordinator.schedule as schedule

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(), host="localhost", port=502, slave_id=10, name="test"
    )
    coordinator._ensure_connection = AsyncMock()
    coordinator._assert_write_connection_ready = MagicMock()
    coordinator._locked_read_holding_registers = AsyncMock(return_value=None)
    write = AsyncMock(return_value=(True, False))
    monkeypatch.setattr(schedule, "run_single_write_attempts", write)
    assert not await coordinator.async_write_register("setting_summer_mon_1", 30, refresh=False)
    write.assert_not_awaited()


@pytest.mark.parametrize(
    "name,value",
    [
        ("schedule_summer_mon_1", 0xA200),
        ("manual_airing_time_to_start", 0x2400),
        ("airing_winter_mon", 0x2400),
    ],
)
def test_disabled_time_is_supported_during_discovery(name, value):
    from custom_components.thessla_green_modbus.scanner.capabilities import is_valid_register_value

    assert is_valid_register_value(SimpleNamespace(_register_ranges={}), name, value)


@pytest.mark.parametrize("name", ["f_142", "f_143", "f_146", "f_147"])
def test_filter_faults_included_in_aggregate(name):
    from custom_components.thessla_green_modbus.sensor import (
        _format_error_status_code,
        _is_error_or_status_register,
    )

    assert _is_error_or_status_register(name)
    assert _format_error_status_code(name) == name.replace("_", "").upper()


@pytest.mark.asyncio
async def test_airing_service_disable_is_not_midnight(regs):
    from custom_components.thessla_green_modbus.services.handlers_airing import (
        register_airing_service,
    )

    handlers = {}
    hass = SimpleNamespace(
        services=SimpleNamespace(async_register=lambda d, n, h, s: handlers.update({n: h}))
    )
    coord = SimpleNamespace(
        device_client=SimpleNamespace(available_registers={"holding_registers": set(regs)}),
        async_request_refresh=AsyncMock(),
    )
    writes = []

    async def write(c, name, value, *args):
        writes.append((name, regs[name].encode(value)))
        return True

    deps = SimpleNamespace(
        domain="test",
        normalize_option=lambda v: v,
        day_to_device_key={"monday": "mon"},
        iter_target_coordinators=AsyncMock(return_value=[("climate.test", coord)]),
        write_register=write,
    )
    register_airing_service(hass, deps)
    await handlers["set_airing_schedule"](
        SimpleNamespace(data={"schedule": "manual", "enabled": False})
    )
    await handlers["set_airing_schedule"](
        SimpleNamespace(data={"schedule": "winter", "day": "monday", "start_time": time(0, 0)})
    )
    assert writes == [("manual_airing_time_to_start", 0x2400), ("airing_winter_mon", 0)]
    with pytest.raises(ServiceValidationError):
        await handlers["set_airing_schedule"](
            SimpleNamespace(data={"schedule": "manual", "enabled": True})
        )
    assert len(writes) == 2


@pytest.mark.parametrize("raw", [[], [0x142C, 0x142C]])
@pytest.mark.asyncio
async def test_partial_aatt_short_or_excess_read_never_writes(raw, monkeypatch):
    """A truncated/malformed reply is not a usable temperature observation."""
    import custom_components.thessla_green_modbus.coordinator.schedule as schedule

    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(), host="localhost", port=502, slave_id=10, name="test"
    )
    coord._ensure_connection = AsyncMock()
    coord._assert_write_connection_ready = MagicMock()
    coord._locked_read_holding_registers = AsyncMock(return_value=raw)
    write = AsyncMock(return_value=(True, False))
    monkeypatch.setattr(schedule, "run_single_write_attempts", write)
    assert not await coord.async_write_register("setting_summer_mon_1", 30, refresh=False)
    write.assert_not_awaited()


@pytest.mark.parametrize("command", [17, 33])
@pytest.mark.asyncio
async def test_airpack4_filter_command_reaches_transport_unchanged(command, monkeypatch):
    """Profile validation and the real register encoder accept AP4 command bytes."""
    import custom_components.thessla_green_modbus.coordinator.schedule as schedule

    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(),
        host="localhost",
        port=502,
        slave_id=10,
        name="test",
        entry=MagicMock(options={"device_family": "airpack4"}, data={}, entry_id="test"),
    )
    coord._ensure_connection = AsyncMock()
    coord._assert_write_connection_ready = MagicMock()
    plans = []

    async def write(coordinator, definition, plan, refresh):
        plans.append((plan.address, plan.scalar_value))
        return True, False

    monkeypatch.setattr(schedule, "run_single_write_attempts", write)
    assert await coord.async_write_register("filter_change", command, refresh=False)
    assert plans == [(8191, command)]


@pytest.mark.parametrize(
    "family,value", [("airpack_home", 17), ("airpack4", 4), ("unspecified", 1)]
)
@pytest.mark.asyncio
async def test_wrong_family_filter_write_never_opens_transport(family, value):
    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(),
        host="localhost",
        port=502,
        slave_id=10,
        name="test",
        entry=MagicMock(options={"device_family": family}, data={}, entry_id="test"),
    )
    coord._ensure_connection = AsyncMock()
    with pytest.raises(ValueError, match="Filter write rejected"):
        await coord.async_write_register("filter_change", value, refresh=False)
    coord._ensure_connection.assert_not_awaited()


@pytest.mark.parametrize(
    "name,raw,expected",
    [
        ("supply_air_flow", 65535, None),
        ("exhaust_air_flow", 0, 0),
        ("rtc_cal", 238, -18),
        ("cf_version", 13, "0.13"),
        ("season_mode", 0, 0),
        ("special_mode", 7, 7),
        ("filter_change", 1, 1),
    ],
)
def test_runtime_processing_preserves_correct_contract(name, raw, expected):
    """Check the real poll decoder, not only direct RegisterDef calls."""
    from custom_components.thessla_green_modbus.core.register_processing import (
        process_register_value,
    )

    assert process_register_value(name, raw) == expected
