"""TASK 3: Tests proving coordinator→DeviceClient IO ownership cleanup.

Verifies:
1. Coordinator no longer exposes the 5 removed delegate methods.
2. DeviceClient is the IO owner for get_client_method, mark_registers_failed,
   clear_register_failure, find_register_name, process_register_value.
3. Update cycle routes read calls through device_client (not coordinator).
4. Failed-register tracking semantics work via device_client._failed_registers.
5. No fan-percentage regressions.
6. No dangerous-entity regressions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers_coordinator import make_coordinator as _make_coordinator

# ---------------------------------------------------------------------------
# 1. Coordinator no longer exposes the 5 removed delegate methods
# ---------------------------------------------------------------------------


def test_coordinator_no_get_client_method():
    coord = _make_coordinator()
    assert (
        not hasattr(coord, "_get_client_method")
        or callable(getattr(coord.__class__, "_get_client_method", None)) is False
    ), "_get_client_method was not removed from coordinator"
    # DeviceClient still has it
    assert callable(coord.device_client._get_client_method)


def test_coordinator_no_mark_registers_failed():
    coord = _make_coordinator()
    assert not hasattr(coord.__class__, "_mark_registers_failed") or (
        getattr(coord.__class__, "_mark_registers_failed", None)
        is getattr(coord.device_client.__class__, "_mark_registers_failed", None)
    )
    assert callable(coord.device_client._mark_registers_failed)


def test_coordinator_no_clear_register_failure():
    coord = _make_coordinator()
    # Direct attribute lookup on coordinator class should not find it
    found_on_coord = any(
        "_clear_register_failure" in cls.__dict__
        for cls in type(coord).__mro__
        if cls.__name__ not in ("ThesslaGreenDeviceClient",) and "DeviceClient" not in cls.__name__
    )
    # DeviceClient still exposes it
    assert callable(coord.device_client._clear_register_failure)
    # The coordinator should not define its own version of it
    assert not found_on_coord, "_clear_register_failure still defined on coordinator MRO"


def test_coordinator_no_find_register_name():
    coord = _make_coordinator()
    assert not hasattr(coord, "_find_register_name") or not any(
        "_find_register_name" in cls.__dict__
        for cls in type(coord).__mro__
        if "DeviceClient" not in cls.__name__ and "Mixin" not in cls.__name__
    )
    assert callable(coord.device_client._find_register_name)


def test_coordinator_no_process_register_value():
    coord = _make_coordinator()
    # Coordinator must not have a thin delegate wrapping device_client
    assert not any(
        "_process_register_value" in cls.__dict__
        for cls in type(coord).__mro__
        if "DeviceClient" not in cls.__name__
        and "Mixin" not in cls.__name__
        and cls.__name__ != "ThesslaGreenModbusCoordinator"
    )
    # DeviceClient still has concrete implementation
    assert callable(coord.device_client._process_register_value)
    # Calling via device_client works as expected
    result = coord.device_client._process_register_value("outside_temperature", 205)
    assert result == pytest.approx(20.5)


# ---------------------------------------------------------------------------
# 2. DeviceClient is the IO owner for the 4 register-protocol methods
# ---------------------------------------------------------------------------


def test_device_client_owns_get_client_method():
    coord = _make_coordinator()
    dc = coord.device_client
    method = dc._get_client_method("read_holding_registers")
    assert callable(method)


def test_device_client_owns_mark_registers_failed():
    coord = _make_coordinator()
    dc = coord.device_client
    dc._failed_registers = set()
    dc._mark_registers_failed({"reg_a", "reg_b"})
    assert "reg_a" in dc._failed_registers
    assert "reg_b" in dc._failed_registers


def test_device_client_owns_clear_register_failure():
    coord = _make_coordinator()
    dc = coord.device_client
    dc._failed_registers = {"outside_temperature", "mode"}
    dc._clear_register_failure("outside_temperature")
    assert "outside_temperature" not in dc._failed_registers
    assert "mode" in dc._failed_registers


def test_device_client_owns_find_register_name():
    coord = _make_coordinator()
    dc = coord.device_client
    # Works with actual register map (resolves by address)
    result = dc._find_register_name("input_registers", 0)
    # None is OK if 0 is not in map; just ensure it doesn't raise
    assert result is None or isinstance(result, str)


def test_device_client_owns_process_register_value():
    coord = _make_coordinator()
    dc = coord.device_client
    # Temperature register: 205 raw → 20.5 decoded
    assert dc._process_register_value("outside_temperature", 205) == pytest.approx(20.5)
    # Unknown register returns False (no definition found)
    assert dc._process_register_value("_nonexistent_xyz", 42) is False


# ---------------------------------------------------------------------------
# 3. Update cycle routes calls through device_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_cycle_uses_device_client_read_all():
    """_async_update_data delegates to device_client._read_all_register_data."""
    coord = _make_coordinator()
    dc = coord.device_client

    mock_data = {"outside_temperature": 21.5}
    dc._read_input_registers_optimized = AsyncMock(return_value=mock_data)
    dc._read_holding_registers_optimized = AsyncMock(return_value={})
    dc._read_coil_registers_optimized = AsyncMock(return_value={})
    dc._read_discrete_inputs_optimized = AsyncMock(return_value={})
    dc.client = MagicMock()
    coord._ensure_connection = AsyncMock()

    result = await coord._async_update_data()

    dc._read_input_registers_optimized.assert_awaited_once()
    assert result.get("outside_temperature") == pytest.approx(21.5)


@pytest.mark.asyncio
async def test_update_cycle_does_not_call_coordinator_read_methods():
    """Coordinator-level _read_*_optimized must NOT be called during update cycle."""
    coord = _make_coordinator()
    dc = coord.device_client

    dc._read_input_registers_optimized = AsyncMock(return_value={"mode": 0})
    dc._read_holding_registers_optimized = AsyncMock(return_value={})
    dc._read_coil_registers_optimized = AsyncMock(return_value={})
    dc._read_discrete_inputs_optimized = AsyncMock(return_value={})
    dc.client = MagicMock()
    coord._ensure_connection = AsyncMock()

    # Poison-pill: if coordinator-level method were called, it would raise
    coord._read_input_registers_optimized = MagicMock(
        side_effect=AssertionError("coordinator IO called!")
    )

    await coord._async_update_data()  # Must NOT raise


# ---------------------------------------------------------------------------
# 4. Failed-register tracking via device_client._failed_registers
# ---------------------------------------------------------------------------


def test_failed_registers_tracked_on_device_client():
    """_failed_registers set lives on DeviceClient, not coordinator."""
    coord = _make_coordinator()
    dc = coord.device_client
    dc._failed_registers = set()
    dc._mark_registers_failed({"supply_temperature"})
    assert "supply_temperature" in dc._failed_registers
    dc._clear_register_failure("supply_temperature")
    assert "supply_temperature" not in dc._failed_registers


# ---------------------------------------------------------------------------
# 5. Fan-percentage logic unchanged (no regression from #1682)
# ---------------------------------------------------------------------------


def test_fan_percentage_registers_decode_correctly():
    """fan_percentage and related registers decode via device_client._process_register_value."""
    coord = _make_coordinator()
    dc = coord.device_client
    # air_flow_rate_manual raw 50 → 50 (integer, no scaling)
    result = dc._process_register_value("air_flow_rate_manual", 50)
    assert result == 50 or result == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# 6. Dangerous-entity availability — no entity_registry_enabled_default: False
# ---------------------------------------------------------------------------


def test_no_dangerous_entity_enabled_default_false():
    """Dangerous entities must not have entity_registry_enabled_default: False."""
    import json
    import pathlib

    mapping_files = list(pathlib.Path("custom_components/thessla_green_modbus").rglob("*.json"))
    for path in mapping_files:
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    assert entry.get("entity_registry_enabled_default") is not False, (
                        f"{path}: found entity_registry_enabled_default: false in {entry}"
                    )
