"""Tests for targeted read-back after successful single-register writes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.coordinator.schedule import (
    _NO_READBACK_REGISTERS,
    _targeted_readback_safe,
)
from custom_components.thessla_green_modbus.registers.loader import RegisterDef

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_coordinator() -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=10,
        retry=3,
    )
    coord.device_client.available_registers = {
        "holding_registers": {
            "mode",
            "air_flow_rate_manual",
            "special_mode",
            "comfort_temperature",
        },
        "input_registers": {"supply_temperature"},
        "coil_registers": {"system_on_off"},
        "discrete_inputs": set(),
    }
    return coord


def _write_response(error: bool = False) -> MagicMock:
    resp = MagicMock()
    resp.isError.return_value = error
    return resp


def _read_response(registers: list[int]) -> MagicMock:
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = registers
    return resp


@pytest.fixture
def coordinator() -> ThesslaGreenModbusCoordinator:
    return _make_coordinator()


# ---------------------------------------------------------------------------
# _targeted_readback_safe unit tests
# ---------------------------------------------------------------------------


def _reg(function: int = 3, length: int = 1, name: str = "test_reg") -> RegisterDef:
    return RegisterDef(function=function, address=100, name=name, access="rw", length=length)


def test_targeted_readback_safe_holding_single() -> None:
    """Normal holding single register is eligible for targeted read-back."""
    assert _targeted_readback_safe("mode", _reg(function=3, length=1, name="mode")) is True


def test_targeted_readback_safe_coil_excluded() -> None:
    """Coil registers (function=1) are never eligible for read-back in v1."""
    assert _targeted_readback_safe("system_on_off", _reg(function=1, name="system_on_off")) is False


def test_targeted_readback_safe_multi_register_excluded() -> None:
    """Multi-word registers stay on full_refresh_only."""
    assert _targeted_readback_safe("device_name", _reg(length=8, name="device_name")) is False


def test_targeted_readback_safe_no_readback_register() -> None:
    """Registers in _NO_READBACK_REGISTERS are excluded."""
    for name in _NO_READBACK_REGISTERS:
        assert _targeted_readback_safe(name, _reg(name=name)) is False, name


def test_targeted_readback_safe_schedule_excluded() -> None:
    """schedule_ registers stay on full_refresh_only for v1."""
    reg = _reg(name="schedule_summer_mon_1")
    assert _targeted_readback_safe("schedule_summer_mon_1", reg) is False


def test_targeted_readback_safe_setting_excluded() -> None:
    """setting_ (AATT) registers stay on full_refresh_only for v1."""
    reg = _reg(name="setting_summer_mon_1")
    assert _targeted_readback_safe("setting_summer_mon_1", reg) is False


# ---------------------------------------------------------------------------
# Safe holding register: targeted read-back succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_targeted_readback_updates_coordinator_data(coordinator) -> None:
    """Write + successful read-back: coordinator.data updated, no full refresh."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()

    # Seed initial data so async_set_updated_data has something to merge into
    coordinator.data = {"mode": 0}

    result = await coordinator.async_write_register("mode", 1, refresh=True)

    assert result is True
    # Read-back succeeded → no full refresh requested
    coordinator.async_request_refresh.assert_not_called()
    # coordinator.data should be updated with the decoded read-back value
    assert "mode" in coordinator.data


