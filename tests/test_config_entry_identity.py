"""Tests for stable config-entry identity migration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.thessla_green_modbus.config_entry_identity import (
    migrate_config_entry_unique_id,
)
from custom_components.thessla_green_modbus.const import DOMAIN


def _coordinator(serial_number: object) -> SimpleNamespace:
    return SimpleNamespace(
        device_client=SimpleNamespace(device_info={"serial_number": serial_number})
    )


def test_migrates_legacy_endpoint_unique_id_to_serial() -> None:
    """A confirmed serial replaces a mutable legacy endpoint unique ID."""
    hass = MagicMock()
    hass.config_entries.async_entry_for_domain_unique_id.return_value = None
    entry = SimpleNamespace(entry_id="entry-1", unique_id="192.0.2.1:502:10")

    migrated = migrate_config_entry_unique_id(hass, entry, _coordinator(" SN-123 "))

    assert migrated is True
    hass.config_entries.async_entry_for_domain_unique_id.assert_called_once_with(
        DOMAIN, "serial:sn-123"
    )
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry, unique_id="serial:sn-123"
    )


def test_does_not_migrate_without_usable_serial() -> None:
    """Placeholder or missing device identity must not replace the legacy ID."""
    for serial in (None, "", "Unknown", "0"):
        hass = MagicMock()
        entry = SimpleNamespace(entry_id="entry-1", unique_id="192.0.2.1:502:10")

        migrated = migrate_config_entry_unique_id(hass, entry, _coordinator(serial))

        assert migrated is False
        hass.config_entries.async_entry_for_domain_unique_id.assert_not_called()
        hass.config_entries.async_update_entry.assert_not_called()


def test_does_not_claim_unique_id_owned_by_another_entry() -> None:
    """A stable ID collision must not silently reindex two entries to one identity."""
    hass = MagicMock()
    hass.config_entries.async_entry_for_domain_unique_id.return_value = SimpleNamespace(
        entry_id="entry-2"
    )
    entry = SimpleNamespace(entry_id="entry-1", unique_id="192.0.2.1:502:10")

    migrated = migrate_config_entry_unique_id(hass, entry, _coordinator("SN-123"))

    assert migrated is False
    hass.config_entries.async_update_entry.assert_not_called()


def test_stable_entry_is_left_unchanged() -> None:
    """Already-migrated entries must not generate redundant config-entry updates."""
    hass = MagicMock()
    entry = SimpleNamespace(entry_id="entry-1", unique_id="serial:sn-123")

    migrated = migrate_config_entry_unique_id(hass, entry, _coordinator("SN-123"))

    assert migrated is False
    hass.config_entries.async_entry_for_domain_unique_id.assert_not_called()
    hass.config_entries.async_update_entry.assert_not_called()
