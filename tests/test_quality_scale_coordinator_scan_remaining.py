# mypy: ignore-errors
"""Exercise remaining coordinator scan cache and setup branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_MODE_AUTO
from custom_components.thessla_green_modbus.coordinator import scan


def _coordinator():
    client = SimpleNamespace(
        _register_maps={
            "input_registers": {"i": 1, "version_patch": 2},
            "holding_registers": {"h": 3, "exp_version": 4},
            "coil_registers": {"c": 5},
            "discrete_inputs": {"d": 6},
        },
        available_registers={},
        device_info={},
        capabilities=SimpleNamespace(as_dict=lambda: {"basic_control": True}),
        device_scan_result=None,
        config=SimpleNamespace(connection_mode="tcp"),
        _resolved_connection_mode=None,
        skip_missing_registers=False,
        force_full_register_list=False,
    )
    return SimpleNamespace(
        device_client=client,
        entry=None,
        hass=SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=Mock())),
    )


def test_scan_cache_access_and_full_list_known_missing() -> None:
    assert scan.get_scan_cache_from_entry(None) == {}
    assert (
        scan.get_scan_cache_from_entry(SimpleNamespace(options={"device_scan_cache": []})) == {}
    )
    assert scan.get_scan_cache_from_entry(
        SimpleNamespace(options={"device_scan_cache": {"x": 1}})
    ) == {"x": 1}

    coordinator = _coordinator()
    coordinator.device_client.skip_missing_registers = True
    scan.load_full_register_list(coordinator)
    assert "i" in coordinator.device_client.available_registers["input_registers"]
    assert "version_patch" not in coordinator.device_client.available_registers["input_registers"]
    assert "exp_version" not in coordinator.device_client.available_registers["holding_registers"]


def test_firmware_known_missing_classification() -> None:
    assert scan.firmware_lacks_known_missing(None) is False
    assert scan.firmware_lacks_known_missing("3.11") is True
    assert scan.firmware_lacks_known_missing("4.0") is False


def test_apply_scan_cache_validation_normalization_capability_and_identity_paths() -> None:
    coordinator = _coordinator()
    assert scan.apply_scan_cache(coordinator, {}) is False

    cache = {"available_registers": {"input_registers": ["i"]}}
    coordinator._normalise_available_registers = Mock(side_effect=ValueError("bad"))
    assert scan.apply_scan_cache(coordinator, cache) is False

    coordinator._normalise_available_registers = Mock(
        return_value={
            "input_registers": {"i", "version_patch"},
            "holding_registers": {"exp_version"},
        }
    )
    coordinator.device_client.config.connection_mode = CONNECTION_MODE_AUTO
    cache = {
        "available_registers": {
            "input_registers": ["i"],
            "holding_registers": ["exp_version"],
        },
        "device_info": {"serial_number": "ABC", "firmware": "3.11"},
        "capabilities": {"not_a_real_field": True},
        "resolved_connection_mode": "tcp_rtu",
    }
    assert scan.apply_scan_cache(coordinator, cache) is True
    assert coordinator.device_client._resolved_connection_mode == "tcp_rtu"
    assert "serial_number" in coordinator.device_client.available_registers["input_registers"]
    assert "version_patch" not in coordinator.device_client.available_registers["input_registers"]
    assert "exp_version" not in coordinator.device_client.available_registers["holding_registers"]
    assert coordinator.device_client.device_scan_result is cache


def test_apply_scan_cache_uses_shared_normalizer_when_no_hook() -> None:
    coordinator = _coordinator()
    with patch.object(
        scan,
        "normalise_available_registers",
        return_value={"input_registers": {"i"}},
    ) as normalise:
        assert scan.apply_scan_cache(
            coordinator,
            {"available_registers": {"input_registers": ["i"]}, "device_info": []},
        ) is True
    normalise.assert_called_once()
    assert coordinator.device_client.device_info == {}


def test_store_and_consume_scan_cache_paths() -> None:
    coordinator = _coordinator()
    scan.store_scan_cache(coordinator)
    coordinator.hass.config_entries.async_update_entry.assert_not_called()

    coordinator.entry = SimpleNamespace(entry_id="entry", options={"keep": 1})
    coordinator.device_client.available_registers = {"input_registers": {"b", "a"}}
    coordinator.device_client.device_info = {"firmware": "4.0"}
    coordinator.device_client._resolved_connection_mode = "tcp"
    scan.store_scan_cache(coordinator)
    call = coordinator.hass.config_entries.async_update_entry.call_args
    assert call.kwargs["options"]["device_scan_cache"]["available_registers"] == {
        "input_registers": ["a", "b"]
    }

    coordinator.entry = None
    assert scan.consume_config_flow_scan_cache(coordinator) == {}
    coordinator.entry = SimpleNamespace(options={"config_flow_scan_cache": []})
    assert scan.consume_config_flow_scan_cache(coordinator) == {}
    coordinator.entry = SimpleNamespace(
        options={"keep": 1, "config_flow_scan_cache": {"x": 1}}
    )
    coordinator.hass.config_entries.async_update_entry.reset_mock()
    assert scan.consume_config_flow_scan_cache(coordinator) == {"x": 1}
    assert coordinator.hass.config_entries.async_update_entry.call_args.kwargs["options"] == {
        "keep": 1
    }


@pytest.mark.asyncio
async def test_prepare_registers_for_setup_all_selection_paths() -> None:
    coordinator = _coordinator()
    coordinator._load_full_register_list = Mock()
    coordinator._get_scan_cache_from_entry = Mock(return_value={})
    coordinator._apply_scan_cache = Mock(return_value=False)
    coordinator._consume_config_flow_scan_cache = Mock(return_value={})
    coordinator._run_device_scan = AsyncMock()
    coordinator.enable_device_scan = True

    coordinator.device_client.force_full_register_list = True
    await scan.prepare_registers_for_setup(coordinator)
    coordinator._load_full_register_list.assert_called_once()

    coordinator.device_client.force_full_register_list = False
    coordinator._load_full_register_list.reset_mock()
    coordinator.enable_device_scan = False
    coordinator._get_scan_cache_from_entry.return_value = {"cached": True}
    coordinator._apply_scan_cache.return_value = True
    await scan.prepare_registers_for_setup(coordinator)
    coordinator._load_full_register_list.assert_not_called()

    coordinator._apply_scan_cache.return_value = False
    await scan.prepare_registers_for_setup(coordinator)
    coordinator._load_full_register_list.assert_called_once()

    coordinator.enable_device_scan = True
    coordinator._consume_config_flow_scan_cache.return_value = {"flow": True}
    coordinator._apply_scan_cache.return_value = True
    coordinator._run_device_scan.reset_mock()
    await scan.prepare_registers_for_setup(coordinator)
    coordinator._run_device_scan.assert_not_awaited()

    coordinator._apply_scan_cache.return_value = False
    await scan.prepare_registers_for_setup(coordinator)
    coordinator._run_device_scan.assert_awaited_once()
