# mypy: ignore-errors
"""Exercise small compatibility, facade, schema, and cache modules."""

from __future__ import annotations

import asyncio
import importlib
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pymodbus.exceptions import ModbusException

from custom_components.thessla_green_modbus import (
    button as button_module,
    error_contract,
    protocols,
    register_defs_cache,
)
from custom_components.thessla_green_modbus.modbus import framer as framer_module
from custom_components.thessla_green_modbus.registers import (
    parse_file_helpers,
    parser as parser_module,
)
from custom_components.thessla_green_modbus.scanner import (
    read_facade,
    register_map_cache,
    register_map_facade,
    register_map_runtime,
)
from custom_components.thessla_green_modbus.services import schema as service_schema


@pytest.mark.asyncio
async def test_protocol_method_bodies_are_runtime_safe() -> None:
    """Typing protocol stubs remain harmless if introspection invokes them."""
    scanner = object()
    assert await protocols.ScannerProtocol.scan_device(scanner) is None
    assert await protocols.ScannerProtocol.close(scanner) is None
    assert (
        protocols.ScannerFactory.__call__(
            object(),
            host="host",
            port=502,
            slave_id=10,
            timeout=1,
            retry=0,
            scan_uart_settings=False,
            skip_known_missing=True,
            full_register_scan=False,
            max_registers_per_request=8,
            connection_type="tcp",
            connection_mode="tcp",
            serial_port="",
            baud_rate=9600,
            parity="N",
            stop_bits=1,
            hass=object(),
        )
        is None
    )


@pytest.mark.asyncio
async def test_button_setup_delegates_entity_creation() -> None:
    coordinator = object()
    entity = object()
    entry = SimpleNamespace(runtime_data=coordinator)
    add_entities = Mock()
    with patch.object(
        button_module, "SyncDeviceClockButton", return_value=entity
    ) as button_cls:
        await button_module.async_setup_entry(object(), entry, add_entities)
    button_cls.assert_called_once_with(coordinator, entry)
    add_entities.assert_called_once_with([entity])


def test_error_contract_all_kinds_and_retry_log_details() -> None:
    assert error_contract.classify_error(TimeoutError("slow")) == error_contract.ErrorContract(
        "transient", "timeout"
    )
    assert error_contract.classify_error(
        asyncio.CancelledError()
    ) == error_contract.ErrorContract("transient", "cancelled")
    assert error_contract.classify_error(
        ModbusException("illegal data address")
    ) == error_contract.ErrorContract("permanent", "illegal_data_address")
    assert error_contract.classify_error(ValueError("unexpected")) == error_contract.ErrorContract(
        "permanent", "unexpected"
    )
    assert error_contract.is_transient(TimeoutError()) is True

    logger = Mock(spec=logging.Logger)
    exc = TimeoutError("retry")
    error_contract.log_retry_attempt(
        logger=logger,
        layer="scanner",
        operation="read",
        attempt=2,
        max_attempts=3,
        exc=exc,
        backoff=0.25,
        extra={"address": 10},
    )
    logger.warning.assert_called_once()
    details = logger.warning.call_args.args[1]
    assert details["backoff"] == 0.25
    assert details["address"] == 10
    assert details["reason"] == "timeout"


def test_register_definitions_cache_clear_reloads_source() -> None:
    one = SimpleNamespace(name="one")
    two = SimpleNamespace(name="two")
    register_defs_cache.clear_register_definitions_cache()
    with patch.object(
        register_defs_cache, "get_all_registers", return_value=[one, two]
    ) as loader:
        assert register_defs_cache.get_register_definitions() == {"one": one, "two": two}
        assert register_defs_cache.get_register_definitions() == {"one": one, "two": two}
        loader.assert_called_once_with()
        register_defs_cache.clear_register_definitions_cache()
        assert register_defs_cache.get_register_definitions() == {"one": one, "two": two}
        assert loader.call_count == 2
    register_defs_cache.clear_register_definitions_cache()


@pytest.mark.asyncio
async def test_async_register_json_errors_are_normalized() -> None:
    path = Path("missing.json")
    with patch.object(
        parse_file_helpers,
        "_async_executor",
        new=AsyncMock(side_effect=FileNotFoundError()),
    ):
        with pytest.raises(RuntimeError, match="Register definition file missing"):
            await parse_file_helpers.async_read_registers_json(None, path)

    with patch.object(
        parse_file_helpers,
        "_async_executor",
        new=AsyncMock(return_value="not-json"),
    ):
        with pytest.raises(RuntimeError, match="Failed to read register definitions"):
            await parse_file_helpers.async_read_registers_json(None, path)


