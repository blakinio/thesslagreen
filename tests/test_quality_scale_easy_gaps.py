# mypy: ignore-errors
"""Close small, deterministic quality-scale coverage gaps."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus._config_flow import ConfigFlow
from custom_components.thessla_green_modbus.core import (
    client_scanner,
    connection_lifecycle,
    runtime_io,
)
from custom_components.thessla_green_modbus.device_registry_migration import (
    _belongs_to_entry,
)
from custom_components.thessla_green_modbus.mappings import _mapping_payloads
from custom_components.thessla_green_modbus.registers import load_cache_helpers
from custom_components.thessla_green_modbus.scanner import (
    capabilities_facade,
    helpers,
    register_maps,
)
from pymodbus.exceptions import ConnectionException


@pytest.mark.asyncio
async def test_reconfigure_without_submission_displays_form() -> None:
    entry = SimpleNamespace(data={"host": "192.0.2.10"})
    flow = ConfigFlow()
    flow._get_reconfigure_entry = MagicMock(return_value=entry)
    flow.async_show_form = MagicMock(return_value={"type": "form"})

    with patch(
        "custom_components.thessla_green_modbus._config_flow._build_reconfigure_schema_impl",
        return_value="schema",
    ):
        result = await flow.async_step_reconfigure(None)

    assert result == {"type": "form"}
    flow.async_show_form.assert_called_once_with(
        step_id="reconfigure", data_schema="schema", errors={}
    )


@pytest.mark.asyncio
async def test_device_client_scanner_factory_scan_and_normalise() -> None:
    mixin = client_scanner._DeviceClientScannerMixin()
    mixin.config = SimpleNamespace(
        host="host",
        port=502,
        slave_id=10,
        connection_type="tcp",
        connection_mode="auto",
        serial_port="",
        baud_rate=9600,
        parity="N",
        stop_bits=1,
    )
    mixin.timeout = 2.0
    mixin.retry = 2
    mixin.backoff = 0.1
    mixin.backoff_jitter = 0.0
    mixin.scan_uart_settings = False
    mixin.skip_missing_registers = True
    mixin.deep_scan = False
    mixin.effective_batch = 8
    mixin.safe_scan = True
    mixin.hass = object()
    mixin._resolved_connection_mode = "tcp"

    scanner = SimpleNamespace(scan_device=AsyncMock(return_value={"ok": True}))
    with patch.object(
        client_scanner.ThesslaGreenDeviceScanner,
        "create",
        new=AsyncMock(return_value=scanner),
    ) as create:
        assert await mixin.async_create_scanner() is scanner
    assert create.await_args.kwargs["connection_mode"] == "tcp"

    mixin.async_create_scanner = AsyncMock(return_value=scanner)
    assert await mixin.async_scan_device() == {"ok": True}
    scanner.scan_device.assert_awaited_once_with()

    with patch.object(
        client_scanner,
        "_normalise_available_registers_impl",
        return_value={"holding_registers": {"mode"}},
    ) as normalise:
        assert mixin._normalise_available_registers({"holding_registers": ["mode"]}) == {
            "holding_registers": {"mode"}
        }
    normalise.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_connected_lifecycle_updates_runtime_and_mode() -> None:
    device_client = SimpleNamespace(
        _client_lock=asyncio.Lock(),
        _transport=None,
        client=None,
        _resolved_connection_mode=None,
    )
    ensure_runtime = AsyncMock(return_value=("transport", "client", "tcp_rtu"))
    selector = AsyncMock()

    await connection_lifecycle.ensure_connected_lifecycle(
        device_client,
        disconnect_locked_fn=AsyncMock(),
        ensure_connected_runtime_fn=ensure_runtime,
        reconnect_client_if_needed_fn=AsyncMock(),
        ensure_transport_selected_fn_factory=lambda: selector,
        connect_transport_or_client_fn=AsyncMock(),
        mark_connection_established_fn=Mock(),
        mark_connection_failure_fn=Mock(),
        logger=Mock(),
    )

    assert device_client._transport == "transport"
    assert device_client.client == "client"
    assert device_client._resolved_connection_mode == "tcp_rtu"
    assert ensure_runtime.await_args.kwargs["ensure_transport_selected_fn"] is selector


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "log_method"),
    [
        (ConnectionException("connect"), "exception"),
        (TimeoutError("timeout"), "warning"),
        (OSError("os"), "exception"),
    ],
)
async def test_ensure_connected_lifecycle_logs_and_reraises(error, log_method) -> None:
    device_client = SimpleNamespace(
        _client_lock=asyncio.Lock(),
        _transport=None,
        client=None,
        _resolved_connection_mode=None,
    )
    logger = Mock()
    with pytest.raises(type(error)):
        await connection_lifecycle.ensure_connected_lifecycle(
            device_client,
            disconnect_locked_fn=AsyncMock(),
            ensure_connected_runtime_fn=AsyncMock(side_effect=error),
            reconnect_client_if_needed_fn=AsyncMock(),
            ensure_transport_selected_fn_factory=lambda: AsyncMock(),
            connect_transport_or_client_fn=AsyncMock(),
            mark_connection_established_fn=Mock(),
            mark_connection_failure_fn=Mock(),
            logger=logger,
        )
    getattr(logger, log_method).assert_called_once()


@pytest.mark.asyncio
async def test_runtime_io_uses_transport_and_post_processes_reads() -> None:
    transport = SimpleNamespace(call=AsyncMock(return_value="transport-result"))
    client = SimpleNamespace(
        _transport=transport,
        client=None,
        slave_id=10,
        retry=3,
        timeout=2.0,
        backoff=0.1,
        backoff_jitter=0.2,
    )
    func = object()
    assert await runtime_io.call_modbus(client, func, 5, attempt=2, count=1) == "transport-result"
    transport.call.assert_awaited_once_with(
        func,
        10,
        5,
        attempt=2,
        max_attempts=3,
        backoff=0.1,
        backoff_jitter=0.2,
        count=1,
    )

    client._read_input_registers_optimized = AsyncMock(return_value={"a": 1})
    client._read_holding_registers_optimized = AsyncMock(return_value={"b": 2})
    client._read_coil_registers_optimized = AsyncMock(return_value={"c": 3})
    client._read_discrete_inputs_optimized = AsyncMock(return_value={"d": 4})
    client._post_process_data = Mock(return_value={"done": 10})
    assert await runtime_io.read_all_register_data(client) == {"done": 10}
    client._post_process_data.assert_called_once_with({"a": 1, "b": 2, "c": 3, "d": 4})


def test_device_registry_membership_handles_non_iterable_config_entries() -> None:
    assert _belongs_to_entry(SimpleNamespace(config_entry_id="entry"), "entry") is True
    assert _belongs_to_entry(SimpleNamespace(config_entries={"entry"}), "entry") is True
    assert _belongs_to_entry(SimpleNamespace(config_entries=None), "entry") is False


def test_mapping_payloads_cover_invalid_and_unclassified_states() -> None:
    assert _mapping_payloads.parse_info_states("bad; x - invalid; 1 - Good Label") == {
        "good_label": 1
    }
    assert (
        _mapping_payloads.classify_discrete_holding_payload(
            "binary_only",
            "R",
            {"off": 0, "on": 1},
            set(),
            {"binary_only"},
            set(),
        )[0]
        == "binary"
    )
    assert _mapping_payloads.classify_discrete_holding_payload(
        "unknown",
        "R",
        {"off": 0, "on": 1},
        set(),
        set(),
        set(),
    ) == (None, None)
    assert _mapping_payloads.classify_discrete_holding_payload(
        "select_me",
        "R",
        {"one": 1, "two": 2, "three": 3},
        set(),
        set(),
        {"select_me"},
    ) == (
        "select",
        {
            "translation_key": "select_me",
            "register_type": "holding_registers",
            "states": {"one": 1, "two": 2, "three": 3},
        },
    )


def test_cached_mtime_requires_metadata() -> None:
    with patch.object(load_cache_helpers, "get_cached_file_info", return_value=None):
        with pytest.raises(RuntimeError, match="Missing cache metadata"):
            load_cache_helpers._get_cached_mtime(SimpleNamespace())


@pytest.mark.asyncio
async def test_register_maps_noop_and_rebuild_paths() -> None:
    original_definitions = dict(register_maps.REGISTER_DEFINITIONS)
    original_hash = register_maps.REGISTER_HASH
    try:
        register_maps.REGISTER_DEFINITIONS.clear()
        register_maps.REGISTER_DEFINITIONS["existing"] = object()
        register_maps.REGISTER_HASH = "same"
        with (
            patch.object(register_maps, "registers_sha256", return_value="same"),
            patch.object(register_maps, "_build_register_maps") as build,
        ):
            register_maps._ensure_register_maps()
        build.assert_not_called()

        register_maps.REGISTER_HASH = "old"
        with (
            patch.object(register_maps, "registers_sha256", return_value="new"),
            patch.object(register_maps, "_build_register_maps") as build,
        ):
            register_maps._ensure_register_maps()
        build.assert_called_once_with()

        register_maps.REGISTER_HASH = "same"
        with (
            patch.object(
                register_maps, "async_registers_sha256", new=AsyncMock(return_value="same")
            ),
            patch.object(register_maps, "_async_build_register_maps", new=AsyncMock()) as build,
        ):
            await register_maps._async_ensure_register_maps(None)
        build.assert_not_awaited()

        register_maps.REGISTER_HASH = "old"
        with (
            patch.object(
                register_maps, "async_registers_sha256", new=AsyncMock(return_value="new")
            ),
            patch.object(register_maps, "_async_build_register_maps", new=AsyncMock()) as build,
        ):
            await register_maps._async_ensure_register_maps(None)
        build.assert_awaited_once_with(None)
    finally:
        register_maps.REGISTER_DEFINITIONS.clear()
        register_maps.REGISTER_DEFINITIONS.update(original_definitions)
        register_maps.REGISTER_HASH = original_hash


def test_scanner_helper_manual_and_setting_fallbacks() -> None:
    with patch.object(helpers, "_decode_register_time", return_value=None):
        assert helpers._format_register_value("manual_airing_time_to_start", 123) == "123 (invalid)"
        assert (
            helpers._format_register_value(
                "manual_airing_time_to_start", helpers.SENSOR_UNAVAILABLE
            )
            is None
        )

    with patch.object(helpers, "_decode_aatt", return_value=None):
        assert helpers._format_register_value("setting_test", 123) == 123
    with patch.object(helpers, "_decode_aatt", return_value={"airflow_pct": None, "temp_c": 20}):
        assert helpers._format_register_value("setting_test", 123) == 123
    with patch.object(helpers, "_decode_aatt", return_value={"airflow_pct": 55, "temp_c": 20.5}):
        assert helpers._format_register_value("setting_test", 123) == "55% @ 20.5°C"


def test_scanner_capability_facade_delegates_input_unsupported() -> None:
    facade = capabilities_facade.ScannerCapabilitiesFacadeMixin()
    with patch.object(capabilities_facade.scanner_capabilities, "mark_input_unsupported") as mark:
        facade._mark_input_unsupported(10, 20, None)
    mark.assert_called_once_with(facade, 10, 20, None)
