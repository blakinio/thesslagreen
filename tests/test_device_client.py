"""Contract tests for ThesslaGreenDeviceClient.

These tests verify that DeviceClient:
  1. Initialises with the correct default state.
  2. Exposes the public interface expected by the coordinator and by tests.
  3. Properly stores/retrieves device state (connection, registers, stats, …).
  4. Coordinator property proxies correctly delegate to the DeviceClient.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.core.client import ThesslaGreenDeviceClient
from custom_components.thessla_green_modbus.core.models import CoordinatorConfig
from custom_components.thessla_green_modbus.scanner import DeviceCapabilities

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**kwargs) -> CoordinatorConfig:
    defaults = dict(
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test-device",
        timeout=5,
        retry=3,
        scan_interval=30,
    )
    defaults.update(kwargs)
    return CoordinatorConfig(**defaults)


def _make_client(**kwargs) -> ThesslaGreenDeviceClient:
    config = _make_config()
    hass = MagicMock()
    return ThesslaGreenDeviceClient(
        config,
        hass=hass,
        effective_batch=100,
        resolved_connection_mode=None,
        backoff=0.5,
        backoff_jitter=None,
        **kwargs,
    )


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


# ---------------------------------------------------------------------------
# 1. Instantiation
# ---------------------------------------------------------------------------


def test_device_client_instantiation():
    client = _make_client()
    assert client is not None
    assert isinstance(client, ThesslaGreenDeviceClient)


def test_device_client_config_stored():
    config = _make_config(host="10.0.0.1", port=8502, slave_id=5)
    hass = MagicMock()
    client = ThesslaGreenDeviceClient(
        config,
        hass=hass,
        effective_batch=50,
        resolved_connection_mode=None,
        backoff=1.0,
        backoff_jitter=(0.1, 0.5),
    )
    assert client.config is config
    assert client.slave_id == 5
    assert client.timeout == config.timeout
    assert client.retry == config.retry
    assert client.backoff == 1.0
    assert client.backoff_jitter == (0.1, 0.5)
    assert client.effective_batch == 50
    assert client.max_registers_per_request == 50


def test_device_client_initial_connection_state():
    client = _make_client()
    assert client.client is None
    assert client._transport is None
    assert isinstance(client._client_lock, asyncio.Lock)
    assert isinstance(client._write_lock, asyncio.Lock)
    assert client.offline_state is False
    assert client._update_in_progress is False


def test_device_client_initial_device_state():
    client = _make_client()
    assert isinstance(client.capabilities, DeviceCapabilities)
    assert client.device_info == {}
    assert client.device_scan_result is None
    assert client.unknown_registers == {}
    assert client.scanned_registers == {}
    assert client.last_scan is None


def test_device_client_initial_register_maps():
    client = _make_client()
    assert "input_registers" in client._register_maps
    assert "holding_registers" in client._register_maps
    assert "coil_registers" in client._register_maps
    assert "discrete_inputs" in client._register_maps
    assert len(client._register_maps["input_registers"]) > 0

    assert "input_registers" in client._reverse_maps
    assert "input_registers" in client.available_registers
    assert "calculated" in client.available_registers


def test_device_client_initial_statistics():
    client = _make_client()
    stats = client.statistics
    assert stats["successful_reads"] == 0
    assert stats["failed_reads"] == 0
    assert stats["connection_errors"] == 0
    assert stats["timeout_errors"] == 0
    assert stats["last_error"] is None
    assert stats["average_response_time"] == 0.0


def test_device_client_consecutive_failures_initialized():
    client = _make_client()
    assert client._consecutive_failures == 0
    assert client._max_failures == 5


def test_device_client_resolved_connection_mode_stored():
    config = _make_config()
    hass = MagicMock()
    client = ThesslaGreenDeviceClient(
        config,
        hass=hass,
        effective_batch=100,
        resolved_connection_mode="tcp",
        backoff=0.5,
        backoff_jitter=None,
    )
    assert client._resolved_connection_mode == "tcp"


# ---------------------------------------------------------------------------
# 2. Properties
# ---------------------------------------------------------------------------


def test_is_connected_false_with_no_client():
    client = _make_client()
    assert client.is_connected is False


def test_is_connected_true_with_client():
    client = _make_client()
    client.client = MagicMock()
    assert client.is_connected is True


def test_is_connected_uses_transport_when_set():
    client = _make_client()
    transport = MagicMock()
    transport.is_connected.return_value = True
    client._transport = transport
    assert client.is_connected is True
    transport.is_connected.assert_called_once()


def test_is_connected_transport_disconnected():
    client = _make_client()
    transport = MagicMock()
    transport.is_connected.return_value = False
    client._transport = transport
    assert client.is_connected is False


def test_selected_transport_none_by_default():
    client = _make_client()
    assert client.selected_transport is None


def test_selected_transport_reflects_resolved_mode():
    config = _make_config()
    hass = MagicMock()
    client = ThesslaGreenDeviceClient(
        config,
        hass=hass,
        effective_batch=100,
        resolved_connection_mode="tcp_rtu",
        backoff=0.5,
        backoff_jitter=None,
    )
    assert client.selected_transport == "tcp_rtu"


# ---------------------------------------------------------------------------
# 3. Public API methods exist and return expected types
# ---------------------------------------------------------------------------


def test_get_device_info_returns_dict():
    client = _make_client()
    client.device_info = {"model": "GreenUnit", "firmware": "1.0"}
    result = client.get_device_info()
    assert result == {"model": "GreenUnit", "firmware": "1.0"}
    # Must return a copy, not the internal dict
    result["extra"] = "X"
    assert "extra" not in client.device_info


def test_get_capabilities_returns_device_capabilities():
    client = _make_client()
    result = client.get_capabilities()
    assert isinstance(result, DeviceCapabilities)
    assert result is client.capabilities


def test_get_register_map_input_registers():
    client = _make_client()
    reg_map = client.get_register_map("input_registers")
    assert isinstance(reg_map, dict)
    assert len(reg_map) > 0


def test_get_register_map_missing_type():
    client = _make_client()
    result = client.get_register_map("nonexistent_type")
    assert result == {}


def test_compute_register_groups_runs():
    client = _make_client()
    # compute_register_groups iterates available_registers; exclude "calculated"
    # pseudo-key since it has no entry in _register_maps (same as coordinator tests).
    client.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    client.compute_register_groups()


def test_find_register_name_returns_name():
    client = _make_client()
    # Use a known address from the input_registers map
    reg_map = client._register_maps["input_registers"]
    some_name, some_addr = next(iter(reg_map.items()))
    found = client._find_register_name("input_registers", some_addr)
    assert found == some_name


def test_find_register_name_unknown_address():
    client = _make_client()
    result = client._find_register_name("input_registers", 99999)
    assert result is None


def test_mark_and_clear_register_failure():
    client = _make_client()
    reg_name = "fan_speed"
    assert reg_name not in client._failed_registers
    client._mark_registers_failed([reg_name])
    assert reg_name in client._failed_registers
    client._clear_register_failure(reg_name)
    assert reg_name not in client._failed_registers


def test_get_client_method_no_client_returns_callable():
    client = _make_client()
    method = client._get_client_method("read_input_registers")
    assert callable(method)


@pytest.mark.asyncio
async def test_get_client_method_no_client_noop():
    client = _make_client()
    method = client._get_client_method("read_input_registers")
    result = await method(1, 0, count=1)
    assert result is None


def test_get_client_method_uses_transport():
    client = _make_client()
    transport = MagicMock()
    client._transport = transport
    method = client._get_client_method("read_input_registers")
    assert method is transport.read_input_registers


def test_get_client_method_falls_back_to_client():
    client = _make_client()
    mock_client = MagicMock()
    client._transport = None
    client.client = mock_client
    method = client._get_client_method("read_holding_registers")
    assert method is mock_client.read_holding_registers


# ---------------------------------------------------------------------------
# 4. disconnect/close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_disconnect_clears_client():
    client = _make_client()
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    client.client = mock_client
    await client.async_disconnect()
    assert client.client is None


@pytest.mark.asyncio
async def test_async_close_is_alias_for_disconnect():
    client = _make_client()
    client.async_disconnect = AsyncMock()
    await client.async_close()
    client.async_disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. Coordinator property proxies route to DeviceClient
# ---------------------------------------------------------------------------


def test_coordinator_client_proxy():
    coord = _make_coordinator()
    mock_client = MagicMock()
    coord.client = mock_client
    assert coord._device_client.client is mock_client
    assert coord.client is mock_client


def test_coordinator_transport_proxy():
    coord = _make_coordinator()
    mock_transport = MagicMock()
    coord._transport = mock_transport
    assert coord._device_client._transport is mock_transport
    assert coord._transport is mock_transport


def test_coordinator_locks_proxy_to_device_client_locks():
    coord = _make_coordinator()
    assert coord._client_lock is coord._device_client._client_lock
    assert coord._write_lock is coord._device_client._write_lock


def test_coordinator_statistics_proxy():
    coord = _make_coordinator()
    coord.statistics["successful_reads"] = 99
    assert coord._device_client.statistics["successful_reads"] == 99


def test_coordinator_capabilities_proxy():
    coord = _make_coordinator()
    new_caps = DeviceCapabilities()
    coord.capabilities = new_caps
    assert coord._device_client.capabilities is new_caps


def test_coordinator_offline_state_proxy():
    coord = _make_coordinator()
    assert coord.offline_state is False
    coord.offline_state = True
    assert coord._device_client.offline_state is True


def test_coordinator_timeout_proxy():
    coord = _make_coordinator()
    coord.timeout = 99
    assert coord._device_client.timeout == 99


def test_coordinator_retry_proxy():
    coord = _make_coordinator()
    coord.retry = 7
    assert coord._device_client.retry == 7


def test_coordinator_consecutive_failures_proxy():
    coord = _make_coordinator()
    coord._consecutive_failures = 3
    assert coord._device_client._consecutive_failures == 3


def test_coordinator_config_proxy():
    coord = _make_coordinator()
    original_config = coord.config
    assert coord._device_client.config is original_config


def test_coordinator_register_maps_proxy():
    coord = _make_coordinator()
    maps = coord._register_maps
    assert maps is coord._device_client._register_maps
    assert "input_registers" in maps


def test_coordinator_failed_registers_proxy():
    coord = _make_coordinator()
    coord._failed_registers.add("fan_speed")
    assert "fan_speed" in coord._device_client._failed_registers


def test_coordinator_device_name_proxy():
    coord = _make_coordinator()
    coord._device_name = "custom-name"
    assert coord._device_client._device_name == "custom-name"


# ---------------------------------------------------------------------------
# 6. DeviceClient owns state independently of coordinator
# ---------------------------------------------------------------------------


def test_device_client_has_independent_locks():
    client_a = _make_client()
    client_b = _make_client()
    assert client_a._client_lock is not client_b._client_lock
    assert client_a._write_lock is not client_b._write_lock


def test_device_client_hass_stored():
    hass = MagicMock()
    config = _make_config()
    client = ThesslaGreenDeviceClient(
        config,
        hass=hass,
        effective_batch=100,
        resolved_connection_mode=None,
        backoff=0.5,
        backoff_jitter=None,
    )
    assert client.hass is hass
