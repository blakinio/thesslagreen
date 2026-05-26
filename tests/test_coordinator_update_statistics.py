from __future__ import annotations

from tests.helpers_coordinator import make_coordinator as _make_coordinator


def test_clear_register_failure_with_attribute():
    c = _make_coordinator()
    c.device_client._failed_registers = {"outside_temperature", "mode"}
    c.device_client._clear_register_failure("outside_temperature")
    assert (
        "outside_temperature" not in c.device_client._failed_registers
        and "mode" in c.device_client._failed_registers
    )
