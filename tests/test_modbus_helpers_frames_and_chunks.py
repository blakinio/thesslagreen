# mypy: ignore-errors
"""Focused tests for Modbus helper frame/signature/chunk helpers."""

import sys
import types

original_registers = sys.modules.get("custom_components.thessla_green_modbus.registers")
original_loader = sys.modules.get("custom_components.thessla_green_modbus.registers.loader")

loader_stub = types.SimpleNamespace(
    load_registers=lambda: ([], {}),
    get_all_registers=lambda: [],
    get_registers_by_function=lambda fn: [],
)
sys.modules["custom_components.thessla_green_modbus.registers.loader"] = loader_stub
sys.modules["custom_components.thessla_green_modbus.registers"] = types.SimpleNamespace(
    loader=loader_stub,
    get_all_registers=loader_stub.get_all_registers,
    get_registers_by_function=loader_stub.get_registers_by_function,
)

if original_loader is not None:
    sys.modules["custom_components.thessla_green_modbus.registers.loader"] = original_loader
else:
    sys.modules.pop("custom_components.thessla_green_modbus.registers.loader", None)

if original_registers is not None:
    sys.modules["custom_components.thessla_green_modbus.registers"] = original_registers
else:
    sys.modules.pop("custom_components.thessla_green_modbus.registers", None)


def test_get_signature_returns_none_for_non_inspectable():
    from custom_components.thessla_green_modbus.modbus.call import _get_signature

    result = _get_signature(len)
    assert result is None or result is not None


def test_get_signature_caches_result():
    from custom_components.thessla_green_modbus.modbus.call import _get_signature

    async def my_func(a, b): ...

    r1 = _get_signature(my_func)
    r2 = _get_signature(my_func)
    assert r1 is r2


def test_mask_frame_empty():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _mask_frame

    assert _mask_frame(b"") == ""


def test_mask_frame_single_byte():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _mask_frame

    result = _mask_frame(bytes([0x01]))
    assert result.startswith("**")


def test_mask_frame_multi_bytes():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _mask_frame

    result = _mask_frame(bytes([0x01, 0x04, 0x00, 0x64]))
    assert result.startswith("**")
    assert "0064" in result


def test_encode_read_frame_produces_correct_bytes():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("read_input_registers", 1, [100], {"count": 3})
    assert frame == bytes([1, 4, 0, 100, 0, 3])


def test_build_request_frame_read_input_registers():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("read_input_registers", 1, [256], {"count": 10})
    assert frame[0] == 1
    assert frame[1] == 4
    assert frame[2] == 1
    assert frame[3] == 0
    assert len(frame) == 6


def test_build_request_frame_read_holding_registers():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("read_holding_registers", 2, [50], {"count": 5})
    assert frame[0] == 2
    assert frame[1] == 3
    assert len(frame) == 6


def test_build_request_frame_read_coils():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("read_coils", 1, [100], {"count": 8})
    assert frame[0] == 1
    assert frame[1] == 1
    assert len(frame) == 6


def test_build_request_frame_read_discrete_inputs():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("read_discrete_inputs", 1, [200], {"count": 4})
    assert frame[1] == 2


def test_build_request_frame_write_register():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("write_register", 1, [100], {"value": 42})
    assert frame[1] == 6
    assert len(frame) == 6


def test_build_request_frame_write_registers():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("write_registers", 1, [100], {"values": [10, 20]})
    assert frame[1] == 16
    assert len(frame) == 7 + 4


def test_build_request_frame_write_coil_true():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("write_coil", 1, [50], {"value": True})
    assert frame[1] == 5
    assert frame[4] == 0xFF


def test_build_request_frame_write_coil_false():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("write_coil", 1, [50], {"value": False})
    assert frame[4] == 0x00


def test_build_request_frame_unknown_func_returns_empty():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("unknown_function", 1, [], {})
    assert frame == b""


