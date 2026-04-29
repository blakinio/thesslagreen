"""Split coordinator coverage tests by behavior area."""

from __future__ import annotations

from unittest.mock import MagicMock

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


def test_get_device_info_model_from_entry():
    """get_device_info uses entry.options when device_info has no model (line 2539)."""
    coord = _make_coordinator()
    from unittest.mock import MagicMock

    entry = MagicMock()
    entry.options = {"model": "Thessla Air 350"}
    entry.data = {}
    coord.entry = entry
    coord.device_scan_result = {}
    coord.device_info = {}
    info = coord.get_device_info()
    assert info["model"] == "Thessla Air 350"

def test_compat_device_info_getattr_key_error():
    """_CompatDeviceInfo.__getattr__ raises AttributeError for missing key (lines 2552-2555)."""
    coord = _make_coordinator()
    info = coord.get_device_info()
    with pytest.raises(AttributeError):
        _ = info.nonexistent_attribute_xyz

