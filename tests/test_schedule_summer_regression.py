from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException


@pytest.fixture
def coordinator() -> ThesslaGreenModbusCoordinator:
    coord = ThesslaGreenModbusCoordinator(
        hass=MagicMock(),
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=5,
        retry=1,
    )
    names = [f"schedule_summer_{i}" for i in range(1, 5)]
    coord.available_registers = {
        "holding_registers": set(names),
        "input_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    coord._register_groups = {"holding_registers": [(15, len(names))]}
    coord._failed_registers = set()
    coord.effective_batch = 20

    addr_to_name = {15 + i: name for i, name in enumerate(names)}
    coord._find_register_name = lambda rt, addr: addr_to_name.get(addr)
    coord._process_register_value = lambda _name, value: value
    coord._clear_register_failure = MagicMock()
    coord._mark_registers_failed = MagicMock(side_effect=lambda regs: coord._failed_registers.update(r for r in regs if r))
    return coord


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_mode", ["raises", "empty"])
async def test_schedule_summer_batch_bug_falls_back_to_individual_reads(
    coordinator: ThesslaGreenModbusCoordinator,
    batch_mode: str,
) -> None:
    coordinator._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    coordinator.client = None

    single_values = {15: 101, 16: 202, 17: 303, 18: 404}

    async def _fake_read_with_retry(_read_method, address, count, **_kwargs):
        if count > 1:
            if batch_mode == "raises":
                raise ModbusIOException("corrupt")
            return SimpleNamespace(registers=[])
        return SimpleNamespace(registers=[single_values[address]])

    coordinator._read_with_retry = AsyncMock(side_effect=_fake_read_with_retry)
    original_fallback = coordinator._read_holding_individually
    coordinator._read_holding_individually = AsyncMock(wraps=original_fallback)

    data = await coordinator._read_holding_registers_optimized()

    coordinator._read_holding_individually.assert_awaited_once()

    single_calls = [
        call
        for call in coordinator._read_with_retry.await_args_list
        if call.args[2] == 1
    ]
    assert [call.args[1] for call in single_calls] == [15, 16, 17, 18]

    assert data == {
        "schedule_summer_1": 101,
        "schedule_summer_2": 202,
        "schedule_summer_3": 303,
        "schedule_summer_4": 404,
    }
    assert not any(name.startswith("schedule_summer_") for name in coordinator._failed_registers)