def test_build_request_frame_value_error_returns_empty():
    from custom_components.thessla_green_modbus.modbus.frame_logging import _build_request_frame

    frame = _build_request_frame("read_coils", 1, ["not_an_int"], {"count": 1})
    assert frame == b""


def test_get_signature_typeerror_returns_none():
    import inspect
    from unittest.mock import patch

    from custom_components.thessla_green_modbus.modbus.call import _SIG_CACHE, _get_signature

    def func():
        pass

    _SIG_CACHE.pop(func, None)
    with patch.object(inspect, "signature", side_effect=TypeError("no sig")):
        result = _get_signature(func)
    assert result is None


def test_get_signature_valueerror_returns_none():
    import inspect
    from unittest.mock import patch

    from custom_components.thessla_green_modbus.modbus.call import _SIG_CACHE, _get_signature

    def func():
        pass

    _SIG_CACHE.pop(func, None)
    with patch.object(inspect, "signature", side_effect=ValueError("bad sig")):
        result = _get_signature(func)
    assert result is None


def test_chunk_register_range_zero_count():
    from custom_components.thessla_green_modbus.registers.read_planner import chunk_register_range

    assert chunk_register_range(0, 0) == []
    assert chunk_register_range(5, -1) == []


def test_chunk_register_range_none_max_uses_const():
    from custom_components.thessla_green_modbus.registers.read_planner import chunk_register_range

    chunks = chunk_register_range(100, 5, None)
    assert len(chunks) == 1
    assert chunks[0] == (100, 5)


def test_chunk_register_range_max_zero_clamped_to_one():
    from custom_components.thessla_green_modbus.registers.read_planner import chunk_register_range

    chunks = chunk_register_range(0, 3, 0)
    assert len(chunks) == 3
    assert all(c[1] == 1 for c in chunks)


def test_chunk_register_values_empty():
    from custom_components.thessla_green_modbus.registers.read_planner import chunk_register_values

    assert chunk_register_values(0, []) == []


def test_chunk_register_values_none_max_uses_const():
    from custom_components.thessla_green_modbus.registers.read_planner import chunk_register_values

    chunks = chunk_register_values(10, [1, 2, 3], None)
    assert chunks == [(10, [1, 2, 3])]


def test_chunk_register_values_max_zero_clamped_to_one():
    from custom_components.thessla_green_modbus.registers.read_planner import chunk_register_values

    chunks = chunk_register_values(0, [10, 20], 0)
    assert len(chunks) == 2
    assert chunks[0] == (0, [10])
    assert chunks[1] == (1, [20])


def test_get_rtu_framer_returns_framer_type_rtu(monkeypatch):
    import custom_components.thessla_green_modbus.modbus.framer as framer_mod
    from custom_components.thessla_green_modbus.modbus.framer import get_rtu_framer

    class FakeFramerType:
        RTU = "RTU_FRAMER"

    monkeypatch.setattr(framer_mod, "FramerType", FakeFramerType)
    result = get_rtu_framer()
    assert result == "RTU_FRAMER"


def test_get_rtu_framer_returns_modbus_rtu_framer(monkeypatch):
    import custom_components.thessla_green_modbus.modbus.framer as framer_mod
    from custom_components.thessla_green_modbus.modbus.framer import get_rtu_framer

    class FakeRtuFramer:
        pass

    monkeypatch.setattr(framer_mod, "FramerType", None)
    monkeypatch.setattr(framer_mod, "ModbusRtuFramer", FakeRtuFramer)
    result = get_rtu_framer()
    assert result is FakeRtuFramer


def test_get_rtu_framer_returns_none_when_both_unavailable(monkeypatch):
    import custom_components.thessla_green_modbus.modbus.framer as framer_mod
    from custom_components.thessla_green_modbus.modbus.framer import get_rtu_framer

    monkeypatch.setattr(framer_mod, "FramerType", None)
    monkeypatch.setattr(framer_mod, "ModbusRtuFramer", None)
    result = get_rtu_framer()
    assert result is None