@pytest.mark.asyncio
async def test_targeted_readback_fallback_when_read_fails(coordinator) -> None:
    """Write succeeds but read-back returns None → full refresh is requested."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    # Simulate read-back failure: read returns an error response
    bad_read = MagicMock()
    bad_read.isError.return_value = True
    client.read_holding_registers = AsyncMock(return_value=bad_read)
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_write_register("mode", 1, refresh=True)

    assert result is True
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_targeted_readback_uses_decoded_value_not_raw_request(coordinator) -> None:
    """coordinator.data is updated from read-back decoded value, not the requested value."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    # Device returns 2 even though we wrote 1 (firmware clamped it)
    client.read_holding_registers = AsyncMock(return_value=_read_response([2]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {"mode": 0}

    result = await coordinator.async_write_register("mode", 1, refresh=True)

    assert result is True
    coordinator.async_request_refresh.assert_not_called()
    # Value in coordinator.data must come from read-back (device returned 2), not from
    # the written value (1). The exact decoded type depends on the register definition.
    assert coordinator.data.get("mode") != 1


@pytest.mark.asyncio
async def test_write_failure_returns_false_no_readback(coordinator) -> None:
    """Failed write must return False without attempting read-back."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=True))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_write_register("mode", 1, refresh=True)

    assert result is False
    client.read_holding_registers.assert_not_called()
    coordinator.async_request_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# Unsafe registers stay on full_refresh_only / no_readback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hard_reset_settings_no_targeted_readback(coordinator, monkeypatch) -> None:
    """hard_reset_settings must not use targeted read-back."""
    import custom_components.thessla_green_modbus.coordinator.coordinator as coord_mod

    reset_def = RegisterDef(function=3, address=999, name="hard_reset_settings", access="rw")
    monkeypatch.setattr(coord_mod, "get_register_definition", lambda _n: reset_def)

    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_write_register("hard_reset_settings", 1, refresh=True)

    assert result is True
    # hard_reset_settings is in _NO_READBACK_REGISTERS → no targeted read-back
    client.read_holding_registers.assert_not_called()
    # Falls back to full refresh (refresh=True)
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_hard_reset_schedule_no_targeted_readback(coordinator, monkeypatch) -> None:
    """hard_reset_schedule must not use targeted read-back."""
    import custom_components.thessla_green_modbus.coordinator.coordinator as coord_mod

    reset_def = RegisterDef(function=3, address=998, name="hard_reset_schedule", access="rw")
    monkeypatch.setattr(coord_mod, "get_register_definition", lambda _n: reset_def)

    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_write_register("hard_reset_schedule", 1, refresh=True)

    assert result is True
    client.read_holding_registers.assert_not_called()
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_coil_register_no_targeted_readback(coordinator, monkeypatch) -> None:
    """Coil registers (function=1) stay on full_refresh_only in v1."""
    import custom_components.thessla_green_modbus.coordinator.coordinator as coord_mod

    coil_def = RegisterDef(function=1, address=0, name="system_on_off", access="rw")
    monkeypatch.setattr(coord_mod, "get_register_definition", lambda _n: coil_def)

    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_coil = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_write_register("system_on_off", True, refresh=True)

    assert result is True
    # Coil registers don't use holding-register targeted read-back
    client.read_holding_registers.assert_not_called()
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_multi_register_write_no_targeted_readback(coordinator) -> None:
    """Multi-register writes (async_write_registers) stay on full_refresh_only."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_registers = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1, 2, 3]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_write_registers(
        start_address=100, values=[1, 2, 3], refresh=True
    )

    assert result is True
    # Multi-register path has no targeted read-back; relies on full refresh
    coordinator.async_request_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# No second Modbus connection: existing write lock is re-used
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_second_connection_write_lock_held_during_readback(coordinator) -> None:
    """Read-back uses the same lock as the write; no new connection is opened."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))

    lock_held_during_readback: list[bool] = []

    async def fake_read(address: int, *, count: int, slave: int = 1, **kwargs):
        # Check that the write lock is already held when read-back fires
        lock_held_during_readback.append(coordinator.device_client._write_lock.locked())
        return _read_response([1])

    client.read_holding_registers = fake_read
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {"mode": 0}

    await coordinator.async_write_register("mode", 1, refresh=True)

    # Read-back fired at least once, and the lock was held every time
    assert lock_held_during_readback, "Read-back was not attempted"
    assert all(lock_held_during_readback), "Write lock was not held during read-back"


# ---------------------------------------------------------------------------
# targeted_readback caller-level override (hotfix for #1722 side effects)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_targeted_readback_default_true_still_reads_back(coordinator) -> None:
    """Default targeted_readback=True still performs read-back for a safe register."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {"mode": 0}

    result = await coordinator.async_write_register("mode", 1, refresh=True)

    assert result is True
    client.read_holding_registers.assert_called_once()
    coordinator.async_request_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_targeted_readback_false_skips_locked_read(coordinator) -> None:
    """targeted_readback=False must skip the holding-register read-back entirely."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {"mode": 0}

    result = await coordinator.async_write_register(
        "mode", 1, refresh=True, targeted_readback=False
    )

    assert result is True
    client.read_holding_registers.assert_not_called()


@pytest.mark.asyncio
async def test_targeted_readback_false_refresh_true_triggers_full_refresh(coordinator) -> None:
    """targeted_readback=False with refresh=True falls back to a full refresh."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_write_register(
        "mode", 1, refresh=True, targeted_readback=False
    )

    assert result is True
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_targeted_readback_false_refresh_false_no_full_refresh(coordinator) -> None:
    """targeted_readback=False with refresh=False performs no refresh at all."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_write_register(
        "mode", 1, refresh=False, targeted_readback=False
    )

    assert result is True
    coordinator.async_request_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_targeted_readback_decode_failure_does_not_fail_write(
    coordinator, monkeypatch
) -> None:
    """A decode error on read-back must not turn an already-successful write into a failure."""
    import custom_components.thessla_green_modbus.coordinator.coordinator as coord_mod

    class _BadDecodeDef:
        function = 3
        length = 1
        address = 100

        def encode(self, value):
            return int(value)

        def decode(self, raw):
            raise ValueError("boom")

    monkeypatch.setattr(coord_mod, "get_register_definition", lambda _n: _BadDecodeDef())

    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {"mode": 0}

    result = await coordinator.async_write_register("mode", 1, refresh=True)

    # Write already succeeded; decode failure must not flip the result to False.
    assert result is True
    # refresh=True + decode failure falls back to a full refresh.
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_targeted_readback_decode_failure_refresh_false_no_full_refresh(
    coordinator, monkeypatch
) -> None:
    """Decode failure with refresh=False must not force a full refresh."""
    import custom_components.thessla_green_modbus.coordinator.coordinator as coord_mod

    class _BadDecodeDef:
        function = 3
        length = 1
        address = 100

        def encode(self, value):
            return int(value)

        def decode(self, raw):
            raise ValueError("boom")

    monkeypatch.setattr(coord_mod, "get_register_definition", lambda _n: _BadDecodeDef())

    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coordinator.device_client.client = client
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {"mode": 0}

    result = await coordinator.async_write_register("mode", 1, refresh=False)

    assert result is True
    coordinator.async_request_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# Entity base class: _write_register delegates post-write policy to coordinator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entity_write_register_no_manual_refresh_on_readback_success() -> None:
    """ThesslaGreenEntity._write_register does not call async_request_refresh when
    the coordinator's targeted read-back succeeds."""
    from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity

    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coord.device_client.client = client
    coord.async_request_refresh = AsyncMock()
    coord.data = {"mode": 0}

    entity = ThesslaGreenEntity.__new__(ThesslaGreenEntity)
    entity.coordinator = coord

    await entity._write_register("mode", 1, refresh=True)

    # Coordinator handled the refresh internally via targeted read-back
    coord.async_request_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_entity_write_register_full_refresh_on_readback_failure() -> None:
    """ThesslaGreenEntity._write_register triggers full refresh when read-back fails."""
    from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity

    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    bad_read = MagicMock()
    bad_read.isError.return_value = True
    client.read_holding_registers = AsyncMock(return_value=bad_read)
    coord.device_client.client = client
    coord.async_request_refresh = AsyncMock()

    entity = ThesslaGreenEntity.__new__(ThesslaGreenEntity)
    entity.coordinator = coord

    await entity._write_register("mode", 1, refresh=True)

    coord.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_entity_write_register_no_refresh_when_refresh_false() -> None:
    """When refresh=False, entity passes refresh=False to coordinator.
    Even if read-back succeeds, no full refresh is requested."""
    from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity

    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coord.device_client.client = client
    coord.async_request_refresh = AsyncMock()
    coord.data = {"mode": 0}

    entity = ThesslaGreenEntity.__new__(ThesslaGreenEntity)
    entity.coordinator = coord

    await entity._write_register("mode", 1, refresh=False)

    coord.async_request_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# Fan: full_refresh_only preserved even for safe registers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fan_write_register_full_refresh_only() -> None:
    """Fan._write_register always requests a full refresh because fan display
    reads from supply_percentage (status register), not the written setpoint."""
    from custom_components.thessla_green_modbus.fan import ThesslaGreenFan

    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    client.read_holding_registers = AsyncMock(return_value=_read_response([1]))
    coord.device_client.client = client
    coord.async_request_refresh = AsyncMock()

    fan = ThesslaGreenFan.__new__(ThesslaGreenFan)
    fan.coordinator = coord

    await fan._write_register("air_flow_rate_manual", 60, refresh=True)

    # Fan must request a full refresh after the write, ignoring any targeted read-back
    coord.async_request_refresh.assert_called_once()
    # Fan disables targeted read-back entirely: the setpoint register isn't
    # what fan.percentage displays, so a targeted read-back would be a
    # redundant/misleading extra round-trip.
    client.read_holding_registers.assert_not_called()


@pytest.mark.asyncio
async def test_fan_write_register_no_refresh_when_refresh_false() -> None:
    """Fan._write_register with refresh=False: no refresh requested."""
    from custom_components.thessla_green_modbus.fan import ThesslaGreenFan

    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_write_response(error=False))
    coord.device_client.client = client
    coord.async_request_refresh = AsyncMock()

    fan = ThesslaGreenFan.__new__(ThesslaGreenFan)
    fan.coordinator = coord

    await fan._write_register("air_flow_rate_manual", 60, refresh=False)

    coord.async_request_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# Public contract: no entity / service / translation / unique-ID changes
# ---------------------------------------------------------------------------


def test_no_readback_registers_are_documented() -> None:
    """The exclusion set contains the required safety entries."""
    required = {
        "hard_reset_settings",
        "hard_reset_schedule",
        "filter_change",
        "airflow_rate_change_flag",
        "temperature_change_flag",
    }
    assert required.issubset(_NO_READBACK_REGISTERS), (
        f"Missing from _NO_READBACK_REGISTERS: {required - _NO_READBACK_REGISTERS}"
    )
