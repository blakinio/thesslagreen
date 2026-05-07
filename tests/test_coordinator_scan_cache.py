from __future__ import annotations

from custom_components.thessla_green_modbus.coordinator.scan import get_scan_cache_from_entry


class _Entry:
    def __init__(self, options):
        self.options = options


def test_get_scan_cache_from_entry_none_returns_empty_dict() -> None:
    assert get_scan_cache_from_entry(None) == {}


def test_get_scan_cache_from_entry_invalid_payload_returns_empty_dict() -> None:
    entry = _Entry({"device_scan_cache": "bad"})
    assert get_scan_cache_from_entry(entry) == {}


def test_get_scan_cache_from_entry_valid_payload_returns_dict() -> None:
    cache = {"available_registers": {"input_registers": ["mode"]}}
    entry = _Entry({"device_scan_cache": cache})
    assert get_scan_cache_from_entry(entry) == cache
