"""Regression tests for available_registers fallback and time entity creation.

Scenario verified (Phase 2):
- Batch read for holding registers 16-43 (summer schedule) fails.
- Individual fallback reads succeed for at least some schedule_summer_* registers.
- Successful registers are added to available_registers["holding_registers"].
- Corresponding time entities are created via async_setup_entry.

Also verifies:
- Failed summer schedule does not block winter schedule discovery.
- Full register list mode creates both summer and winter schedule time entities.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.scanner.registers import scan_register_batch

# Four Monday summer schedule registers at addresses 16-19 (0x10-0x13)
_SUMMER_MON_ADDR_TO_NAMES: dict[int, set[str]] = {
    16: {"schedule_summer_mon_1"},
    17: {"schedule_summer_mon_2"},
    18: {"schedule_summer_mon_3"},
    19: {"schedule_summer_mon_4"},
}
_SUMMER_MON_ADDRS = [16, 17, 18, 19]

# Four Monday winter schedule registers at addresses 44-47 (0x2C-0x2F)
_WINTER_MON_ADDR_TO_NAMES: dict[int, set[str]] = {
    44: {"schedule_winter_mon_1"},
    45: {"schedule_winter_mon_2"},
    46: {"schedule_winter_mon_3"},
    47: {"schedule_winter_mon_4"},
}
_WINTER_MON_ADDRS = [44, 45, 46, 47]

# Minimal time mapping used by entity-creation tests
_TIME_MAP: dict[str, dict] = {
    "schedule_summer_mon_1": {
        "translation_key": "schedule_summer_mon_1",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
    },
    "schedule_winter_mon_1": {
        "translation_key": "schedule_winter_mon_1",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
    },
}
_REGISTER_MAP = {"schedule_summer_mon_1": 16, "schedule_winter_mon_1": 44}


def _make_scanner_stub() -> MagicMock:
    """Create a minimal scanner stub compatible with scan_register_batch."""
    scanner = MagicMock()
    scanner.available_registers = {
        "holding_registers": set(),
        "input_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    scanner.failed_addresses = {
        "modbus_exceptions": {
            "holding_registers": set(),
            "input_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
        "invalid_values": {
            "holding_registers": set(),
            "input_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
    }
    scanner._transport = None
    scanner._is_valid_register_value = MagicMock(return_value=True)
    scanner._log_invalid_value = MagicMock()
    scanner._group_registers_for_batch_read = MagicMock()
    return scanner


@pytest.mark.asyncio
async def test_summer_batch_fail_individual_success_populates_available_registers() -> None:
    """Batch read 16-19 fails; individual fallback reads succeed → all four names in available_registers."""
    scanner = _make_scanner_stub()
    scanner._group_registers_for_batch_read.return_value = [(16, 4)]

    async def _read(start: int, count: int, *, skip_cache: bool = False):
        if count > 1:
            return None  # batch fails
        return [0x0800]  # individual succeeds with valid BCD time 08:00

    await scan_register_batch(
        scanner, "holding_registers", _SUMMER_MON_ADDR_TO_NAMES, _SUMMER_MON_ADDRS, _read
    )

    for name in (
        "schedule_summer_mon_1",
        "schedule_summer_mon_2",
        "schedule_summer_mon_3",
        "schedule_summer_mon_4",
    ):
        assert name in scanner.available_registers["holding_registers"], (
            f"{name!r} should be in available_registers after successful individual fallback probe"
        )


@pytest.mark.asyncio
async def test_summer_batch_all_fail_does_not_add_to_available_registers() -> None:
    """When batch and individual reads both fail, no summer names appear in available_registers."""
    scanner = _make_scanner_stub()
    scanner._group_registers_for_batch_read.return_value = [(16, 4)]

    async def _read(start: int, count: int, *, skip_cache: bool = False):
        return None  # all reads fail

    await scan_register_batch(
        scanner, "holding_registers", _SUMMER_MON_ADDR_TO_NAMES, _SUMMER_MON_ADDRS, _read
    )

    for name in (
        "schedule_summer_mon_1",
        "schedule_summer_mon_2",
        "schedule_summer_mon_3",
        "schedule_summer_mon_4",
    ):
        assert name not in scanner.available_registers["holding_registers"], (
            f"{name!r} must not appear in available_registers when all reads fail"
        )


@pytest.mark.asyncio
async def test_winter_schedule_independent_of_failed_summer() -> None:
    """Winter batch succeeds independently even after summer batch and individual reads all fail."""
    scanner = _make_scanner_stub()

    async def _fail(start: int, count: int, *, skip_cache: bool = False):
        return None

    async def _succeed(start: int, count: int, *, skip_cache: bool = False):
        return [0x0800] * count

    # Scan summer (everything fails — no summer names in available_registers)
    scanner._group_registers_for_batch_read.return_value = [(16, 4)]
    await scan_register_batch(
        scanner, "holding_registers", _SUMMER_MON_ADDR_TO_NAMES, _SUMMER_MON_ADDRS, _fail
    )

    # Scan winter (succeeds — all winter names enter available_registers)
    scanner._group_registers_for_batch_read.return_value = [(44, 4)]
    await scan_register_batch(
        scanner, "holding_registers", _WINTER_MON_ADDR_TO_NAMES, _WINTER_MON_ADDRS, _succeed
    )

    for name in (
        "schedule_summer_mon_1",
        "schedule_summer_mon_2",
        "schedule_summer_mon_3",
        "schedule_summer_mon_4",
    ):
        assert name not in scanner.available_registers["holding_registers"], (
            f"Failed summer batch must not leave {name!r} in available_registers"
        )

    for name in (
        "schedule_winter_mon_1",
        "schedule_winter_mon_2",
        "schedule_winter_mon_3",
        "schedule_winter_mon_4",
    ):
        assert name in scanner.available_registers["holding_registers"], (
            f"{name!r} should be in available_registers after successful winter batch"
        )


@pytest.mark.asyncio
async def test_force_full_register_list_creates_schedule_time_entities() -> None:
    """force_full_register_list creates time entities even when available_registers is empty."""
    from custom_components.thessla_green_modbus.time import async_setup_entry

    coordinator = MagicMock()
    coordinator.device_client.available_registers = {"holding_registers": set()}
    coordinator.device_client.force_full_register_list = True
    coordinator.device_client.capabilities = MagicMock()
    coordinator.get_register_map.return_value = _REGISTER_MAP
    coordinator.device_client.get_register_map.return_value = _REGISTER_MAP

    config_entry = MagicMock()
    config_entry.runtime_data = coordinator

    entities_added: list = []

    with patch(
        "custom_components.thessla_green_modbus.time.ENTITY_MAPPINGS",
        {"time": _TIME_MAP},
    ):
        await async_setup_entry(
            MagicMock(), config_entry, lambda e, u=True: entities_added.extend(e)
        )

    names = {e._register_name for e in entities_added}
    assert "schedule_summer_mon_1" in names, (
        "force_full_register_list must create summer schedule time entity"
    )
    assert "schedule_winter_mon_1" in names, (
        "force_full_register_list must create winter schedule time entity"
    )


@pytest.mark.asyncio
async def test_available_registers_creates_schedule_time_entities() -> None:
    """Time entities are created for register names present in available_registers."""
    from custom_components.thessla_green_modbus.time import async_setup_entry

    coordinator = MagicMock()
    coordinator.device_client.available_registers = {
        "holding_registers": {"schedule_summer_mon_1", "schedule_winter_mon_1"}
    }
    coordinator.device_client.force_full_register_list = False
    coordinator.device_client.capabilities = MagicMock()
    coordinator.get_register_map.return_value = _REGISTER_MAP
    coordinator.device_client.get_register_map.return_value = _REGISTER_MAP

    config_entry = MagicMock()
    config_entry.runtime_data = coordinator

    entities_added: list = []

    with patch(
        "custom_components.thessla_green_modbus.time.ENTITY_MAPPINGS",
        {"time": _TIME_MAP},
    ):
        await async_setup_entry(
            MagicMock(), config_entry, lambda e, u=True: entities_added.extend(e)
        )

    names = {e._register_name for e in entities_added}
    assert "schedule_summer_mon_1" in names, (
        "schedule_summer_mon_1 in available_registers must create a time entity"
    )
    assert "schedule_winter_mon_1" in names, (
        "schedule_winter_mon_1 in available_registers must create a time entity"
    )
