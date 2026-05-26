"""Regression tests for the AirPack4 FW 3.11 batch-read bug on summer schedule.

Background
----------
On firmware 3.11 the device occasionally returns either:
  * a Modbus exception on FC03 batches that span addresses 0x10–0x2B
    (summer schedule), or
  * a partial/empty response with fewer registers than requested.

When that happens, the previous behaviour was to mark the entire chunk (or
its tail) as failed, which caused the next coordinator poll to skip the
chunk entirely. After a write to one of those registers, the UI would
revert to the stale value because no fresh read ever arrived.

These tests pin the recovery contract:
  * empty batch  -> full fallback to individual reads,
  * raises       -> full fallback to individual reads,
  * partial head -> tail-only fallback to individual reads.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)
from pymodbus.exceptions import ModbusIOException

# Use the real register names from registers/thessla_green_registers_full.json
# at addresses 0x10..0x13 (Monday slots 1..4). This guards against accidental
# renames in the register JSON.
SUMMER_NAMES = [
    "schedule_summer_mon_1",
    "schedule_summer_mon_2",
    "schedule_summer_mon_3",
    "schedule_summer_mon_4",
]
SUMMER_BASE_ADDR = 0x10  # 16

# All 28 summer + 28 winter + 14 airing time registers
_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_SLOTS = ["1", "2", "3", "4"]
ALL_SUMMER_NAMES = [f"schedule_summer_{d}_{s}" for d in _DAYS for s in _SLOTS]
ALL_WINTER_NAMES = [f"schedule_winter_{d}_{s}" for d in _DAYS for s in _SLOTS]
AIRING_NAMES = [f"airing_summer_{d}" for d in _DAYS] + [f"airing_winter_{d}" for d in _DAYS]


@pytest.fixture
def coordinator() -> ThesslaGreenModbusCoordinator:
    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(),
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=5,
        retry=1,
    )
    coord.device_client.available_registers = {
        "holding_registers": set(SUMMER_NAMES),
        "input_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    coord.device_client._register_groups = {
        "holding_registers": [(SUMMER_BASE_ADDR, len(SUMMER_NAMES))]
    }
    coord.device_client._failed_registers = set()
    coord.device_client.effective_batch = 20

    addr_to_name = {SUMMER_BASE_ADDR + i: name for i, name in enumerate(SUMMER_NAMES)}
    dc = coord.device_client
    dc._find_register_name = lambda rt, addr: addr_to_name.get(addr)
    dc._process_register_value = lambda _name, value: value
    dc._clear_register_failure = MagicMock()
    dc._mark_registers_failed = MagicMock(
        side_effect=lambda regs: coord.device_client._failed_registers.update(r for r in regs if r)
    )
    return coord


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_mode", ["raises", "empty"])
async def test_schedule_summer_batch_bug_falls_back_to_individual_reads(
    coordinator: ThesslaGreenModbusCoordinator,
    batch_mode: str,
) -> None:
    coordinator.device_client._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    coordinator.device_client.client = None

    single_values = {
        SUMMER_BASE_ADDR + 0: 101,
        SUMMER_BASE_ADDR + 1: 202,
        SUMMER_BASE_ADDR + 2: 303,
        SUMMER_BASE_ADDR + 3: 404,
    }

    async def _fake_read_with_retry(_read_method, address, count, **_kwargs):
        if count > 1:
            if batch_mode == "raises":
                raise ModbusIOException("corrupt")
            return SimpleNamespace(registers=[])
        return SimpleNamespace(registers=[single_values[address]])

    dc = coordinator.device_client
    dc._read_with_retry = AsyncMock(side_effect=_fake_read_with_retry)
    original_fallback = dc._read_holding_individually
    dc._read_holding_individually = AsyncMock(wraps=original_fallback)

    data = await dc._read_holding_registers_optimized()

    dc._read_holding_individually.assert_awaited_once()

    single_calls = [call for call in dc._read_with_retry.await_args_list if call.args[2] == 1]
    assert [call.args[1] for call in single_calls] == [SUMMER_BASE_ADDR + i for i in range(4)]

    assert data == dict(zip(SUMMER_NAMES, [101, 202, 303, 404], strict=True))
    assert not any(
        name.startswith("schedule_summer_") for name in coordinator.device_client._failed_registers
    )


@pytest.mark.asyncio
async def test_schedule_summer_partial_batch_falls_back_for_tail_only(
    coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    """FW 3.11 returns 2 of 4 registers — tail must NOT be marked failed."""
    coordinator.device_client._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    coordinator.device_client.client = None

    tail_singles = {SUMMER_BASE_ADDR + 2: 303, SUMMER_BASE_ADDR + 3: 404}

    async def _fake_read_with_retry(_read_method, address, count, **_kwargs):
        if count > 1:
            return SimpleNamespace(registers=[101, 202])
        return SimpleNamespace(registers=[tail_singles[address]])

    dc = coordinator.device_client
    dc._read_with_retry = AsyncMock(side_effect=_fake_read_with_retry)
    original_fallback = dc._read_holding_individually
    dc._read_holding_individually = AsyncMock(wraps=original_fallback)

    data = await dc._read_holding_registers_optimized()

    dc._read_holding_individually.assert_awaited_once()
    fallback_call = dc._read_holding_individually.await_args
    assert fallback_call.args[1] == SUMMER_BASE_ADDR + 2  # tail_start
    assert len(fallback_call.args[2]) == 2  # tail_names

    assert data == dict(zip(SUMMER_NAMES, [101, 202, 303, 404], strict=True))
    assert not coordinator.device_client._failed_registers


def test_summer_schedule_register_names_exist_in_registry() -> None:
    """Guard against silent rename of summer schedule registers in JSON."""
    from custom_components.thessla_green_modbus.registers.loader import (
        get_register_definition,
    )

    for name in SUMMER_NAMES:
        definition = get_register_definition(name)
        assert definition is not None, f"Register {name!r} missing from registry JSON"
        assert definition.function == 3, f"{name} must be FC03 (holding register)"


def test_all_schedule_and_airing_register_names_exist_in_registry() -> None:
    """Guard against silent renames of all 28 summer + 28 winter + 14 airing registers."""
    from custom_components.thessla_green_modbus.registers.loader import (
        get_register_definition,
    )

    for name in ALL_SUMMER_NAMES + ALL_WINTER_NAMES + AIRING_NAMES:
        definition = get_register_definition(name)
        assert definition is not None, f"Register {name!r} missing from registry"
        assert definition.function == 3, f"{name} must be FC03 (holding register)"


def test_entity_mappings_time_contains_all_schedule_entries() -> None:
    """ENTITY_MAPPINGS['time'] must include all 28 summer + 28 winter + 14 airing entries."""
    from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS

    time_keys = set(ENTITY_MAPPINGS["time"].keys())
    for name in ALL_SUMMER_NAMES:
        assert name in time_keys, f"Missing summer schedule time entity: {name!r}"
    for name in ALL_WINTER_NAMES:
        assert name in time_keys, f"Missing winter schedule time entity: {name!r}"
    for name in AIRING_NAMES:
        assert name in time_keys, f"Missing airing time entity: {name!r}"
