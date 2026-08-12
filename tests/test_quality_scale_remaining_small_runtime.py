# mypy: ignore-errors
"""Exercise remaining small runtime adapters and fail-closed branches."""

from __future__ import annotations

import asyncio
from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import write_path as coordinator_write
from custom_components.thessla_green_modbus.core import (
    client_connection,
    io_mixin,
    register_groups,
    retry,
)
from custom_components.thessla_green_modbus.services import (
    handlers_mode,
    handlers_schedule,
    targets,
)
from homeassistant.exceptions import ServiceValidationError
from pymodbus.exceptions import ConnectionException


def test_register_groups_unexpected_definition_errors_fall_back_to_one_register() -> None:
    for safe_scan in (True, False):
        client = SimpleNamespace(
            _register_groups={"old": [(1, 1)]},
            available_registers={"holding_registers": {"known"}},
            _register_maps={"holding_registers": {"known": 10}},
            safe_scan=safe_scan,
            effective_batch=4,
        )
        grouped = Mock(return_value=[(10, 1)])
        register_groups.compute_register_groups(
            client,
            get_register_definition=Mock(side_effect=RuntimeError("unexpected")),
            group_reads=grouped,
            holding_batch_boundaries=frozenset({16}),
        )
        assert client._register_groups["holding_registers"] == [(10, 1)]
        if safe_scan:
            grouped.assert_not_called()
        else:
            grouped.assert_called_once_with([10], max_block_size=4, boundaries=frozenset({16}))


@pytest.mark.asyncio
async def test_io_mixin_disconnected_bit_reads_fail_closed_and_delegate() -> None:
    owner = io_mixin._ModbusIOMixin()
    owner.device_client = SimpleNamespace(client=None)
    with pytest.raises(ConnectionException, match="not connected"):
        await owner._read_coils_transport(10, 1, count=2)
    with pytest.raises(ConnectionException, match="not connected"):
        await owner._read_discrete_inputs_transport(10, 1, count=2)

    with patch.object(
        io_mixin, "_read_discrete_inputs_optimized_impl", new=AsyncMock(return_value={"x": 1})
    ) as delegated:
        assert await owner._read_discrete_inputs_optimized() == {"x": 1}
    delegated.assert_awaited_once_with(owner)


@pytest.mark.asyncio
async def test_device_client_connection_aliases_and_direct_client_paths() -> None:
    owner = client_connection._DeviceClientConnectionMixin()
    owner.config = SimpleNamespace(
        host="host", port=502, slave_id=10, parity="none", stop_bits=1,
        connection_type="tcp", connection_mode="tcp", serial_port="", baud_rate=9600,
    )
    owner._write_lock = asyncio.Lock()
    owner._transport = object()
    owner.client = object()
    owner.retry = 1
    owner.backoff = 0
    owner.timeout = 1
    owner.offline_state = False
    owner._resolved_connection_mode = None

    owner.async_ensure_connected = AsyncMock()
    owner.async_disconnect = AsyncMock()
    with patch.object(client_connection, "_run_connection_test_impl", new=AsyncMock()) as test_impl:
        await owner.async_test_connection()
    test_impl.assert_awaited_once()

    await owner._ensure_connection()
    owner.async_ensure_connected.assert_awaited_once()
    await owner._disconnect()
    owner.async_disconnect.assert_awaited_once()

    with patch.object(
        client_connection, "_close_client_connection_impl", new=AsyncMock()
    ) as close_impl:
        await owner._close_client_connection()
    close_impl.assert_awaited_once_with(client=owner.client, logger=client_connection._LOGGER)

    direct = object()
    with patch.object(
        client_connection, "_connect_direct_tcp_client_impl", new=AsyncMock(return_value=direct)
    ):
        assert await owner._try_direct_client_connect(allow_parameterless_ctor=True) is True
    assert owner.client is direct
    assert owner._transport is None

    with patch.object(
        client_connection, "_connect_direct_tcp_client_impl", new=AsyncMock(return_value=None)
    ):
        assert await owner._try_direct_client_connect(allow_parameterless_ctor=False) is False


@pytest.mark.asyncio
async def test_retry_disconnect_success_restore_and_connection_error_logging() -> None:
    previous = object()
    owner = SimpleNamespace(
        device_client=SimpleNamespace(client=previous, retry=2, _transport=None),
        _disconnect=AsyncMock(),
        _log_read_retry=Mock(),
        backoff=0,
    )

    async def disconnect_and_clear():
        owner.device_client.client = None

    owner._disconnect = AsyncMock(side_effect=disconnect_and_clear)
    assert await retry._safe_disconnect_for_retry(
        owner, register_type="holding", start_address=1, attempt=1, restore_client=True
    ) is None
    assert owner.device_client.client is previous

    exc = ConnectionException("offline")
    result = await retry._handle_retry_exception(
        owner,
        register_type="holding",
        start_address=1,
        attempt=1,
        exc=exc,
        reconnect=False,
    )
    assert result is exc
    owner._log_read_retry.assert_called_once()


