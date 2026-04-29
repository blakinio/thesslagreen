from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


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
    assert coord.device_info == {"firmware": "4.8"}


def test_apply_scan_cache_non_list_values_filtered():
    coord = _make_coordinator()
    result = coord._apply_scan_cache(
        {"available_registers": {"input_registers": "not_a_list", "holding_registers": ["mode"]}}
    )
    assert result is True
    assert "holding_registers" in coord.available_registers
