# mypy: ignore-errors
"""Exercise remaining integration setup and migration compatibility branches."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus import _setup
from custom_components.thessla_green_modbus.const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymodbus.exceptions import ConnectionException


def test_scan_interval_and_platform_cache_helpers() -> None:
    assert _setup._scan_interval_seconds(timedelta(seconds=12)) == 12
    assert _setup._scan_interval_seconds(7) == 7
    _setup._get_platforms.cache_clear()
    platforms = _setup._get_platforms(("sensor", "fan"))
    assert [str(platform) for platform in platforms]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("connection_type", "connection_mode", "expected_type"),
    [
        ("invalid", "tcp", CONNECTION_TYPE_TCP),
        (CONNECTION_TYPE_RTU, "tcp", CONNECTION_TYPE_RTU),
        (CONNECTION_TYPE_TCP, CONNECTION_MODE_TCP_RTU, CONNECTION_TYPE_TCP),
        (CONNECTION_TYPE_TCP, CONNECTION_MODE_AUTO, CONNECTION_TYPE_TCP),
    ],
)
async def test_create_coordinator_transport_label_branches(
    connection_type, connection_mode, expected_type
) -> None:
    config = SimpleNamespace(
        connection_type=connection_type,
        connection_mode=connection_mode,
        port=502,
        host="host",
        serial_port="ttyS0",
        name="unit",
        slave_id=10,
        scan_interval=timedelta(seconds=30),
    )
    entry = SimpleNamespace(options={_setup.CONF_CONNECTION_MODE: connection_mode})
    sentinel = object()
    with (
        patch(
            "custom_components.thessla_green_modbus.core.models.CoordinatorConfig.from_entry",
            return_value=config,
        ),
        patch.object(_setup, "resolve_connection_settings", return_value=(expected_type, connection_mode)),
        patch.object(_setup, "_apply_log_level"),
        patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator",
            return_value=sentinel,
        ) as coordinator_cls,
    ):
        assert await _setup.async_create_coordinator(object(), entry) is sentinel
    assert config.connection_type == expected_type
    coordinator_cls.assert_called_once()


@pytest.mark.asyncio
async def test_start_coordinator_sync_setup_and_invalid_auth_reauth() -> None:
    coordinator = SimpleNamespace(
        async_setup=Mock(return_value=None),
        async_config_entry_first_refresh=AsyncMock(),
    )
    entry = SimpleNamespace(async_start_reauth=AsyncMock())
    assert await _setup.async_start_coordinator(object(), entry, coordinator) is True

    coordinator.async_setup = Mock(side_effect=ConnectionException("auth"))
    with patch.object(_setup, "is_invalid_auth_error", return_value=True):
        assert await _setup.async_start_coordinator(object(), entry, coordinator) is False
    entry.async_start_reauth.assert_awaited()


@pytest.mark.asyncio
async def test_start_coordinator_setup_and_refresh_error_translation() -> None:
    entry = SimpleNamespace(async_start_reauth=AsyncMock())
    coordinator = SimpleNamespace(
        async_setup=Mock(side_effect=RuntimeError("setup boom")),
        async_config_entry_first_refresh=AsyncMock(),
    )
    with pytest.raises(ConfigEntryNotReady, match="Unable to connect"):
        await _setup.async_start_coordinator(object(), entry, coordinator)

    coordinator.async_setup = Mock(return_value=None)
    coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=UpdateFailed("refresh boom"))
    with pytest.raises(ConfigEntryNotReady, match="Unable to fetch"):
        await _setup.async_start_coordinator(object(), entry, coordinator)

    coordinator.async_setup = Mock(side_effect=ConfigEntryNotReady("already"))
    with pytest.raises(ConfigEntryNotReady, match="already"):
        await _setup.async_start_coordinator(object(), entry, coordinator)


@pytest.mark.asyncio
async def test_start_coordinator_cancellation_propagates() -> None:
    entry = SimpleNamespace(async_start_reauth=AsyncMock())
    coordinator = SimpleNamespace(
        async_setup=Mock(side_effect=asyncio.CancelledError()),
        async_config_entry_first_refresh=AsyncMock(),
    )
    with pytest.raises(asyncio.CancelledError):
        await _setup.async_start_coordinator(object(), entry, coordinator)

    coordinator.async_setup = Mock(return_value=None)
    coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await _setup.async_start_coordinator(object(), entry, coordinator)


@pytest.mark.asyncio
async def test_setup_mappings_delegates_both_initializers() -> None:
    with (
        patch.object(_setup, "async_setup_options", new=AsyncMock()) as options,
        patch.object(_setup, "async_setup_entity_mappings", new=AsyncMock()) as mappings,
    ):
        await _setup.async_setup_mappings("hass")
    options.assert_awaited_once_with("hass")
    mappings.assert_awaited_once_with("hass")


@pytest.mark.asyncio
async def test_unique_id_migration_registry_and_metadata_error_paths() -> None:
    from homeassistant.helpers import entity_registry as er

    entry = SimpleNamespace(entry_id="entry")
    coordinator = SimpleNamespace(
        device_client=SimpleNamespace(
            device_info={},
            config=SimpleNamespace(host="host", port=502, slave_id=10),
            slave_id=10,
        )
    )

    with patch.object(er, "async_get", side_effect=KeyError("registry")):
        await _setup.async_migrate_entity_unique_ids(object(), entry, coordinator)

    registry = SimpleNamespace(async_update_entity=Mock())
    entity = SimpleNamespace(entity_id="sensor.test", unique_id="old")
    with (
        patch.object(er, "async_get", return_value=registry),
        patch.object(er, "async_entries_for_config_entry", return_value=[entity]),
        patch.object(_setup, "migrate_unique_id", return_value="new"),
    ):
        await _setup.async_migrate_entity_unique_ids(object(), entry, coordinator)
    registry.async_update_entity.assert_called_once_with("sensor.test", new_unique_id="new")

    registry.async_update_entity = Mock(side_effect=ValueError("update"))
    with (
        patch.object(er, "async_get", return_value=registry),
        patch.object(er, "async_entries_for_config_entry", return_value=[entity]),
        patch.object(_setup, "migrate_unique_id", return_value="new"),
    ):
        await _setup.async_migrate_entity_unique_ids(object(), entry, coordinator)

    with (
        patch.object(er, "async_get", return_value=registry),
        patch.object(er, "async_entries_for_config_entry", side_effect=TypeError("entries")),
    ):
        await _setup.async_migrate_entity_unique_ids(object(), entry, coordinator)


@pytest.mark.asyncio
async def test_setup_platforms_preload_errors_sync_forward_and_cancellation() -> None:
    _setup._get_platforms.cache_clear()
    config_entries = SimpleNamespace(async_forward_entry_setups=Mock(return_value=None))
    hass = SimpleNamespace(
        async_add_executor_job=AsyncMock(side_effect=[ImportError("missing"), RuntimeError("boom")]),
        config_entries=config_entries,
    )
    await _setup.async_setup_platforms(hass, object(), ["sensor", "fan"])
    config_entries.async_forward_entry_setups.assert_called_once()

    hass = SimpleNamespace(
        async_add_executor_job=AsyncMock(return_value=None),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=Mock(side_effect=asyncio.CancelledError())
        ),
    )
    with pytest.raises(asyncio.CancelledError):
        await _setup.async_setup_platforms(hass, object(), ["sensor"])
