"""Diagnostics must return physical words without changing device state."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from custom_components.thessla_green_modbus.registers.register_def import RegisterDef
from custom_components.thessla_green_modbus.services import handlers_register_read as module
from homeassistant.exceptions import ServiceValidationError


def coordinator():
    return SimpleNamespace(
        device_client=SimpleNamespace(_write_lock=asyncio.Lock()), _ensure_connection=AsyncMock()
    )


def response(words=None, bits=None, error=False):
    return SimpleNamespace(registers=words, bits=bits, isError=lambda: error, exception_code=2)


@pytest.mark.asyncio
async def test_atomic_clock_aliases_and_duplicate_names_share_complete_read(monkeypatch):
    definitions = {f"word_{i}": RegisterDef(3, i, f"word_{i}", "R") for i in range(4)}
    monkeypatch.setattr(module, "get_register_definition", definitions.__getitem__)
    read = AsyncMock(return_value=response([0x2610, 0x2802, 0x1200, 0]))
    monkeypatch.setattr(module, "_read_batch_via_existing_client", read)
    result = await module.read_register_diagnostics(coordinator(), ["word_1", "word_2", "word_1"])
    assert result["registers"]["word_1"]["raw"] == [0x2802]
    assert result["registers"]["word_2"]["raw"] == [0x1200]
    assert result["writes_sent"] == 0
    assert read.await_count == 1
    assert read.call_args.args[1:] == ("holding_registers", 0, 4)


@pytest.mark.asyncio
@pytest.mark.parametrize("address,count", [(7, 3), (8, 3), (9, 3), (50, 1)])
async def test_lock_date_and_ordinary_reads(monkeypatch, address, count):
    monkeypatch.setattr(
        module, "get_register_definition", lambda _: RegisterDef(3, address, "reg", "R")
    )
    read = AsyncMock(return_value=response([10] * count))
    monkeypatch.setattr(module, "_read_batch_via_existing_client", read)
    result = await module.read_register_diagnostics(coordinator(), ["reg"])
    assert result["registers"]["reg"]["status"] == "ok"
    assert read.call_args.args[2:] == (7 if address < 10 else 50, count)


@pytest.mark.asyncio
@pytest.mark.parametrize("function", [1, 2, 4])
async def test_bit_and_input_reads(monkeypatch, function):
    monkeypatch.setattr(
        module, "get_register_definition", lambda _: RegisterDef(function, 50, "reg", "R")
    )
    monkeypatch.setattr(
        module,
        "_read_batch_via_existing_client",
        AsyncMock(return_value=response([42], [True] * 8)),
    )
    result = await module.read_register_diagnostics(coordinator(), ["reg"])
    assert result["registers"]["reg"]["raw"] == ([True] if function < 3 else [42])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply,status",
    [
        (None, "indeterminate"),
        (response(error=True), "modbus_exception"),
        (response([]), "incomplete_response"),
    ],
)
async def test_no_success_for_missing_error_or_truncated_data(monkeypatch, reply, status):
    monkeypatch.setattr(module, "_read_batch_via_existing_client", AsyncMock(return_value=reply))
    result = await module.read_register_diagnostics(coordinator(), ["s_17"])
    assert result["registers"]["s_17"]["status"] == status
    assert result["registers"]["s_17"]["raw"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), OSError()])
async def test_transport_failure_is_indeterminate(monkeypatch, error):
    monkeypatch.setattr(module, "_read_batch_via_existing_client", AsyncMock(side_effect=error))
    result = await module.read_register_diagnostics(coordinator(), ["s_17"])
    assert result["registers"]["s_17"]["status"] == "indeterminate"


@pytest.mark.asyncio
async def test_invalid_serial_preserves_raw_but_is_not_decoded(monkeypatch):
    monkeypatch.setattr(
        module, "_read_batch_via_existing_client", AsyncMock(return_value=response([0xFFFF] * 6))
    )
    result = await module.read_register_diagnostics(coordinator(), ["serial_number"])
    assert result["registers"]["serial_number"]["status"] == "decode_error"
    assert result["registers"]["serial_number"]["raw"] == [0xFFFF] * 6


@pytest.mark.asyncio
async def test_unknown_name_rejected_before_connecting():
    dc = coordinator()
    with pytest.raises(ServiceValidationError):
        await module.read_register_diagnostics(dc, ["s_17", "not_a_register"])
    dc._ensure_connection.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("target_count", [0, 1, 2])
async def test_handler_requires_exactly_one_unit(monkeypatch, target_count):
    hass = SimpleNamespace(services=Mock())
    targets = [(f"climate.unit_{i}", coordinator()) for i in range(target_count)]
    deps = SimpleNamespace(domain="test", iter_target_coordinators=AsyncMock(return_value=targets))
    module.register_register_read_service(hass, deps)
    handle = hass.services.async_register.call_args.args[2]
    read = AsyncMock(return_value={"writes_sent": 0})
    monkeypatch.setattr(module, "read_register_diagnostics", read)
    if target_count == 1:
        assert await handle(SimpleNamespace(data={"names": ["s_17"]})) == {"writes_sent": 0}
    else:
        with pytest.raises(ServiceValidationError):
            await handle(SimpleNamespace(data={"names": ["s_17"]}))
        read.assert_not_awaited()


@pytest.mark.parametrize("names", [[], ["s_17"] * 33, [123]])
def test_schema_bounds(names):
    import voluptuous as vol

    with pytest.raises(vol.Invalid):
        module.READ_REGISTER_DIAGNOSTICS_SCHEMA({"entity_id": "climate.unit", "names": names})
