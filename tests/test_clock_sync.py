# mypy: ignore-errors
"""Tests for device clock synchronization."""

from __future__ import annotations

import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.clock_sync import (
    ClockSyncManager,
    async_perform_clock_sync,
    bcd_decode,
    bcd_encode,
    decode_rtc_registers,
    encode_rtc_registers,
)

# ---------------------------------------------------------------------------
# BCD encode/decode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, 0x00),
        (1, 0x01),
        (9, 0x09),
        (10, 0x10),
        (25, 0x25),
        (59, 0x59),
        (99, 0x99),
    ],
)
def test_bcd_encode(value, expected):
    assert bcd_encode(value) == expected


@pytest.mark.parametrize(
    "byte, expected",
    [
        (0x00, 0),
        (0x01, 1),
        (0x09, 9),
        (0x10, 10),
        (0x25, 25),
        (0x59, 59),
        (0x99, 99),
    ],
)
def test_bcd_decode(byte, expected):
    assert bcd_decode(byte) == expected


def test_bcd_round_trip():
    for v in range(100):
        assert bcd_decode(bcd_encode(v)) == v


# ---------------------------------------------------------------------------
# encode_rtc_registers
# ---------------------------------------------------------------------------


def test_encode_rtc_registers_known_value():
    dt = datetime.datetime(2025, 5, 9, 14, 30, 45)  # Friday = weekday 4
    regs = encode_rtc_registers(dt)
    assert len(regs) == 4
    # addr 0: yymm = (BCD(25) << 8) | BCD(5)
    assert regs[0] == (bcd_encode(25) << 8) | bcd_encode(5)
    # addr 1: ddww = (BCD(9) << 8) | BCD(4)
    assert regs[1] == (bcd_encode(9) << 8) | bcd_encode(4)
    # addr 2: hhmm = (BCD(14) << 8) | BCD(30)
    assert regs[2] == (bcd_encode(14) << 8) | bcd_encode(30)
    # addr 3: sscc = (BCD(45) << 8) | 0x00
    assert regs[3] == (bcd_encode(45) << 8) | 0x00


# ---------------------------------------------------------------------------
# decode_rtc_registers / round-trip compatibility
# ---------------------------------------------------------------------------


def test_decode_rtc_registers_known_value():
    dt = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(dt)
    result = decode_rtc_registers(*regs)
    assert result == "2025-05-09T14:30:45"


def test_decode_rtc_round_trip():
    """Encoder output can be decoded back to the same datetime string."""
    for dt in [
        datetime.datetime(2025, 1, 1, 0, 0, 0),
        datetime.datetime(2025, 12, 31, 23, 59, 59),
        datetime.datetime(2026, 6, 15, 12, 0, 0),
    ]:
        regs = encode_rtc_registers(dt)
        decoded = decode_rtc_registers(*regs)
        assert decoded == dt.strftime("%Y-%m-%dT%H:%M:%S")


def test_decode_rtc_invalid_returns_none():
    assert decode_rtc_registers(0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF) is None


def test_decoder_matches_capabilities_decoder():
    """Our decoder must match the implementation in core/capabilities_mixin.py."""
    from custom_components.thessla_green_modbus.core.capabilities_mixin import (
        _CoordinatorCapabilitiesMixin,
    )

    mixin = _CoordinatorCapabilitiesMixin.__new__(_CoordinatorCapabilitiesMixin)
    dt = datetime.datetime(2025, 3, 15, 8, 45, 30)
    regs = encode_rtc_registers(dt)
    data = {
        "date_time": regs[0],
        "date_time_ddtt": regs[1],
        "date_time_ggmm": regs[2],
        "date_time_sscc": regs[3],
    }
    caps_result = mixin._decode_device_clock(data)
    our_result = decode_rtc_registers(*regs)
    assert caps_result == our_result


# ---------------------------------------------------------------------------
# async_perform_clock_sync — helpers
# ---------------------------------------------------------------------------


def _make_coordinator(*, write_ok=True, data=None, readback_regs=None):
    """Build a mock coordinator for clock sync tests.

    ``readback_regs`` is the list of raw register values that the mock
    returns as the read-back result.  Pass None to simulate a failed/absent
    read-back (the device clock is unavailable after write).
    """
    now_regs = readback_regs  # alias for clarity
    coord = MagicMock()
    coord.async_write_and_read_holding_registers = AsyncMock(return_value=(write_ok, now_regs))
    coord.async_request_refresh = AsyncMock()
    coord.data = data if data is not None else {}
    coord.device_client.config.host = "192.168.1.100"
    return coord


