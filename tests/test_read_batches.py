"""Direct unit tests for core/read_batches.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.core.read_batches import (
    _fallback_individual_input_reads,
    _handle_batch_read_failure,
    _merge_batch_read_results,
    _read_input_register_batch,
    read_holding_individually,
    read_holding_registers_optimized,
    read_input_registers_optimized,
)
from custom_components.thessla_green_modbus.core.retry import _PermanentModbusError
from pymodbus.exceptions import ConnectionException, ModbusException

# ---------------------------------------------------------------------------
# Minimal owner factory
# ---------------------------------------------------------------------------


def _make_owner(
    *,
    reg_groups=None,
    transport=None,
    client=None,
    available=None,
    failed_registers=None,
):
    """Build a minimal duck-typed owner compatible with read_batches helpers."""
    dc = SimpleNamespace(
        _register_groups=reg_groups or {},
        _transport=transport,
        client=client,
        effective_batch=125,
        available_registers={
            "input_registers": {"reg_a", "reg_b"},
            "holding_registers": {"hold_a", "hold_b"},
        },
        statistics={"total_registers_read": 0},
    )
    owner = SimpleNamespace(
        device_client=dc,
        _failed_registers=failed_registers if failed_registers is not None else set(),
    )
    owner._find_register_name = MagicMock(return_value=None)
    owner._process_register_value = MagicMock(return_value=42)
    owner._clear_register_failure = MagicMock()
    owner._mark_registers_failed = MagicMock()
    owner._read_with_retry = AsyncMock()
    owner._call_modbus = AsyncMock()
    return owner


def _ok_response(values):
    r = MagicMock()
    r.registers = list(values)
    return r


# ---------------------------------------------------------------------------
# _merge_batch_read_results
# ---------------------------------------------------------------------------


def test_merge_stores_processed_value():
    owner = _make_owner()
    owner._find_register_name.return_value = "reg_a"
    owner._process_register_value.return_value = 55
    data = {}
    _merge_batch_read_results(owner, _ok_response([10]), chunk_start=0, data=data)
    assert data == {"reg_a": 55}
    assert owner.device_client.statistics["total_registers_read"] == 1


def test_merge_skips_when_register_not_available():
    owner = _make_owner()
    owner._find_register_name.return_value = "unknown_reg"
    data = {}
    _merge_batch_read_results(owner, _ok_response([10]), chunk_start=0, data=data)
    assert data == {}


def test_merge_skips_when_process_returns_none():
    owner = _make_owner()
    owner._find_register_name.return_value = "reg_a"
    owner._process_register_value.return_value = None
    data = {}
    _merge_batch_read_results(owner, _ok_response([10]), chunk_start=0, data=data)
    assert data == {}
    assert owner.device_client.statistics["total_registers_read"] == 0


def test_merge_clears_failure_on_success():
    owner = _make_owner()
    owner._find_register_name.return_value = "reg_a"
    owner._process_register_value.return_value = 7
    _merge_batch_read_results(owner, _ok_response([7]), chunk_start=0, data={})
    owner._clear_register_failure.assert_called_once_with("reg_a")


# ---------------------------------------------------------------------------
# _fallback_individual_input_reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_reads_each_register():
    owner = _make_owner()
    owner._process_register_value.return_value = 99
    owner._read_with_retry.return_value = _ok_response([99])
    data = {}
    await _fallback_individual_input_reads(
        owner, owner._read_with_retry, 0, ["reg_a", "reg_b"], data
    )
    assert data == {"reg_a": 99, "reg_b": 99}


@pytest.mark.asyncio
async def test_fallback_skips_none_register_names():
    owner = _make_owner()
    owner._read_with_retry.return_value = _ok_response([1])
    data = {}
    await _fallback_individual_input_reads(owner, owner._read_with_retry, 0, [None, "reg_a"], data)
    assert owner._read_with_retry.call_count == 1


@pytest.mark.asyncio
async def test_fallback_marks_failed_on_permanent_error():
    owner = _make_owner()
    owner._read_with_retry.side_effect = _PermanentModbusError("bad")
    await _fallback_individual_input_reads(owner, owner._read_with_retry, 0, ["reg_a"], {})
    owner._mark_registers_failed.assert_called_once_with(["reg_a"])


@pytest.mark.asyncio
async def test_fallback_marks_failed_on_modbus_exception():
    owner = _make_owner()
    owner._read_with_retry.side_effect = ModbusException("err")
    await _fallback_individual_input_reads(owner, owner._read_with_retry, 0, ["reg_a"], {})
    owner._mark_registers_failed.assert_called_once_with(["reg_a"])


@pytest.mark.asyncio
async def test_fallback_marks_failed_when_response_empty():
    owner = _make_owner()
    owner._read_with_retry.return_value = _ok_response([])
    await _fallback_individual_input_reads(owner, owner._read_with_retry, 0, ["reg_a"], {})
    owner._mark_registers_failed.assert_called_once_with(["reg_a"])


# ---------------------------------------------------------------------------
# _handle_batch_read_failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_failure_empty_response_triggers_per_register_fallback():
    owner = _make_owner()
    owner._read_with_retry.return_value = _ok_response([5])
    owner._process_register_value.return_value = 5
    data = {}
    await _handle_batch_read_failure(
        owner,
        response=_ok_response([]),
        chunk_count=2,
        register_names=["reg_a", "reg_b"],
        read_method=owner._read_with_retry,
        chunk_start=0,
        data=data,
    )
    assert owner._read_with_retry.call_count == 2


@pytest.mark.asyncio
async def test_handle_failure_partial_response_marks_tail_failed():
    owner = _make_owner()
    data = {}
    await _handle_batch_read_failure(
        owner,
        response=_ok_response([1]),
        chunk_count=3,
        register_names=["reg_a", "reg_b", None],
        read_method=owner._read_with_retry,
        chunk_start=0,
        data=data,
    )
    owner._mark_registers_failed.assert_called_once_with(["reg_b", None])


# ---------------------------------------------------------------------------
# _read_input_register_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_batch_skips_when_all_already_failed():
    owner = _make_owner(failed_registers={"reg_a", "reg_b"})
    await _read_input_register_batch(
        owner, owner._read_with_retry, 0, 2, ["reg_a", "reg_b"], {}, {"reg_a", "reg_b"}
    )
    owner._read_with_retry.assert_not_called()


@pytest.mark.asyncio
async def test_read_batch_success_path():
    owner = _make_owner()
    owner._find_register_name.return_value = "reg_a"
    owner._process_register_value.return_value = 10
    owner._read_with_retry.return_value = _ok_response([10, 20])
    data = {}
    await _read_input_register_batch(
        owner, owner._read_with_retry, 0, 2, ["reg_a", "reg_b"], data, set()
    )
    assert "reg_a" in data


@pytest.mark.asyncio
async def test_read_batch_connection_exception_propagates():
    owner = _make_owner()
    owner._read_with_retry.side_effect = ConnectionException("down")
    with pytest.raises(ConnectionException):
        await _read_input_register_batch(owner, owner._read_with_retry, 0, 1, ["reg_a"], {}, set())


@pytest.mark.asyncio
async def test_read_batch_permanent_error_marks_failed():
    owner = _make_owner()
    owner._read_with_retry.side_effect = _PermanentModbusError("perm")
    await _read_input_register_batch(owner, owner._read_with_retry, 0, 1, ["reg_a"], {}, set())
    owner._mark_registers_failed.assert_called_once_with(["reg_a"])


@pytest.mark.asyncio
async def test_read_batch_modbus_exception_marks_failed():
    owner = _make_owner()
    owner._read_with_retry.side_effect = ModbusException("transient")
    await _read_input_register_batch(owner, owner._read_with_retry, 0, 1, ["reg_a"], {}, set())
    owner._mark_registers_failed.assert_called_once_with(["reg_a"])


# ---------------------------------------------------------------------------
# read_input_registers_optimized
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_input_no_group_returns_empty():
    owner = _make_owner(reg_groups={})
    result = await read_input_registers_optimized(owner)
    assert result == {}


@pytest.mark.asyncio
async def test_read_input_no_transport_no_client_raises():
    owner = _make_owner(reg_groups={"input_registers": [(0, 1)]}, transport=None, client=None)
    with pytest.raises(ConnectionException):
        await read_input_registers_optimized(owner)


@pytest.mark.asyncio
async def test_read_input_uses_transport_when_connected():
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(return_value=_ok_response([]))
    owner = _make_owner(
        reg_groups={"input_registers": [(0, 1)]},
        transport=transport,
    )
    owner._find_register_name.return_value = "reg_a"
    owner._read_with_retry.return_value = _ok_response([5])
    owner._process_register_value.return_value = 5
    await read_input_registers_optimized(owner)


# ---------------------------------------------------------------------------
# read_holding_individually
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_holding_individually_success():
    owner = _make_owner()
    owner._process_register_value.return_value = 77
    owner._read_with_retry.return_value = _ok_response([77])
    data = {}
    await read_holding_individually(owner, owner._read_with_retry, 0, ["hold_a"], data)
    assert data == {"hold_a": 77}
    assert owner.device_client.statistics["total_registers_read"] == 1


@pytest.mark.asyncio
async def test_read_holding_individually_connection_exception_propagates():
    owner = _make_owner()
    owner._read_with_retry.side_effect = ConnectionException("down")
    with pytest.raises(ConnectionException):
        await read_holding_individually(owner, owner._read_with_retry, 0, ["hold_a"], {})


@pytest.mark.asyncio
async def test_read_holding_individually_marks_failed_on_permanent():
    owner = _make_owner()
    owner._read_with_retry.side_effect = _PermanentModbusError("perm")
    await read_holding_individually(owner, owner._read_with_retry, 0, ["hold_a"], {})
    owner._mark_registers_failed.assert_called_once_with(["hold_a"])


# ---------------------------------------------------------------------------
# read_holding_registers_optimized
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_holding_no_group_returns_empty():
    owner = _make_owner(reg_groups={})
    result = await read_holding_registers_optimized(owner)
    assert result == {}


@pytest.mark.asyncio
async def test_read_holding_no_transport_no_client_returns_empty():
    owner = _make_owner(reg_groups={"holding_registers": [(0, 1)]}, transport=None, client=None)
    result = await read_holding_registers_optimized(owner)
    assert result == {}


@pytest.mark.asyncio
async def test_read_holding_uses_transport_when_connected():
    transport = MagicMock()
    transport.is_connected.return_value = True
    owner = _make_owner(
        reg_groups={"holding_registers": [(0, 2)]},
        transport=transport,
    )
    owner._find_register_name.return_value = "hold_a"
    owner._process_register_value.return_value = 3
    owner._read_with_retry.return_value = _ok_response([3, 4])
    result = await read_holding_registers_optimized(owner)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Multi-word register assembly (device_name / serial_number)
# ---------------------------------------------------------------------------


def _real_name_owner(register_type, names, batch):
    from custom_components.thessla_green_modbus.core.register_processing import (
        find_register_name,
        process_register_value,
    )
    from custom_components.thessla_green_modbus.register_defs_cache import (
        get_register_definitions,
    )

    function = 3 if register_type == "holding_registers" else 4
    reverse = {
        register_type: {
            d.address: n for n, d in get_register_definitions().items() if d.function == function
        }
    }
    owner = _make_owner(reg_groups={register_type: [(names[0], names[1])]})
    owner.device_client.effective_batch = batch
    owner.device_client.available_registers = {register_type: set(names[2])}
    owner.device_client._transport = MagicMock()
    owner.device_client._transport.is_connected.return_value = True
    owner._find_register_name = lambda rt, addr: find_register_name(reverse, rt, addr)
    owner._process_register_value = process_register_value
    return owner


@pytest.mark.asyncio
@pytest.mark.parametrize("batch", [3, 8, 16])
async def test_holding_poll_assembles_device_name_across_chunks(batch):
    words = [int.from_bytes(b, "big") for b in (b"Ai", b"rP", b"ac", b"k ", b"40", b"0h")]
    words += [0, 0]
    names = {"device_name"} | {f"device_name_{i}" for i in range(2, 9)}
    owner = _real_name_owner("holding_registers", (8144, 8, names), batch)

    def read(addr, count):
        return _ok_response(words[addr - 8144 : addr - 8144 + count])

    owner._read_with_retry = AsyncMock(side_effect=lambda _m, a, c, **_k: read(a, c))
    data = await read_holding_registers_optimized(owner)

    assert data["device_name"] == "AirPack 400h"


@pytest.mark.asyncio
async def test_holding_poll_drops_incomplete_multi_word_value():
    names = {"device_name"}
    owner = _real_name_owner("holding_registers", (8144, 8, names), 8)
    owner._read_with_retry = AsyncMock(return_value=_ok_response([0x4142]))
    owner._read_holding_individually = AsyncMock()
    data = await read_holding_registers_optimized(owner)

    assert "device_name" not in data


@pytest.mark.asyncio
async def test_input_poll_assembles_serial_number():
    raw = b"AB1234567890"
    words = [int.from_bytes(raw[i : i + 2], "big") for i in range(0, 12, 2)]
    owner = _real_name_owner("input_registers", (24, 6, {"serial_number"}), 4)

    def read(addr, count):
        return _ok_response(words[addr - 24 : addr - 24 + count])

    owner._read_with_retry = AsyncMock(side_effect=lambda _m, a, c, **_k: read(a, c))
    data = await read_input_registers_optimized(owner)

    assert data["serial_number"] == "AB1234567890"


@pytest.mark.asyncio
async def test_holding_poll_assembles_lock_pass_u32():
    """Vendor example: 0x423f (8187), 0x000f (8188) is product key 999999."""
    owner = _real_name_owner("holding_registers", (8187, 2, {"lock_pass"}), 16)
    owner._read_with_retry = AsyncMock(return_value=_ok_response([0x423F, 0x000F]))
    data = await read_holding_registers_optimized(owner)

    assert data["lock_pass"] == 999999


@pytest.mark.asyncio
async def test_holding_fallback_reads_still_assemble_lock_pass():
    """A failed batch recovered by single reads keeps the multi-word value."""
    owner = _real_name_owner("holding_registers", (8187, 2, {"lock_pass"}), 16)
    singles = {8187: 0x423F, 8188: 0x000F}

    def read(addr, count):
        if count > 1:
            raise ModbusException("batch failed")
        return _ok_response([singles[addr]])

    owner._read_with_retry = AsyncMock(side_effect=lambda _m, a, c, **_k: read(a, c))
    data = await read_holding_registers_optimized(owner)

    assert data["lock_pass"] == 999999


@pytest.mark.asyncio
async def test_holding_partial_batch_tail_recovery_assembles_device_name():
    words = [int.from_bytes(b, "big") for b in (b"Ai", b"rP", b"ac", b"k ", b"40", b"0h")]
    words += [0, 0]
    names = {"device_name"} | {f"device_name_{i}" for i in range(2, 9)}
    owner = _real_name_owner("holding_registers", (8144, 8, names), 8)

    def read(addr, count):
        if count > 1:
            return _ok_response(words[:3])
        return _ok_response([words[addr - 8144]])

    owner._read_with_retry = AsyncMock(side_effect=lambda _m, a, c, **_k: read(a, c))
    data = await read_holding_registers_optimized(owner)

    assert data["device_name"] == "AirPack 400h"


@pytest.mark.asyncio
async def test_input_empty_batch_fallback_assembles_serial_number():
    raw = b"AB1234567890"
    words = [int.from_bytes(raw[i : i + 2], "big") for i in range(0, 12, 2)]
    names = {"serial_number"} | {f"serial_number_{i}" for i in range(2, 7)}
    owner = _real_name_owner("input_registers", (24, 6, names), 16)

    def read(addr, count):
        if count > 1:
            return _ok_response([])
        return _ok_response([words[addr - 24]])

    owner._read_with_retry = AsyncMock(side_effect=lambda _m, a, c, **_k: read(a, c))
    data = await read_input_registers_optimized(owner)

    assert data["serial_number"] == "AB1234567890"
