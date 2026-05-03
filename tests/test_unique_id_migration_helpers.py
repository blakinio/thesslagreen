"""Focused tests for unique-id migration helper module."""

from custom_components.thessla_green_modbus.unique_id_migration import (
    device_unique_id_prefix,
    sanitize_identifier,
)


def test_sanitize_identifier_replaces_invalid_chars() -> None:
    assert sanitize_identifier("a::b  c") == "a-b-c"


def test_device_unique_id_prefix_falls_back_to_device() -> None:
    assert device_unique_id_prefix(None, "", None) == "device"
