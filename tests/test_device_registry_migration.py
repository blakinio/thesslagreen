"""Device-registry migration regressions."""

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.device_registry_migration import (
    migrate_device_identifier,
)
from homeassistant.helpers import device_registry as dr


def _coordinator(*, host: str = "192.168.1.20", serial: str | None = "AP4-42"):
    device_info = {"serial_number": serial} if serial is not None else {}
    return SimpleNamespace(
        device_client=SimpleNamespace(
            config=SimpleNamespace(host=host, port=8899, slave_id=10),
            device_info=device_info,
        ),
        entry=SimpleNamespace(entry_id="entry-123"),
    )


def test_migrates_legacy_endpoint_identifier_to_serial() -> None:
    """Existing endpoint-keyed devices gain only the stable integration identifier."""
    legacy = (DOMAIN, "192.168.1.20:8899:10")
    stable = (DOMAIN, "serial:ap4-42")
    device = SimpleNamespace(
        id="device-1",
        config_entry_id="entry-123",
        identifiers={legacy, ("other_domain", "keep-me")},
    )
    registry = MagicMock(spec=["async_get_device", "async_update_device"])
    registry.async_get_device.side_effect = lambda identifiers=None, connections=None: (
        device if identifiers == {legacy} else None
    )

    with patch(
        "custom_components.thessla_green_modbus.device_registry_migration.dr.async_get",
        return_value=registry,
    ):
        migrate_device_identifier(
            SimpleNamespace(),
            SimpleNamespace(entry_id="entry-123"),
            _coordinator(),
        )

    registry.async_update_device.assert_called_once_with(
        "device-1",
        new_identifiers={("other_domain", "keep-me"), stable},
    )


def test_migrates_no_serial_device_to_config_entry_identity() -> None:
    """No-serial devices use config-entry identity rather than mutable endpoint data."""
    legacy = (DOMAIN, "192.168.1.20:8899:10")
    stable = (DOMAIN, "entry:entry-123")
    device = SimpleNamespace(
        id="device-1",
        config_entries={"entry-123"},
        identifiers={legacy},
    )
    registry = MagicMock(spec=["async_get_device", "async_update_device"])
    registry.async_get_device.side_effect = lambda identifiers=None, connections=None: (
        device if identifiers == {legacy} else None
    )

    with patch(
        "custom_components.thessla_green_modbus.device_registry_migration.dr.async_get",
        return_value=registry,
    ):
        migrate_device_identifier(
            SimpleNamespace(),
            SimpleNamespace(entry_id="entry-123"),
            _coordinator(serial=None),
        )

    registry.async_update_device.assert_called_once_with("device-1", new_identifiers={stable})


def test_stable_device_requires_no_registry_update() -> None:
    """An already migrated device remains untouched."""
    stable = (DOMAIN, "serial:ap4-42")
    device = SimpleNamespace(
        id="device-1",
        config_entry_id="entry-123",
        identifiers={stable},
    )
    registry = MagicMock(spec=["async_get_device", "async_update_device"])
    registry.async_get_device.side_effect = lambda identifiers=None, connections=None: (
        device if identifiers == {stable} else None
    )

    with patch(
        "custom_components.thessla_green_modbus.device_registry_migration.dr.async_get",
        return_value=registry,
    ):
        migrate_device_identifier(
            SimpleNamespace(),
            SimpleNamespace(entry_id="entry-123"),
            _coordinator(),
        )

    registry.async_update_device.assert_not_called()


def _entry_scoped_registry(
    devices: dict[tuple[tuple[str, str], str], SimpleNamespace],
) -> MagicMock:
    registry = MagicMock(
        spec=["async_get_device", "async_get_device_by_identifier", "async_update_device"]
    )
    registry.async_get_device_by_identifier.side_effect = lambda identifier, entry_id: devices.get(
        (identifier, entry_id)
    )
    return registry


def test_uses_entry_scoped_lookup_when_available() -> None:
    """Newer HA registries are queried per config entry, not via deprecated lookup."""
    legacy = (DOMAIN, "192.168.1.20:8899:10")
    stable = (DOMAIN, "serial:ap4-42")
    device = SimpleNamespace(id="device-1", identifiers={legacy})
    registry = _entry_scoped_registry({(legacy, "entry-123"): device})

    with patch(
        "custom_components.thessla_green_modbus.device_registry_migration.dr.async_get",
        return_value=registry,
    ):
        migrate_device_identifier(
            SimpleNamespace(),
            SimpleNamespace(entry_id="entry-123"),
            _coordinator(),
        )

    registry.async_get_device.assert_not_called()
    registry.async_get_device_by_identifier.assert_any_call(stable, "entry-123")
    registry.async_get_device_by_identifier.assert_any_call(legacy, "entry-123")
    registry.async_update_device.assert_called_once_with("device-1", new_identifiers={stable})


def test_entry_scoped_lookup_ignores_other_entries() -> None:
    """A device owned by another config entry is never rewritten."""
    legacy = (DOMAIN, "192.168.1.20:8899:10")
    device = SimpleNamespace(id="device-1", identifiers={legacy})
    registry = _entry_scoped_registry({(legacy, "other-entry"): device})

    with patch(
        "custom_components.thessla_green_modbus.device_registry_migration.dr.async_get",
        return_value=registry,
    ):
        migrate_device_identifier(
            SimpleNamespace(),
            SimpleNamespace(entry_id="entry-123"),
            _coordinator(),
        )

    registry.async_get_device.assert_not_called()
    registry.async_update_device.assert_not_called()


def test_installed_registry_matches_supported_lookup_api() -> None:
    """The installed HA provides the entry-scoped lookup or the legacy fallback."""
    get_by_identifier = getattr(dr.DeviceRegistry, "async_get_device_by_identifier", None)
    if get_by_identifier is None:
        assert callable(getattr(dr.DeviceRegistry, "async_get_device", None))
        return
    params = list(inspect.signature(get_by_identifier).parameters)
    assert params[:3] == ["self", "identifier", "config_entry_id"]
