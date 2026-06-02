"""Direct unit tests for coordinator/state.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components.thessla_green_modbus.const import (
    DEFAULT_BAUD_RATE,
    DEFAULT_PARITY,
    DEFAULT_SERIAL_PORT,
    MAX_REGS_PER_REQUEST,
)
from custom_components.thessla_green_modbus.coordinator.state import (
    _initialize_connection_state,
    _initialize_device_state,
    _initialize_runtime_flags,
    _initialize_scan_state,
    initialize_runtime_state,
    normalize_serial_settings,
    resolve_effective_batch,
)

# ---------------------------------------------------------------------------
# normalize_serial_settings
# ---------------------------------------------------------------------------


def test_normalize_serial_normal_values():
    port, baud, parity, stop = normalize_serial_settings("/dev/ttyUSB0", 9600, "n", 1)
    assert port == "/dev/ttyUSB0"
    assert baud == 9600
    assert parity == "n"
    assert stop == 1


def test_normalize_serial_empty_port_uses_default():
    port, _, _, _ = normalize_serial_settings("", 9600, "n", 1)
    assert port == DEFAULT_SERIAL_PORT


def test_normalize_serial_bad_baud_uses_default():
    _, baud, _, _ = normalize_serial_settings("/dev/tty", "not_a_number", "n", 1)
    assert baud == DEFAULT_BAUD_RATE


def test_normalize_serial_unknown_parity_uses_default():
    _, _, parity, _ = normalize_serial_settings("/dev/tty", 9600, "z", 1)
    assert parity == DEFAULT_PARITY


def test_normalize_serial_stop_bits_two():
    _, _, _, stop = normalize_serial_settings("/dev/tty", 9600, "n", 2)
    assert stop == 2


# ---------------------------------------------------------------------------
# resolve_effective_batch
# ---------------------------------------------------------------------------


def test_resolve_effective_batch_no_entry_uses_param():
    result = resolve_effective_batch(None, 50)
    assert result == 50


def test_resolve_effective_batch_clamped_to_max():
    result = resolve_effective_batch(None, MAX_REGS_PER_REQUEST + 1000)
    assert result == MAX_REGS_PER_REQUEST


def test_resolve_effective_batch_minimum_is_one():
    result = resolve_effective_batch(None, 0)
    assert result == 1


def test_resolve_effective_batch_from_entry_options():
    entry = MagicMock()
    entry.options = {"max_registers_per_request": 30}
    result = resolve_effective_batch(entry, 125)
    assert result == 30


def test_resolve_effective_batch_bad_entry_option_uses_max():
    entry = MagicMock()
    entry.options = {"max_registers_per_request": "bad"}
    result = resolve_effective_batch(entry, 125)
    assert result == MAX_REGS_PER_REQUEST


# ---------------------------------------------------------------------------
# _initialize_runtime_flags
# ---------------------------------------------------------------------------


def _make_coord():
    coord = MagicMock()
    coord.device_client = SimpleNamespace(offline_state=None)
    return coord


def test_initialize_runtime_flags_no_entry_uses_defaults():
    coord = _make_coord()
    _initialize_runtime_flags(coord, entry=None)
    from custom_components.thessla_green_modbus.const import DEFAULT_ENABLE_DEVICE_SCAN

    assert coord.enable_device_scan == DEFAULT_ENABLE_DEVICE_SCAN
    assert coord._reauth_scheduled is False
    assert coord._shutting_down is False
    assert coord._stop_listener is None
    assert coord.device_client.offline_state is False


def test_initialize_runtime_flags_reads_option_from_entry():
    coord = _make_coord()
    entry = MagicMock()
    entry.options = {"enable_device_scan": True}
    _initialize_runtime_flags(coord, entry=entry)
    assert coord.enable_device_scan is True


# ---------------------------------------------------------------------------
# _initialize_connection_state
# ---------------------------------------------------------------------------


def test_initialize_connection_state_resets_client():
    coord = _make_coord()
    coord.device_client.client = MagicMock()
    coord.device_client._transport = MagicMock()
    _initialize_connection_state(coord)
    assert coord.device_client.client is None
    assert coord.device_client._transport is None
    assert coord.device_client._update_in_progress is False


def test_initialize_connection_state_creates_locks():
    import asyncio

    coord = _make_coord()
    _initialize_connection_state(coord)
    assert isinstance(coord.device_client._client_lock, asyncio.Lock)
    assert isinstance(coord.device_client._write_lock, asyncio.Lock)


# ---------------------------------------------------------------------------
# _initialize_device_state
# ---------------------------------------------------------------------------


def test_initialize_device_state_resets_device_info():
    coord = _make_coord()
    _initialize_device_state(coord, entry=None)
    assert coord.device_client.device_info == {}


def test_initialize_device_state_available_registers_has_all_types():
    coord = _make_coord()
    _initialize_device_state(coord, entry=None)
    ar = coord.device_client.available_registers
    assert "input_registers" in ar
    assert "holding_registers" in ar
    assert "coil_registers" in ar
    assert "discrete_inputs" in ar
    assert "calculated" in ar


def test_initialize_device_state_calculated_prepopulated():
    coord = _make_coord()
    _initialize_device_state(coord, entry=None)
    assert "estimated_power" in coord.device_client.available_registers["calculated"]
    assert "total_energy" in coord.device_client.available_registers["calculated"]


def test_initialize_device_state_loads_capabilities_from_entry():
    from custom_components.thessla_green_modbus.scanner import DeviceCapabilities

    coord = _make_coord()
    entry = MagicMock()
    entry.data = {"capabilities": {"constant_flow": True}}
    _initialize_device_state(coord, entry=entry)
    assert isinstance(coord.device_client.capabilities, DeviceCapabilities)


def test_initialize_device_state_bad_capabilities_falls_back():
    from custom_components.thessla_green_modbus.scanner import DeviceCapabilities

    coord = _make_coord()
    entry = MagicMock()
    entry.data = {"capabilities": {"_nonexistent_kwarg": True}}
    _initialize_device_state(coord, entry=entry)
    assert isinstance(coord.device_client.capabilities, DeviceCapabilities)


# ---------------------------------------------------------------------------
# _initialize_scan_state
# ---------------------------------------------------------------------------


def test_initialize_scan_state_zeroes_statistics():
    coord = _make_coord()
    with patch("custom_components.thessla_green_modbus.coordinator.state.utcnow"):
        _initialize_scan_state(coord)
    stats = coord.device_client.statistics
    assert stats["successful_reads"] == 0
    assert stats["failed_reads"] == 0
    assert stats["total_registers_read"] == 0
    assert stats["last_error"] is None


def test_initialize_scan_state_resets_scan_result():
    coord = _make_coord()
    coord.device_client.device_scan_result = {"something": True}
    with patch("custom_components.thessla_green_modbus.coordinator.state.utcnow"):
        _initialize_scan_state(coord)
    assert coord.device_client.device_scan_result is None


def test_initialize_scan_state_resets_energy():
    coord = _make_coord()
    with patch("custom_components.thessla_green_modbus.coordinator.state.utcnow"):
        _initialize_scan_state(coord)
    assert coord.device_client._total_energy == 0.0


# ---------------------------------------------------------------------------
# initialize_runtime_state (integration)
# ---------------------------------------------------------------------------


def test_initialize_runtime_state_calls_all_sub_functions():
    coord = _make_coord()
    with patch("custom_components.thessla_green_modbus.coordinator.state.utcnow"):
        initialize_runtime_state(coord, entry=None)
    assert coord._reauth_scheduled is False
    assert coord.device_client.client is None
    assert coord.device_client.device_info == {}
    assert coord.device_client.statistics["successful_reads"] == 0
