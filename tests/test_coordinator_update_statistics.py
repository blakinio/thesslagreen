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


def test_clear_register_failure_with_attribute():
    c = _make_coordinator()
    c._failed_registers = {"outside_temperature", "mode"}
    c._clear_register_failure("outside_temperature")
    assert "outside_temperature" not in c._failed_registers and "mode" in c._failed_registers