def test_parser_schema_delegate_and_reversed_enum_paths() -> None:
    model_validate = Mock(return_value=SimpleNamespace(registers=["validated"]))
    fake_list = SimpleNamespace(model_validate=model_validate)
    with patch.object(parser_module, "RegisterList", fake_list):
        assert parser_module._parse_schema_items({"registers": [1]}) == ["validated"]
    model_validate.assert_called_once_with([1])

    assert parser_module.normalise_enum_map("mode", {"off": "0", "on": "1"}) == {
        0: "off",
        1: "on",
    }


def test_parser_special_modes_import_error_paths_restore_module() -> None:
    """Exercise both expected and unexpected special-mode load failures."""
    try:
        with patch.object(Path, "read_text", side_effect=OSError("unavailable")):
            importlib.reload(parser_module)
            assert parser_module._SPECIAL_MODES_ENUM == {}
        with patch.object(Path, "read_text", side_effect=TypeError("bad path")):
            importlib.reload(parser_module)
            assert parser_module._SPECIAL_MODES_ENUM == {}
    finally:
        importlib.reload(parser_module)


def test_framer_missing_enum_and_invalid_enum_paths_restore_module() -> None:
    real_import = __import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pymodbus.framer" and "FramerType" in fromlist:
            raise ImportError("FramerType unavailable")
        return real_import(name, globals, locals, fromlist, level)

    try:
        with patch("builtins.__import__", side_effect=blocked_import):
            importlib.reload(framer_module)
            assert framer_module.FramerType is None
            result = framer_module.get_rtu_framer()
            assert result is framer_module.ModbusRtuFramer or result is None

        framer_module.FramerType = SimpleNamespace()
        assert framer_module.get_rtu_framer() is None
    finally:
        importlib.reload(framer_module)


