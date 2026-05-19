from __future__ import annotations

from tests.helpers_coordinator import make_coordinator as _make_coordinator


def test_apply_scan_cache_no_available_returns_false():
    assert _make_coordinator()._apply_scan_cache({}) is False


def test_apply_scan_cache_non_dict_available_returns_false():
    assert _make_coordinator()._apply_scan_cache({"available_registers": "bad"}) is False


def test_apply_scan_cache_valid_data_applies():
    coord = _make_coordinator()
    result = coord._apply_scan_cache(
        {
            "available_registers": {
                "input_registers": ["outside_temperature"],
                "holding_registers": ["mode"],
            },
            "device_info": {"firmware": "4.8"},
            "capabilities": {},
        }
    )
    assert result is True
    assert coord.device_client.device_info == {"firmware": "4.8"}


def test_apply_scan_cache_non_list_values_filtered():
    coord = _make_coordinator()
    result = coord._apply_scan_cache(
        {"available_registers": {"input_registers": "not_a_list", "holding_registers": ["mode"]}}
    )
    assert result is True
    assert "holding_registers" in coord.device_client.available_registers