@pytest.mark.asyncio
async def test_retry_reconnect_failure_is_returned() -> None:
    reconnect_error = ConnectionException("still offline")
    owner = SimpleNamespace(
        device_client=SimpleNamespace(client=object(), retry=3, _transport=object()),
        _disconnect=AsyncMock(),
        _ensure_connection=AsyncMock(side_effect=reconnect_error),
        backoff=0,
    )
    assert await retry.disconnect_and_reconnect_for_retry(
        owner, register_type="input", start_address=2, attempt=1
    ) is reconnect_error


def test_write_repair_helpers_are_best_effort() -> None:
    no_hass = SimpleNamespace()
    coordinator_write._create_write_repair(no_hass, "reg")
    coordinator_write._clear_write_repair(no_hass)

    coordinator = SimpleNamespace(hass=object(), entry=object())
    with patch.object(
        coordinator_write, "create_write_failure_issue", side_effect=RuntimeError("no registry")
    ) as create_issue:
        coordinator_write._create_write_repair(coordinator, "reg")
    create_issue.assert_called_once()

    with patch.object(
        coordinator_write, "clear_write_failure_issue", side_effect=RuntimeError("no registry")
    ) as clear_issue:
        coordinator_write._clear_write_repair(coordinator)
    clear_issue.assert_called_once()


class _Services:
    def __init__(self):
        self.handlers = {}

    def async_register(self, _domain, name, handler, _schema=None):
        self.handlers[name] = handler


def _mode_deps(coordinator):
    return SimpleNamespace(
        domain="thessla_green_modbus",
        normalize_option=lambda value: value,
        iter_target_coordinators=AsyncMock(return_value=[("climate.unit", coordinator)]),
        special_function_map={"boost": 1},
        write_register=AsyncMock(),
        logger=Mock(),
    )


@pytest.mark.asyncio
async def test_special_mode_rejects_duration_when_register_is_missing() -> None:
    coordinator = SimpleNamespace(
        device_client=SimpleNamespace(available_registers={"holding_registers": set()}),
        async_request_refresh=AsyncMock(),
    )
    hass = SimpleNamespace(services=_Services())
    deps = _mode_deps(coordinator)
    handlers_mode.register_mode_services(hass, deps)
    with pytest.raises(ServiceValidationError, match="boost_duration"):
        await hass.services.handlers["set_special_mode"](
            SimpleNamespace(data={"mode": "boost", "duration": 10})
        )
    deps.write_register.assert_not_awaited()


def _schedule_deps(coordinator):
    return SimpleNamespace(
        domain="thessla_green_modbus",
        normalize_option=lambda value: value,
        day_to_device_key={"monday": "mon"},
        iter_target_coordinators=AsyncMock(return_value=[("climate.unit", coordinator)]),
        clamp_airflow_rate=lambda _coordinator, value: value,
        write_register=AsyncMock(),
        logger=Mock(),
    )


@pytest.mark.asyncio
async def test_schedule_rejects_unsupported_end_time_before_device_access() -> None:
    coordinator = SimpleNamespace()
    hass = SimpleNamespace(services=_Services())
    deps = _schedule_deps(coordinator)
    handlers_schedule.register_schedule_services(hass, deps)
    call = SimpleNamespace(data={
        "day": "monday", "period": 1, "season": "summer",
        "start_time": time(8, 0), "end_time": time(9, 0),
        "airflow_rate": 50,
    })
    with pytest.raises(ServiceValidationError, match="end_time cannot be written"):
        await hass.services.handlers["set_airflow_schedule"](call)


@pytest.mark.asyncio
async def test_schedule_rejects_missing_required_registers() -> None:
    coordinator = SimpleNamespace(
        device_client=SimpleNamespace(available_registers={"holding_registers": set()}),
        data={},
    )
    hass = SimpleNamespace(services=_Services())
    deps = _schedule_deps(coordinator)
    handlers_schedule.register_schedule_services(hass, deps)
    call = SimpleNamespace(data={
        "day": "monday", "period": 1, "season": "summer",
        "start_time": time(8, 0), "airflow_rate": 50,
    })
    with pytest.raises(ServiceValidationError, match="required schedule registers"):
        await hass.services.handlers["set_airflow_schedule"](call)
    deps.write_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_targets_public_extractor_handles_async_backend(monkeypatch) -> None:
    async def extractor(_call):
        return {"sensor.one"}

    monkeypatch.setattr("homeassistant.helpers.service.async_extract_entity_ids", extractor)
    assert await targets.extract_entity_ids(object(), object()) == {"sensor.one"}


def test_target_coordinator_registry_lookup_failures_are_none() -> None:
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_get_entry=Mock()),
    )
    with patch.object(targets.er, "async_get", side_effect=KeyError("registry unavailable")):
        assert targets.get_coordinator_from_entity_id(hass, "sensor.one") is None
