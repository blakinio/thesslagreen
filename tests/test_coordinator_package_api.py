"""Split coordinator coverage tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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


def test_coordinator_init_super_type_error_fallback():
    """Coordinator init should propagate TypeError from base __init__."""
    from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator

    def patched_init(self, *args, **kwargs):
        raise TypeError("unexpected keyword argument")

    with patch.object(ThesslaGreenModbusCoordinator.__bases__[0], "__init__", patched_init):
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            ThesslaGreenModbusCoordinator.from_params(
                hass=MagicMock(), host="localhost", port=502, slave_id=1
            )


def test_coordinator_init_entry_bad_max_registers_per_request():
    """TypeError/ValueError in entry.options max_registers → MAX_REGS_PER_REQUEST (lines 371-372)."""
    from custom_components.thessla_green_modbus.const import CONF_MAX_REGISTERS_PER_REQUEST

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {}
    entry.options = {CONF_MAX_REGISTERS_PER_REQUEST: "not_a_number"}
    hass = MagicMock()
    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=hass, host="localhost", port=502, slave_id=1, entry=entry
    )
    from custom_components.thessla_green_modbus.const import MAX_BATCH_REGISTERS

    assert coord.effective_batch == MAX_BATCH_REGISTERS


def test_coordinator_init_max_registers_less_than_1():
    """effective_batch < 1 is raised to 1 (lines 375-376)."""
    coord = _make_coordinator(max_registers_per_request=0)
    assert coord.effective_batch == 1


def test_coordinator_init_entry_bad_capabilities():
    """Invalid capabilities dict in entry.data is caught (lines 397-399)."""
    from custom_components.thessla_green_modbus.scanner import DeviceCapabilities

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"capabilities": {"_invalid_kwarg": "bad"}}
    entry.options = {}
    hass = MagicMock()

    original_init = DeviceCapabilities.__init__
    call_count = [0]

    def patched_init(self, **kwargs):
        call_count[0] += 1
        if kwargs:  # Called with kwargs from entry.data → raise TypeError
            raise TypeError("bad kwarg")
        original_init(self)

    with patch.object(DeviceCapabilities, "__init__", patched_init):
        coord = ThesslaGreenModbusCoordinator.from_params(
            hass=hass, host="localhost", port=502, slave_id=1, entry=entry
        )
    # Should not raise; capabilities falls back to default (no capabilities set)
    assert isinstance(coord.capabilities, DeviceCapabilities)


# ---------------------------------------------------------------------------
# _read_coils_transport / _read_discrete_inputs_transport (lines 680-704)
# ---------------------------------------------------------------------------


def test_coordinator_init_jitter_list_with_bad_values():
    """backoff_jitter=[None, None] triggers except (TypeError, ValueError) → jitter_value=None."""
    coord = _make_coordinator(backoff_jitter=[None, None])
    assert coord.backoff_jitter is None


def test_coordinator_init_jitter_else_none():
    """backoff_jitter=None hits else branch → jitter_value = None."""
    coord = _make_coordinator(backoff_jitter=None)
    assert coord.backoff_jitter is None


def test_coordinator_init_jitter_else_default():
    """backoff_jitter={} hits else branch (not None/'') → jitter_value = DEFAULT_BACKOFF_JITTER."""
    from custom_components.thessla_green_modbus.const import DEFAULT_BACKOFF_JITTER

    coord = _make_coordinator(backoff_jitter={})
    assert coord.backoff_jitter == DEFAULT_BACKOFF_JITTER


# ---------------------------------------------------------------------------
# Pass 15 — Sekcja B: _read_with_retry inner paths (lines 543-544, 563-565, 572-576)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_setup_force_full_register_list():
    """force_full_register_list=True skips scan and loads full list (lines 874-877)."""
    coord = _make_coordinator(force_full_register_list=True)
    coord._ensure_connection = AsyncMock()
    coord._test_connection = AsyncMock()

    result = await coord.async_setup()
    assert result is True
    # All registers should be loaded
    assert len(coord.available_registers["input_registers"]) > 0


@pytest.mark.asyncio
async def test_async_setup_scan_disabled_no_entry():
    """scan disabled with no entry falls back to full register list (lines 720-728)."""
    coord = _make_coordinator()
    coord.enable_device_scan = False
    coord.force_full_register_list = False
    coord.entry = None
    coord._ensure_connection = AsyncMock()
    coord._test_connection = AsyncMock()

    result = await coord.async_setup()
    assert result is True


@pytest.mark.asyncio
async def test_async_setup_rtu_connection_type():
    """async_setup uses serial_port endpoint for RTU connection type (line 709)."""
    from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU

    coord = _make_coordinator(connection_type=CONNECTION_TYPE_RTU, serial_port="/dev/ttyUSB0")
    coord.enable_device_scan = False
    coord.force_full_register_list = False
    coord.entry = None
    coord._ensure_connection = AsyncMock()
    coord._test_connection = AsyncMock()

    result = await coord.async_setup()
    assert result is True


# ---------------------------------------------------------------------------
# _load_full_register_list with skip_missing_registers (lines 944-946)
# ---------------------------------------------------------------------------


def test_load_full_register_list_skips_missing():
    """skip_missing_registers=True removes known-missing registers (lines 944-946)."""
    coord = _make_coordinator(skip_missing_registers=True)
    coord._load_full_register_list()
    # Should have loaded registers without raising
    assert isinstance(coord.available_registers, dict)


# ---------------------------------------------------------------------------
# _clear_register_failure (line 1085)
# ---------------------------------------------------------------------------


def test_normalise_available_registers_invalid_type():
    """Non-list/set value skipped via continue (line 968)."""
    coord = _make_coordinator()
    result = coord._normalise_available_registers({"input_registers": 42})
    assert "input_registers" not in result


# ---------------------------------------------------------------------------
# Pass 16 — B3: _compute_register_groups exception branches
# ---------------------------------------------------------------------------


def test_build_tcp_transport_tcp_rtu_mode():
    """TCP_RTU mode returns RawRtuOverTcpTransport."""
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP_RTU
    from custom_components.thessla_green_modbus.modbus_transport import RawRtuOverTcpTransport

    coord = _make_coordinator()
    result = coord._build_tcp_transport(CONNECTION_MODE_TCP_RTU)
    assert isinstance(result, RawRtuOverTcpTransport)


def test_build_tcp_transport_tcp_mode():
    """TCP mode returns TcpModbusTransport."""
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP
    from custom_components.thessla_green_modbus.modbus_transport import TcpModbusTransport

    coord = _make_coordinator()
    result = coord._build_tcp_transport(CONNECTION_MODE_TCP)
    assert isinstance(result, TcpModbusTransport)


# ---------------------------------------------------------------------------
# Pass 16 — B6: async_write_register uncovered branches
# ---------------------------------------------------------------------------