@pytest.mark.asyncio
async def test_scanner_read_facade_delegates_all_helpers() -> None:
    facade = read_facade.ScannerReadFacadeMixin()
    io = read_facade.scanner_domain_io

    with (
        patch.object(io, "unpack_read_args", return_value=(None, 1, 2)) as unpack,
        patch.object(
            io,
            "resolve_transport_and_client",
            return_value=("transport", "client"),
        ) as resolve,
        patch.object(io, "track_input_failure") as input_failure,
        patch.object(io, "track_holding_failure") as holding_failure,
        patch.object(io, "read_input", new=AsyncMock(return_value=[1])) as read_input,
        patch.object(
            io, "read_register_block", new=AsyncMock(return_value=[2])
        ) as read_block,
        patch.object(io, "read_holding", new=AsyncMock(return_value=[3])) as read_holding,
        patch.object(
            io, "read_bit_registers", new=AsyncMock(return_value=[True])
        ) as read_bits,
        patch.object(io, "read_coil", new=AsyncMock(return_value=[False])) as read_coil,
        patch.object(
            io, "read_discrete", new=AsyncMock(return_value=[True])
        ) as read_discrete,
    ):
        assert facade._unpack_read_args(1, 2, None) == (None, 1, 2)
        assert facade._resolve_transport_and_client(None) == ("transport", "client")
        facade._track_input_failure(2, 10)
        facade._track_holding_failure(3, 11)
        assert await facade._read_input(10, 2, skip_cache=True) == [1]
        assert await facade._read_register_block("fn", 10, 2) == [2]
        assert await facade._read_holding(10, 2, skip_cache=True) == [3]
        assert (
            await facade._read_bit_registers(
                "read_coils", "failed", "coils", 10, 2
            )
            == [True]
        )
        assert await facade._read_coil(10, 2) == [False]
        assert await facade._read_discrete(10, 2) == [True]

    unpack.assert_called_once()
    resolve.assert_called_once()
    input_failure.assert_called_once_with(facade, 2, 10)
    holding_failure.assert_called_once_with(facade, 3, 11)
    read_input.assert_awaited_once()
    read_block.assert_awaited_once()
    read_holding.assert_awaited_once()
    read_bits.assert_awaited_once()
    read_coil.assert_awaited_once()
    read_discrete.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_map_cache_and_facades_delegate_all_paths() -> None:
    maps = register_map_cache._register_maps
    with (
        patch.object(maps, "_build_register_maps_from") as build_from,
        patch.object(maps, "_build_register_maps") as build,
        patch.object(
            maps, "_async_build_register_maps", new=AsyncMock()
        ) as async_build,
        patch.object(maps, "_ensure_register_maps") as ensure,
        patch.object(
            maps, "_async_ensure_register_maps", new=AsyncMock()
        ) as async_ensure,
    ):
        maps.REGISTER_HASH = "hash-a"
        assert register_map_cache.sync_register_hash_from_maps() == "hash-a"
        register_map_cache.build_register_maps_from(["reg"], "hash-b")
        register_map_cache.build_register_maps()
        await register_map_cache.async_build_register_maps("hass")
        register_map_cache.ensure_register_maps()
        await register_map_cache.async_ensure_register_maps("hass")
    build_from.assert_called_once_with(["reg"], "hash-b")
    build.assert_called_once_with()
    async_build.assert_awaited_once_with("hass")
    ensure.assert_called_once_with()
    async_ensure.assert_awaited_once_with("hass")

    cache = register_map_facade._register_map_cache
    with (
        patch.object(cache, "build_register_maps_from") as build_from,
        patch.object(cache, "build_register_maps") as build,
        patch.object(
            cache, "async_build_register_maps", new=AsyncMock()
        ) as async_build,
        patch.object(cache, "ensure_register_maps") as ensure,
        patch.object(
            cache, "async_ensure_register_maps", new=AsyncMock()
        ) as async_ensure,
        patch.object(
            cache,
            "sync_register_hash_from_maps",
            side_effect=["a", "b", "c", "d", "e"],
        ),
    ):
        assert register_map_facade.build_register_maps_from(["reg"], "old") == "a"
        assert register_map_facade.build_register_maps() == "b"
        assert await register_map_facade.async_build_register_maps("hass") == "c"
        assert register_map_facade.ensure_register_maps("old") == "d"
        assert (
            await register_map_facade.async_ensure_register_maps("old2", "hass")
            == "e"
        )
    build_from.assert_called_once_with(["reg"], "old")
    build.assert_called_once_with()
    async_build.assert_awaited_once_with("hass")
    ensure.assert_called_once_with()
    async_ensure.assert_awaited_once_with("hass")

    facade = register_map_runtime._register_map_facade
    with (
        patch.object(
            facade, "build_register_maps_from", return_value="from"
        ) as build_from,
        patch.object(facade, "build_register_maps", return_value="build") as build,
        patch.object(
            facade,
            "async_build_register_maps",
            new=AsyncMock(return_value="async-build"),
        ) as async_build,
        patch.object(facade, "ensure_register_maps", return_value="ensure") as ensure,
        patch.object(
            facade,
            "async_ensure_register_maps",
            new=AsyncMock(return_value="async-ensure"),
        ) as async_ensure,
    ):
        register_map_runtime._register_maps.REGISTER_HASH = None
        assert register_map_runtime.initial_register_hash() == ""
        register_map_runtime._register_maps.REGISTER_HASH = "live"
        assert register_map_runtime.sync_register_hash_from_maps() == "live"
        assert register_map_runtime.build_register_maps_from(["reg"], "hash") == "from"
        assert register_map_runtime.build_register_maps() == "build"
        assert await register_map_runtime.async_build_register_maps("hass") == "async-build"
        assert register_map_runtime.ensure_register_maps("hash") == "ensure"
        assert (
            await register_map_runtime.async_ensure_register_maps("hash", "hass")
            == "async-ensure"
        )
    build_from.assert_called_once_with(["reg"], "hash")
    build.assert_called_once_with()
    async_build.assert_awaited_once_with("hass")
    ensure.assert_called_once_with("hash")
    async_ensure.assert_awaited_once_with("hash", "hass")


def test_service_schema_validator_wrappers_delegate() -> None:
    bypass_data = {"mode": "auto"}
    gwc_data = {"mode": "auto"}
    with (
        patch.object(
            service_schema,
            "_validate_bypass_temperature_range_impl",
            return_value=bypass_data,
        ) as bypass,
        patch.object(
            service_schema,
            "_validate_gwc_temperature_range_impl",
            return_value=gwc_data,
        ) as gwc,
    ):
        assert service_schema.validate_bypass_temperature_range(bypass_data) is bypass_data
        assert service_schema.validate_gwc_temperature_range(gwc_data) is gwc_data
    bypass.assert_called_once_with(bypass_data)
    gwc.assert_called_once_with(gwc_data)