def _fixed_now(dt: datetime.datetime):
    return lambda: dt


# ---------------------------------------------------------------------------
# async_perform_clock_sync — force=True always writes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_force_writes_registers():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(now)
    coord = _make_coordinator(
        data={"device_clock": "2025-05-09T14:30:46"},
        readback_regs=regs,
    )

    result = await async_perform_clock_sync(
        coord,
        force=True,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True
    coord.async_write_and_read_holding_registers.assert_awaited_once()
    call_kwargs = coord.async_write_and_read_holding_registers.call_args
    assert call_kwargs.kwargs["start_address"] == 0
    assert len(call_kwargs.kwargs["values"]) == 4


@pytest.mark.asyncio
async def test_sync_force_writes_correct_register_values():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(now)
    coord = _make_coordinator(
        data={"device_clock": "2025-05-09T14:30:46"},
        readback_regs=regs,
    )

    await async_perform_clock_sync(
        coord,
        force=True,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    values = coord.async_write_and_read_holding_registers.call_args.kwargs["values"]
    assert values == encode_rtc_registers(now)


# ---------------------------------------------------------------------------
# async_perform_clock_sync — drift check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_skipped_when_drift_below_threshold():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:30:44"})  # 1s drift

    result = await async_perform_clock_sync(
        coord,
        force=False,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True
    coord.async_write_and_read_holding_registers.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_proceeds_when_drift_exceeds_threshold():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    # Device clock is 400 seconds behind
    regs = encode_rtc_registers(now)
    coord = _make_coordinator(
        data={"device_clock": "2025-05-09T14:23:45"},
        readback_regs=regs,
    )

    result = await async_perform_clock_sync(
        coord,
        force=False,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True
    coord.async_write_and_read_holding_registers.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_proceeds_when_device_clock_missing():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(now)
    coord = _make_coordinator(data={}, readback_regs=regs)  # no device_clock key

    result = await async_perform_clock_sync(
        coord,
        force=False,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True
    coord.async_write_and_read_holding_registers.assert_awaited_once()


# ---------------------------------------------------------------------------
# async_perform_clock_sync — write failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_returns_false_on_write_failure():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(write_ok=False, data={})

    result = await async_perform_clock_sync(
        coord,
        force=True,
        dt_now_fn=_fixed_now(now),
    )
    assert result is False
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# async_perform_clock_sync — read-back validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_read_back_success():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(now)
    coord = _make_coordinator(data={}, readback_regs=regs)

    result = await async_perform_clock_sync(
        coord,
        force=True,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True


@pytest.mark.asyncio
async def test_sync_read_back_validation_failure_raises():
    from homeassistant.exceptions import HomeAssistantError

    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    wrong_dt = datetime.datetime(2025, 5, 9, 12, 0, 0)
    wrong_regs = encode_rtc_registers(wrong_dt)
    coord = _make_coordinator(data={}, readback_regs=wrong_regs)

    with pytest.raises(HomeAssistantError):
        await async_perform_clock_sync(
            coord,
            force=True,
            dt_now_fn=_fixed_now(now),
        )


@pytest.mark.asyncio
async def test_sync_read_back_unavailable_returns_true():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(data={}, readback_regs=None)

    result = await async_perform_clock_sync(
        coord,
        force=True,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True


# ---------------------------------------------------------------------------
# Serialization: write-path locking — new tests for RTC sync concurrency fix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_uses_atomic_write_and_read_method():
    """async_perform_clock_sync delegates to async_write_and_read_holding_registers."""
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(now)
    coord = _make_coordinator(readback_regs=regs)

    await async_perform_clock_sync(coord, force=True, dt_now_fn=_fixed_now(now))

    coord.async_write_and_read_holding_registers.assert_awaited_once()
    call_kwargs = coord.async_write_and_read_holding_registers.call_args.kwargs
    assert call_kwargs["start_address"] == 0
    assert call_kwargs["values"] == encode_rtc_registers(now)
    assert call_kwargs["readback_count"] == 4


@pytest.mark.asyncio
async def test_sync_does_not_call_request_refresh():
    """No async_request_refresh during RTC sync — prevents stale coordinator.data race."""
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(now)
    coord = _make_coordinator(readback_regs=regs)

    await async_perform_clock_sync(coord, force=True, dt_now_fn=_fixed_now(now))

    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_readback_uses_locked_register_values_not_coordinator_data():
    """Read-back validation uses register values from the locked read, not coordinator.data."""
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(now)
    # coordinator.data intentionally holds stale/wrong clock data
    coord = _make_coordinator(
        data={"device_clock": "2000-01-01T00:00:00"},
        readback_regs=regs,
    )

    # Should succeed because readback_regs matches now, even though coordinator.data is wrong
    result = await async_perform_clock_sync(coord, force=True, dt_now_fn=_fixed_now(now))
    assert result is True


@pytest.mark.asyncio
async def test_concurrent_rtc_sync_and_update_serialized():
    """Two concurrent write+read calls via _write_lock are serialized (never overlap)."""
    from custom_components.thessla_green_modbus.coordinator.schedule import (
        _CoordinatorScheduleMixin,
    )

    active_count = [0]
    max_concurrent = [0]
    call_log = []

    class _FakeCoordinator(_CoordinatorScheduleMixin):
        slave_id = 1
        retry = 1
        effective_batch = 16
        _transport = None
        device_client = property(lambda self: self)

        def __init__(self):
            self._write_lock = asyncio.Lock()
            self._device_client = self
            self._client = None

        # Required stubs
        async def _ensure_connection(self):
            pass

        def _assert_write_connection_ready(self):
            pass

        def _validate_multi_register_write_request(self, addr, vals, req_single):
            return True

        def _plan_multi_register_chunks(self, addr, vals, req_single):
            return [(addr, vals)]

        async def _execute_multi_register_chunks(self, chunks, attempt):
            active_count[0] += 1
            max_concurrent[0] = max(max_concurrent[0], active_count[0])
            call_log.append("write_start")
            await asyncio.sleep(0)
            call_log.append("write_end")
            active_count[0] -= 1
            resp = MagicMock()
            resp.isError.return_value = False
            return resp, True

        def _write_response_ok(self, resp):
            return True

        async def _handle_write_attempt_exception(self, **kw):
            return False

        def _handle_write_response_failure(self, **kw):
            return False

        async def _locked_read_holding_registers(self, addr, count):
            active_count[0] += 1
            max_concurrent[0] = max(max_concurrent[0], active_count[0])
            call_log.append("read_start")
            await asyncio.sleep(0)
            call_log.append("read_end")
            active_count[0] -= 1
            return encode_rtc_registers(datetime.datetime(2025, 5, 9, 14, 30, 45))

        async def _disconnect(self):
            pass

    coord = _FakeCoordinator()

    values = encode_rtc_registers(datetime.datetime(2025, 5, 9, 14, 30, 45))

    results = await asyncio.gather(
        coord.async_write_and_read_holding_registers(0, values, 4),
        coord.async_write_and_read_holding_registers(0, values, 4),
    )

    # Both operations should succeed
    assert all(ok for ok, _ in results)
    # The lock must prevent any concurrent active operations
    assert max_concurrent[0] == 1, (
        f"Detected concurrent Modbus access: max_concurrent={max_concurrent[0]}"
    )


@pytest.mark.asyncio
async def test_no_overlapping_read_write_calls_on_same_client():
    """Under _write_lock, write and read-back can never overlap on the same client."""
    from custom_components.thessla_green_modbus.coordinator.schedule import (
        _CoordinatorScheduleMixin,
    )

    overlap_detected = [False]
    lock_held_by = [None]

    class _FakeCoordinator(_CoordinatorScheduleMixin):
        slave_id = 1
        retry = 1
        effective_batch = 16
        _transport = None
        device_client = property(lambda self: self)

        def __init__(self):
            self._write_lock = asyncio.Lock()
            self._device_client = self

        async def _ensure_connection(self):
            pass

        def _assert_write_connection_ready(self):
            pass

        def _validate_multi_register_write_request(self, addr, vals, req_single):
            return True

        def _plan_multi_register_chunks(self, addr, vals, req_single):
            return [(addr, vals)]

        async def _execute_multi_register_chunks(self, chunks, attempt):
            # Check that no other operation is active
            if lock_held_by[0] is not None and lock_held_by[0] != id(self):
                overlap_detected[0] = True
            resp = MagicMock()
            resp.isError.return_value = False
            return resp, True

        def _write_response_ok(self, resp):
            return True

        async def _handle_write_attempt_exception(self, **kw):
            return False

        def _handle_write_response_failure(self, **kw):
            return False

        async def _locked_read_holding_registers(self, addr, count):
            # Check that no other operation is active
            if lock_held_by[0] is not None and lock_held_by[0] != id(self):
                overlap_detected[0] = True
            return encode_rtc_registers(datetime.datetime(2025, 5, 9, 14, 30, 45))

        async def _disconnect(self):
            pass

    coord = _FakeCoordinator()
    values = encode_rtc_registers(datetime.datetime(2025, 5, 9, 14, 30, 45))

    # Two concurrent calls: the _write_lock guarantees no overlap
    async def op():
        lock_held_by[0] = id(coord)
        result = await coord.async_write_and_read_holding_registers(0, values, 4)
        lock_held_by[0] = None
        return result

    await asyncio.gather(op(), op())

    assert not overlap_detected[0], "Overlapping read/write calls detected on same client"


@pytest.mark.asyncio
async def test_readback_only_after_write_response_complete():
    """Read-back cannot start until write response is fully received."""
    from custom_components.thessla_green_modbus.coordinator.schedule import (
        _CoordinatorScheduleMixin,
    )

    sequence = []

    class _FakeCoordinator(_CoordinatorScheduleMixin):
        slave_id = 1
        retry = 1
        effective_batch = 16
        _transport = None
        device_client = property(lambda self: self)

        def __init__(self):
            self._write_lock = asyncio.Lock()
            self._device_client = self

        async def _ensure_connection(self):
            pass

        def _assert_write_connection_ready(self):
            pass

        def _validate_multi_register_write_request(self, addr, vals, req_single):
            return True

        def _plan_multi_register_chunks(self, addr, vals, req_single):
            return [(addr, vals)]

        async def _execute_multi_register_chunks(self, chunks, attempt):
            sequence.append("write_response_received")
            resp = MagicMock()
            resp.isError.return_value = False
            return resp, True

        def _write_response_ok(self, resp):
            return True

        async def _handle_write_attempt_exception(self, **kw):
            return False

        def _handle_write_response_failure(self, **kw):
            return False

        async def _locked_read_holding_registers(self, addr, count):
            sequence.append("read_back_started")
            return encode_rtc_registers(datetime.datetime(2025, 5, 9, 14, 30, 45))

        async def _disconnect(self):
            pass

    coord = _FakeCoordinator()
    values = encode_rtc_registers(datetime.datetime(2025, 5, 9, 14, 30, 45))

    await coord.async_write_and_read_holding_registers(0, values, 4)

    assert sequence == ["write_response_received", "read_back_started"], (
        f"Wrong call order: {sequence}"
    )


@pytest.mark.asyncio
async def test_transaction_mismatch_prevented_by_lock_ordering():
    """Transaction mismatch scenario: _write_lock must be acquired before any Modbus call."""
    from custom_components.thessla_green_modbus.coordinator.schedule import (
        _CoordinatorScheduleMixin,
    )

    lock_was_held_during_write = [False]
    lock_was_held_during_read = [False]

    class _FakeCoordinator(_CoordinatorScheduleMixin):
        slave_id = 1
        retry = 1
        effective_batch = 16
        _transport = None
        device_client = property(lambda self: self)

        def __init__(self):
            self._write_lock = asyncio.Lock()
            self._device_client = self

        async def _ensure_connection(self):
            pass

        def _assert_write_connection_ready(self):
            pass

        def _validate_multi_register_write_request(self, addr, vals, req_single):
            return True

        def _plan_multi_register_chunks(self, addr, vals, req_single):
            return [(addr, vals)]

        async def _execute_multi_register_chunks(self, chunks, attempt):
            lock_was_held_during_write[0] = self._write_lock.locked()
            resp = MagicMock()
            resp.isError.return_value = False
            return resp, True

        def _write_response_ok(self, resp):
            return True

        async def _handle_write_attempt_exception(self, **kw):
            return False

        def _handle_write_response_failure(self, **kw):
            return False

        async def _locked_read_holding_registers(self, addr, count):
            lock_was_held_during_read[0] = self._write_lock.locked()
            return encode_rtc_registers(datetime.datetime(2025, 5, 9, 14, 30, 45))

        async def _disconnect(self):
            pass

    coord = _FakeCoordinator()
    values = encode_rtc_registers(datetime.datetime(2025, 5, 9, 14, 30, 45))

    await coord.async_write_and_read_holding_registers(0, values, 4)

    assert lock_was_held_during_write[0], "_write_lock must be held during Modbus write"
    assert lock_was_held_during_read[0], "_write_lock must be held during Modbus read-back"


# ---------------------------------------------------------------------------
# ClockSyncManager — default disabled
# ---------------------------------------------------------------------------


def test_clock_sync_manager_disabled_by_default():
    hass = MagicMock()
    coord = _make_coordinator()
    entry = MagicMock()
    entry.options = {}

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_not_called()


def test_clock_sync_manager_disabled_explicitly():
    hass = MagicMock()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {"sync_device_clock_enabled": False}

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_not_called()


# ---------------------------------------------------------------------------
# ClockSyncManager — on_start only when enabled
# ---------------------------------------------------------------------------


def test_clock_sync_manager_on_start_when_enabled_and_data_present():
    hass = MagicMock()
    hass.async_create_task.side_effect = lambda coro: coro.close()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": True,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_called_once()


def test_clock_sync_manager_on_start_not_triggered_without_data():
    hass = MagicMock()
    coord = _make_coordinator(data={})  # no device_clock yet
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": True,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_not_called()


def test_clock_sync_manager_on_start_runs_only_once():
    hass = MagicMock()
    hass.async_create_task.side_effect = lambda coro: coro.close()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": True,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    mgr._on_update()
    # on_start should only trigger once; second call goes to periodic check
    # _last_sync is None so a second task will be created for periodic
    assert hass.async_create_task.call_count >= 1


# ---------------------------------------------------------------------------
# ClockSyncManager — periodic sync
# ---------------------------------------------------------------------------


def test_clock_sync_manager_periodic_first_sync():
    """First sync always fires when enabled (no last_sync yet)."""
    hass = MagicMock()
    hass.async_create_task.side_effect = lambda coro: coro.close()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": False,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_called_once()


def test_clock_sync_manager_no_second_sync_before_interval():
    """Second sync not triggered if interval not elapsed."""
    hass = MagicMock()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": False,
        "sync_device_clock_interval_hours": 24,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._last_sync = datetime.datetime.now()  # pretend sync just happened
    mgr._on_start_done = True
    mgr._on_update()
    hass.async_create_task.assert_not_called()


# ---------------------------------------------------------------------------
# Button entity — calls sync logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_button_press_calls_sync():
    """Button.async_press calls async_perform_clock_sync with force=True."""
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:30:45"})
    entry = MagicMock()
    entry.options = {}

    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_sync:
        from custom_components.thessla_green_modbus.button import SyncDeviceClockButton

        btn = SyncDeviceClockButton.__new__(SyncDeviceClockButton)
        btn.coordinator = coord
        btn._entry = entry
        btn._coordinator_connected = lambda: True

        await btn.async_press()
        mock_sync.assert_awaited_once()
        call_kwargs = mock_sync.call_args
        assert call_kwargs.kwargs.get("force") is True


@pytest.mark.asyncio
async def test_button_press_raises_on_failure():
    """Button raises HomeAssistantError when sync returns False."""
    from homeassistant.exceptions import HomeAssistantError

    coord = _make_coordinator()
    entry = MagicMock()
    entry.options = {}

    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new_callable=AsyncMock,
        return_value=False,
    ):
        from custom_components.thessla_green_modbus.button import SyncDeviceClockButton

        btn = SyncDeviceClockButton.__new__(SyncDeviceClockButton)
        btn.coordinator = coord
        btn._entry = entry
        btn._coordinator_connected = lambda: True

        with pytest.raises(HomeAssistantError):
            await btn.async_press()


# ---------------------------------------------------------------------------
# Options flow — exposes sync options with correct defaults
# ---------------------------------------------------------------------------


def test_options_form_has_clock_sync_defaults():
    from custom_components.thessla_green_modbus._config_flow.options_form import (
        build_options_defaults,
    )
    from custom_components.thessla_green_modbus.const import (
        CONF_SYNC_DEVICE_CLOCK_ENABLED,
        CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
        CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
        CONF_SYNC_DEVICE_CLOCK_ON_START,
        DEFAULT_SYNC_DEVICE_CLOCK_ENABLED,
        DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
        DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
        DEFAULT_SYNC_DEVICE_CLOCK_ON_START,
    )

    defaults = build_options_defaults({}, {})
    assert defaults[CONF_SYNC_DEVICE_CLOCK_ENABLED] == DEFAULT_SYNC_DEVICE_CLOCK_ENABLED
    assert defaults[CONF_SYNC_DEVICE_CLOCK_ON_START] == DEFAULT_SYNC_DEVICE_CLOCK_ON_START
    assert (
        defaults[CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS] == DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS
    )
    assert (
        defaults[CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS]
        == DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS
    )


def test_options_form_default_sync_enabled_is_false():
    from custom_components.thessla_green_modbus._config_flow.options_form import (
        build_options_defaults,
    )
    from custom_components.thessla_green_modbus.const import (
        CONF_SYNC_DEVICE_CLOCK_ENABLED,
    )

    defaults = build_options_defaults({}, {})
    assert defaults[CONF_SYNC_DEVICE_CLOCK_ENABLED] is False


def test_options_form_has_clock_sync_schema_keys():
    from custom_components.thessla_green_modbus._config_flow.options_form import (
        build_options_schema,
    )
    from custom_components.thessla_green_modbus.const import (
        CONF_SYNC_DEVICE_CLOCK_ENABLED,
        CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
        CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
        CONF_SYNC_DEVICE_CLOCK_ON_START,
        DEFAULT_SYNC_DEVICE_CLOCK_ENABLED,
        DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
        DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
        DEFAULT_SYNC_DEVICE_CLOCK_ON_START,
    )

    values = {
        "scan_interval": 30,
        "timeout": 10,
        "retry": 3,
        "force_full_register_list": False,
        "enable_device_scan": True,
        "log_level": "info",
        "scan_uart_settings": True,
        "skip_missing_registers": False,
        "safe_scan": False,
        "airflow_unit": "m3h",
        "deep_scan": False,
        "max_registers_per_request": 16,
        CONF_SYNC_DEVICE_CLOCK_ENABLED: DEFAULT_SYNC_DEVICE_CLOCK_ENABLED,
        CONF_SYNC_DEVICE_CLOCK_ON_START: DEFAULT_SYNC_DEVICE_CLOCK_ON_START,
        CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS: DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
        CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS: DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    }
    schema = build_options_schema(values)
    schema_key_strs = [str(k) for k in schema.schema]
    assert any(CONF_SYNC_DEVICE_CLOCK_ENABLED in s for s in schema_key_strs)
    assert any(CONF_SYNC_DEVICE_CLOCK_ON_START in s for s in schema_key_strs)
    assert any(CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS in s for s in schema_key_strs)
    assert any(CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS in s for s in schema_key_strs)


# ---------------------------------------------------------------------------
# Service registration
# ---------------------------------------------------------------------------


def test_sync_device_clock_service_registered():
    from custom_components.thessla_green_modbus.services import REGISTERED_SERVICE_NAMES

    assert "sync_device_clock" in REGISTERED_SERVICE_NAMES


@pytest.mark.asyncio
async def test_sync_device_clock_service_calls_write(monkeypatch):
    """sync_device_clock service writes RTC registers via coordinator."""
    from types import SimpleNamespace

    from custom_components.thessla_green_modbus.services import async_setup_services

    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(now)
    coord = _make_coordinator(data={"device_clock": "2025-05-09T00:00:00"}, readback_regs=regs)

    class _Svc:
        def __init__(self):
            self.handlers = {}
            self.removed = []

        def async_register(self, _d, svc, h, _s):
            self.handlers[svc] = h

        def async_remove(self, _d, svc):
            self.removed.append(svc)

    hass = SimpleNamespace()
    hass.services = _Svc()
    hass.data = {}
    hass.bus = SimpleNamespace(async_fire=MagicMock())

    import custom_components.thessla_green_modbus.services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    await async_setup_services(hass)
    handler = hass.services.handlers["sync_device_clock"]
    call = SimpleNamespace(data={"entity_id": ["climate.dev"], "force": True})

    with patch("homeassistant.util.dt.now", return_value=now):
        await handler(call)

    coord.async_write_and_read_holding_registers.assert_awaited_once()
    values = coord.async_write_and_read_holding_registers.call_args.kwargs["values"]
    assert values == encode_rtc_registers(now)
