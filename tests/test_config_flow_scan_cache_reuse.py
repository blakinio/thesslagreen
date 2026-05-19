"""Tests for reusing config-flow scan cache during initial coordinator setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus._config_flow.entry import (
    _build_config_flow_scan_cache,
    prepare_entry_payload,
)
from custom_components.thessla_green_modbus.coordinator.scan import (
    consume_config_flow_scan_cache,
    prepare_registers_for_setup,
)
from custom_components.thessla_green_modbus.scanner.device_info import DeviceCapabilities

from tests.helpers_coordinator import make_coordinator as _make_coordinator

# ---------------------------------------------------------------------------
# _build_config_flow_scan_cache helpers
# ---------------------------------------------------------------------------


def test_build_config_flow_scan_cache_returns_none_when_no_available():
    assert _build_config_flow_scan_cache({}, DeviceCapabilities) is None


def test_build_config_flow_scan_cache_returns_none_when_available_not_dict():
    assert _build_config_flow_scan_cache({"available_registers": "bad"}, DeviceCapabilities) is None


def test_build_config_flow_scan_cache_returns_none_when_available_empty_dict():
    assert _build_config_flow_scan_cache({"available_registers": {}}, DeviceCapabilities) is None


def test_build_config_flow_scan_cache_serializes_sets_as_sorted_lists():
    scan_result = {
        "available_registers": {
            "input_registers": {"outside_temperature", "supply_temperature"},
            "holding_registers": {"mode"},
        },
        "device_info": {"firmware": "4.8", "model": "AirPack"},
        "capabilities": {},
        "register_count": 3,
    }
    cache = _build_config_flow_scan_cache(scan_result, DeviceCapabilities)
    assert cache is not None
    assert sorted(cache["available_registers"]["input_registers"]) == sorted(
        ["outside_temperature", "supply_temperature"]
    )
    assert cache["available_registers"]["holding_registers"] == ["mode"]
    assert cache["firmware"] == "4.8"
    assert cache["register_count"] == 3
    assert cache["device_info"] == {"firmware": "4.8", "model": "AirPack"}


def test_build_config_flow_scan_cache_skips_non_list_set_values():
    scan_result = {
        "available_registers": {
            "input_registers": ["outside_temperature"],
            "holding_registers": "bad_value",
        },
    }
    cache = _build_config_flow_scan_cache(scan_result, DeviceCapabilities)
    assert cache is not None
    assert "input_registers" in cache["available_registers"]
    assert "holding_registers" not in cache["available_registers"]


def test_build_config_flow_scan_cache_returns_none_when_only_non_iterable_values():
    scan_result = {
        "available_registers": {
            "input_registers": "not_a_list",
            "holding_registers": 42,
        },
    }
    assert _build_config_flow_scan_cache(scan_result, DeviceCapabilities) is None


def test_build_config_flow_scan_cache_handles_caps_dataclass():
    caps = DeviceCapabilities()
    scan_result = {
        "available_registers": {"input_registers": ["mode"]},
        "capabilities": caps,
    }
    cache = _build_config_flow_scan_cache(scan_result, DeviceCapabilities)
    assert cache is not None
    assert isinstance(cache["capabilities"], dict)


# ---------------------------------------------------------------------------
# prepare_entry_payload stores config_flow_scan_cache in options
# ---------------------------------------------------------------------------


def test_prepare_entry_payload_includes_scan_cache_when_registers_present():
    data = {
        "connection_type": "tcp",
        "slave_id": 1,
        "host": "192.168.1.100",
        "port": 502,
    }
    scan_result = {
        "available_registers": {"input_registers": ["outside_temperature"]},
        "device_info": {"firmware": "4.8"},
        "capabilities": {},
    }
    _, options = prepare_entry_payload(data, scan_result, DeviceCapabilities)
    assert "config_flow_scan_cache" in options
    assert options["config_flow_scan_cache"]["available_registers"] == {
        "input_registers": ["outside_temperature"]
    }


def test_prepare_entry_payload_omits_scan_cache_when_no_registers():
    data = {
        "connection_type": "tcp",
        "slave_id": 1,
        "host": "192.168.1.100",
        "port": 502,
    }
    _, options = prepare_entry_payload(data, {}, DeviceCapabilities)
    assert "config_flow_scan_cache" not in options


# ---------------------------------------------------------------------------
# consume_config_flow_scan_cache
# ---------------------------------------------------------------------------


class _MockEntry:
    def __init__(self, options: dict) -> None:
        self.options = dict(options)


def _make_coordinator_with_entry(options: dict) -> MagicMock:
    entry = _MockEntry(options)
    hass = MagicMock()

    def _update_entry(e, *, options: dict) -> None:
        e.options = dict(options)

    hass.config_entries.async_update_entry.side_effect = _update_entry

    coord = MagicMock()
    coord.entry = entry
    coord.hass = hass
    return coord


def test_consume_config_flow_scan_cache_returns_empty_when_no_entry():
    coord = MagicMock()
    coord.entry = None
    assert consume_config_flow_scan_cache(coord) == {}


def test_consume_config_flow_scan_cache_returns_empty_when_key_absent():
    coord = _make_coordinator_with_entry({"device_scan_cache": {}})
    assert consume_config_flow_scan_cache(coord) == {}


def test_consume_config_flow_scan_cache_returns_cache_and_clears_key():
    cache = {"available_registers": {"input_registers": ["mode"]}}
    coord = _make_coordinator_with_entry({"config_flow_scan_cache": cache, "other_key": True})
    result = consume_config_flow_scan_cache(coord)
    assert result == cache
    assert "config_flow_scan_cache" not in coord.entry.options
    assert coord.entry.options.get("other_key") is True


def test_consume_config_flow_scan_cache_returns_empty_for_invalid_type():
    coord = _make_coordinator_with_entry({"config_flow_scan_cache": "bad"})
    assert consume_config_flow_scan_cache(coord) == {}


# ---------------------------------------------------------------------------
# prepare_registers_for_setup — cache reuse and scan skipping
# ---------------------------------------------------------------------------

_VALID_CACHE = {
    "available_registers": {
        "input_registers": ["outside_temperature"],
        "holding_registers": ["mode"],
        "coil_registers": [],
        "discrete_inputs": [],
    },
    "device_info": {"firmware": "4.8"},
    "capabilities": {},
}


@pytest.mark.asyncio
async def test_prepare_registers_uses_config_flow_cache_and_skips_scan(caplog):
    """Coordinator must reuse config-flow scan cache instead of scanning again."""
    coord = _make_coordinator()
    coord.device_client.force_full_register_list = False
    coord.enable_device_scan = True

    coord._consume_config_flow_scan_cache = MagicMock(return_value=_VALID_CACHE)
    coord._apply_scan_cache = MagicMock(return_value=True)
    coord._run_device_scan = AsyncMock()
    coord._load_full_register_list = MagicMock()

    import logging

    with caplog.at_level(logging.INFO):
        await prepare_registers_for_setup(coord)

    coord._apply_scan_cache.assert_called_once_with(_VALID_CACHE)
    coord._run_device_scan.assert_not_called()
    assert "Using config-flow scan cache" in caplog.text


@pytest.mark.asyncio
async def test_prepare_registers_scans_when_no_config_flow_cache(caplog):
    """When config-flow cache is absent, coordinator must scan the device."""
    coord = _make_coordinator()
    coord.device_client.force_full_register_list = False
    coord.enable_device_scan = True

    coord._consume_config_flow_scan_cache = MagicMock(return_value={})
    coord._run_device_scan = AsyncMock()
    coord._load_full_register_list = MagicMock()

    import logging

    with caplog.at_level(logging.INFO):
        await prepare_registers_for_setup(coord)

    coord._run_device_scan.assert_called_once()
    assert "Scanning device for available registers" in caplog.text


@pytest.mark.asyncio
async def test_prepare_registers_scans_when_config_flow_cache_invalid(caplog):
    """Invalid config-flow cache must fall through to device scan."""
    coord = _make_coordinator()
    coord.device_client.force_full_register_list = False
    coord.enable_device_scan = True

    coord._consume_config_flow_scan_cache = MagicMock(return_value={"bad": "data"})
    coord._apply_scan_cache = MagicMock(return_value=False)
    coord._run_device_scan = AsyncMock()
    coord._load_full_register_list = MagicMock()

    await prepare_registers_for_setup(coord)

    coord._run_device_scan.assert_called_once()


@pytest.mark.asyncio
async def test_prepare_registers_normal_restart_no_cache_scans():
    """On HA restart with no config-flow cache, normal scan must occur."""
    coord = _make_coordinator()
    coord.device_client.force_full_register_list = False
    coord.enable_device_scan = True

    coord._consume_config_flow_scan_cache = MagicMock(return_value={})
    coord._run_device_scan = AsyncMock()

    await prepare_registers_for_setup(coord)

    coord._run_device_scan.assert_called_once()


@pytest.mark.asyncio
async def test_prepare_registers_force_full_list_ignores_cache():
    """force_full_register_list must bypass cache and scan entirely."""
    coord = _make_coordinator()
    coord.device_client.force_full_register_list = True
    coord.enable_device_scan = True

    coord._consume_config_flow_scan_cache = MagicMock()
    coord._run_device_scan = AsyncMock()
    coord._load_full_register_list = MagicMock()

    await prepare_registers_for_setup(coord)

    coord._load_full_register_list.assert_called_once()
    coord._consume_config_flow_scan_cache.assert_not_called()
    coord._run_device_scan.assert_not_called()


@pytest.mark.asyncio
async def test_prepare_registers_device_scan_disabled_uses_persistent_cache():
    """When enable_device_scan=False, existing device_scan_cache is used (unchanged path)."""
    coord = _make_coordinator()
    coord.device_client.force_full_register_list = False
    coord.enable_device_scan = False

    coord._get_scan_cache_from_entry = MagicMock(return_value=_VALID_CACHE)
    coord._apply_scan_cache = MagicMock(return_value=True)
    coord._consume_config_flow_scan_cache = MagicMock()
    coord._run_device_scan = AsyncMock()
    coord._load_full_register_list = MagicMock()

    await prepare_registers_for_setup(coord)

    coord._apply_scan_cache.assert_called_once_with(_VALID_CACHE)
    coord._consume_config_flow_scan_cache.assert_not_called()
    coord._run_device_scan.assert_not_called()
