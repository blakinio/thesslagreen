"""Split coordinator coverage tests by behavior area."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


def test_compute_register_groups_safe_scan():
    """safe_scan=True produces per-register (addr, length) tuples (lines 1026-1047)."""
    coord = _make_coordinator(safe_scan=True)
    coord.available_registers = {
        "input_registers": {"outside_temperature"},
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    coord._compute_register_groups()
    groups = coord._register_groups.get("input_registers", [])
    assert isinstance(groups, list)
    assert len(groups) >= 1
    addr, length = groups[0]
    assert isinstance(addr, int)
    assert isinstance(length, int)

def test_compute_register_groups_safe_scan_unknown_register():
    """Unknown register in safe_scan mode is skipped gracefully."""
    coord = _make_coordinator(safe_scan=True)
    coord.available_registers = {
        "input_registers": {"__unknown_reg_xyz__"},
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    coord._compute_register_groups()
    # No exception should be raised; groups for input_registers is empty since reg not in map
    groups = coord._register_groups.get("input_registers", [])
    assert isinstance(groups, list)


# ---------------------------------------------------------------------------
# Group I — _test_connection exception handlers (lines 1125-1141)
# ---------------------------------------------------------------------------

def test_apply_scan_cache_normalise_exception():
    """TypeError in _normalise_available_registers returns False (lines 985-986)."""
    coord = _make_coordinator()
    with patch.object(
        coord,
        "_normalise_available_registers",
        side_effect=TypeError("bad"),
    ):
        result = coord._apply_scan_cache({"available_registers": {"input_registers": ["mode"]}})
    assert result is False

def test_apply_scan_cache_invalid_capabilities():
    """Invalid capabilities dict in cache is caught silently (lines 994-995)."""
    from custom_components.thessla_green_modbus.scanner import DeviceCapabilities

    coord = _make_coordinator()
    with patch.object(DeviceCapabilities, "__init__", side_effect=TypeError("bad")):
        result = coord._apply_scan_cache(
            {
                "available_registers": {"input_registers": ["mode"]},
                "capabilities": {"bad_key": 1},
            }
        )
    assert result is True  # overall still succeeds


# ---------------------------------------------------------------------------
# Pass 15 — Sekcja A: __init__ jitter else branch (lines 326-329)
# ---------------------------------------------------------------------------

def test_compute_register_groups_safe_scan_key_error():
    """KeyError in get_register_definition with safe_scan=True (lines 1035-1037)."""
    coord = _make_coordinator(safe_scan=True)
    coord.available_registers = {"holding_registers": {"mode"}}
    coord._register_maps = {"holding_registers": {"mode": 100}}
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        side_effect=KeyError("mode"),
    ):
        coord._compute_register_groups()
    assert "holding_registers" in coord._register_groups

def test_compute_register_groups_non_safe_addr_none():
    """addr=None in register map hits continue (line 1053)."""
    coord = _make_coordinator(safe_scan=False)
    coord.available_registers = {"holding_registers": {"unknown_reg"}}
    coord._register_maps = {"holding_registers": {}}  # addr will be None
    coord._compute_register_groups()
    assert coord._register_groups.get("holding_registers", []) == []

def test_compute_register_groups_non_safe_key_error():
    """KeyError in get_register_definition with safe_scan=False (lines 1057-1059)."""
    coord = _make_coordinator(safe_scan=False)
    coord.available_registers = {"holding_registers": {"mode"}}
    coord._register_maps = {"holding_registers": {"mode": 100}}
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        side_effect=KeyError("mode"),
    ):
        coord._compute_register_groups()
    assert "holding_registers" in coord._register_groups


# ---------------------------------------------------------------------------
# Pass 16 — B4: _test_connection paths (lines 1111, 1122)
# ---------------------------------------------------------------------------

