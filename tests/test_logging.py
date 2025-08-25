# mypy: ignore-errors
import asyncio
import logging

import pytest

from custom_components.thessla_green_modbus.modbus_helpers import _call_modbus
from homeassistant import core

pytestmark = pytest.mark.asyncio


async def test_call_modbus_logs(caplog):
    """_call_modbus logs batch size, attempts and frames."""

    class Response:
        def __init__(self):
            self.registers = [1, 2]

        def isError(self):
            return False

        def encode(self):
            return b"\x01\x03\x04\x00\x01\x00\x02"

    async def read_holding_registers(address, *, count, unit=None):
        return Response()

    caplog.set_level(logging.DEBUG)
    await _call_modbus(
        read_holding_registers,
        1,
        0,
        count=2,
        attempt=1,
        max_attempts=2,
    )
    assert any(
        "batch=2" in r.message and "attempt 1/2" in r.message
        for r in caplog.records
        if r.levelno == logging.INFO
    )
    assert any("Modbus request" in r.message and "**" in r.message for r in caplog.records)
    assert any("Modbus response" in r.message and "**" in r.message for r in caplog.records)


async def test_read_retries_logged(monkeypatch, caplog):
    """Coordinator logs retries and timeouts."""
    import sys
    import types

    loader_stub = types.SimpleNamespace(
        _load_registers=lambda: ([], {}),
        get_all_registers=lambda: [],
        get_registers_by_function=lambda fn: [],
        registers_sha256=lambda path: "",
        _REGISTERS_PATH="",
    )
    sys.modules[
        "custom_components.thessla_green_modbus.registers.loader"
    ] = loader_stub
    sys.modules[
        "custom_components.thessla_green_modbus.registers"
    ] = types.SimpleNamespace(
        loader=loader_stub,
        get_all_registers=loader_stub.get_all_registers,
        get_registers_by_function=loader_stub.get_registers_by_function,
    )
    ha_util = types.SimpleNamespace(
        network=types.SimpleNamespace(is_host_valid=lambda *a, **k: True)
    )
    sys.modules["homeassistant.util"] = ha_util
    sys.modules["homeassistant.util.network"] = ha_util.network
    from custom_components.thessla_green_modbus.coordinator import (
        ThesslaGreenModbusCoordinator,
    )

    class DummyClient:
        def __init__(self):
            self.connected = True
            self.calls = 0

        async def read_input_registers(self, address, *, count, unit=None):
            self.calls += 1
            if self.calls == 1:
                raise asyncio.TimeoutError
            return type(
                "Resp",
                (),
                {
                    "registers": [1] * count,
                    "isError": lambda self: False,
                    "encode": lambda self: b"\x01\x04\x02\x00\x01",
                },
            )()

    hass = core.HomeAssistant()
    coord = ThesslaGreenModbusCoordinator(hass, "host", 1, 1, "name", scan_interval=1)
    coord.client = DummyClient()
    coord.retry = 2
    coord.available_registers["input_registers"] = {"reg0", "reg1"}
    coord._register_maps["input_registers"] = {"reg0": 0, "reg1": 1}
    coord._reverse_maps["input_registers"] = {0: "reg0", 1: "reg1"}
    coord._register_groups["input_registers"] = [(0, 2)]
    coord._process_register_value = lambda name, value: value

    caplog.set_level(logging.DEBUG)
    data = await coord._read_input_registers_optimized()
    assert data == {"reg0": 1, "reg1": 1}
    assert any(
        "Timeout reading input registers" in r.message
        for r in caplog.records
        if r.levelno == logging.WARNING
    )
    assert any("attempt 1/2" in r.message for r in caplog.records if r.levelno == logging.WARNING)
    assert sum(1 for r in caplog.records if r.levelno == logging.INFO and "batch=2" in r.message) == 2


async def test_write_retries_logged(monkeypatch, caplog):
    """Write path logs retries and handles timeouts."""
    import sys
    import types

    loader_stub = types.SimpleNamespace(
        _load_registers=lambda: ([], {}),
        get_all_registers=lambda: [],
        get_registers_by_function=lambda fn: [],
        registers_sha256=lambda path: "",
        _REGISTERS_PATH="",
    )
    sys.modules[
        "custom_components.thessla_green_modbus.registers.loader"
    ] = loader_stub
    sys.modules[
        "custom_components.thessla_green_modbus.registers"
    ] = types.SimpleNamespace(
        loader=loader_stub,
        get_all_registers=loader_stub.get_all_registers,
        get_registers_by_function=loader_stub.get_registers_by_function,
    )
    ha_util = types.SimpleNamespace(
        network=types.SimpleNamespace(is_host_valid=lambda *a, **k: True)
    )
    sys.modules["homeassistant.util"] = ha_util
    sys.modules["homeassistant.util.network"] = ha_util.network
    from custom_components.thessla_green_modbus.coordinator import (
        ThesslaGreenModbusCoordinator,
    )

    class DummyClient:
        def __init__(self):
            self.connected = True
            self.calls = 0

        async def write_register(self, *, address, value, unit=None):
            self.calls += 1
            if self.calls == 1:
                raise asyncio.TimeoutError
            return type(
                "Resp",
                (),
                {"isError": lambda self: False, "encode": lambda self: b"\x01\x06\x00\x00\x00\x01"},
            )()

    class Def:
        address = 0
        function = 3
        length = 1

        def encode(self, val):
            return val

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        lambda name: Def(),
    )

    hass = core.HomeAssistant()
    coord = ThesslaGreenModbusCoordinator(hass, "host", 1, 1, "name", scan_interval=1)
    coord.client = DummyClient()
    coord.retry = 2
    monkeypatch.setattr(coord, "_ensure_connection", lambda: asyncio.sleep(0))

    caplog.set_level(logging.INFO)
    result = await coord.async_write_register("reg", 1, refresh=False)
    assert result is True
    assert any(
        "Writing register reg timed out" in r.message and "attempt 1/2" in r.message
        for r in caplog.records
        if r.levelno == logging.WARNING
    )
    assert any(
        "Successfully wrote 1 to register reg" in r.message for r in caplog.records
    )
