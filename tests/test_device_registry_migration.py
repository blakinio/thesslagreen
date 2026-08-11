"""Device-registry migration regressions."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.device_registry_migration import (
    async_migrate_device_identifier,
)


def _coordinator(*, host: str = "192.168.1.20", serial: str | None = "AP4-42"):
    device_info = {"serial_number": serial} if serial is not None else {}
    return SimpleNamespace(
        device_client=SimpleNamespace(
            config=SimpleNamespace(host=host, port=8899, slave_id=10),
            device_info=device_info,
        ),
        entry=SimpleNamespace(entry_id="entry-123"),
    )


@pytest.mark.asyncio
async def test_migrates_legacy_endpoint_identifier_to_serial() -> None:
    """Existing endpoint-keyed devices gain only the stable integration identifier."""
    legacy = (DOMAIN, "192.168.1.20:8899:10")
    stable = (DOMAIN, "serial:ap4-42")
    device = SimpleNamespace(
        id="device-1",
        config_entry_id="entry-123",
        identifiers={legacy, ("other_domain", "keep-me")},
    )
    registry = MagicMock()
    registry.async_get_device.side_effect = lambda identifiers=None, connections=None: (
        device if identifiers == {legacy} else None
    )

    with patch(
        "custom_components.thessla_green_modbus.device_registry_migration.dr.async_get",
        return_value=registry,
    ):
        await async_migrate_device_identifier(
            SimpleNamespace(),
            SimpleNamespace(entry_id="entry-123"),
            _coordinator(),
        )

    registry.async_update_device.assert_called_once_with(
        "device-1",
        new_identifiers={("other_domain", "keep-me"), stable},
    )


@pytest.mark.asyncio
async def test_migrates_no_serial_device_to_config_entry_identity() -> None:
    """No-serial devices use config-entry identity rather than mutable endpoint data."""
    legacy = (DOMAIN, "192.168.1.20:8899:10")
    stable = (DOMAIN, "entry:entry-123")
    device = SimpleNamespace(
        id="device-1",
        config_entries={"entry-123"},
        identifiers={legacy},
    )
    registry = MagicMock()
    registry.async_get_device.side_effect = lambda identifiers=None, connections=None: (
        device if identifiers == {legacy} else None
    )

    with patch(
        "custom_components.thessla_green_modbus.device_registry_migration.dr.async_get",
        return_value=registry,
    ):
        await async_migrate_device_identifier(
            SimpleNamespace(),
            SimpleNamespace(entry_id="entry-123"),
            _coordinator(serial=None),
        )

    registry.async_update_device.assert_called_once_with(
        "device-1", new_identifiers={stable}
    )


@pytest.mark.asyncio
async def test_stable_device_requires_no_registry_update() -> None:
    """An already migrated device remains untouched."""
    stable = (DOMAIN, "serial:ap4-42")
    device = SimpleNamespace(
        id="device-1",
        config_entry_id="entry-123",
        identifiers={stable},
    )
    registry = MagicMock()
    registry.async_get_device.side_effect = lambda identifiers=None, connections=None: (
        device if identifiers == {stable} else None
    )

    with patch(
        "custom_components.thessla_green_modbus.device_registry_migration.dr.async_get",
        return_value=registry,
    ):
        await async_migrate_device_identifier(
            SimpleNamespace(),
            SimpleNamespace(entry_id="entry-123"),
            _coordinator(),
        )

    registry.async_update_device.assert_not_called()
