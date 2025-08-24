"""Tests for JSON register loader."""

import json
import sys
import types
from pathlib import Path

import pytest

# Stub the integration package to avoid executing its heavy __init__
pkg = types.ModuleType("custom_components.thessla_green_modbus")
pkg.__path__ = [
    str(Path(__file__).resolve().parents[1] / "custom_components" / "thessla_green_modbus")
]
sys.modules.setdefault("custom_components.thessla_green_modbus", pkg)

# Provide a minimal const module required by modbus_helpers
const_module = types.ModuleType("custom_components.thessla_green_modbus.const")
const_module.MAX_BATCH_REGISTERS = 64
sys.modules.setdefault("custom_components.thessla_green_modbus.const", const_module)

from custom_components.thessla_green_modbus.registers.loader import (
    RegisterDef,
    get_registers_by_function,
)


def test_example_register_mapping() -> None:
    """Verify example registers map to expected addresses."""

    def addr(fn: str, name: str) -> int:
        regs = get_registers_by_function(fn)
        reg = next(r for r in regs if r.name == name)
        return reg.address

    assert addr("01", "duct_water_heater_pump") == 5
    assert addr("02", "expansion") == 0
    assert addr("03", "mode") == 4097
    assert addr("04", "outside_temperature") == 16


def test_enum_multiplier_resolution_handling() -> None:
    """Ensure optional register metadata is preserved."""

    holding_regs = get_registers_by_function("03")

    special_mode = next(r for r in holding_regs if r.name == "special_mode")
    assert special_mode.enum and special_mode.enum["boost"] == 1

    required = next(r for r in holding_regs if r.name == "required_temperature")
    assert required.multiplier == 0.5
    assert required.resolution == 0.5
    assert required.decode(45) == 22.5


def test_multi_register_metadata() -> None:
    """Registers spanning multiple words expose length and type info."""

    holding_regs = get_registers_by_function("03")
    device_name = next(r for r in holding_regs if r.name == "device_name")
    assert device_name.length == 8
    assert device_name.extra["type"] == "string"

    lock = next(r for r in holding_regs if r.name == "lock_pass")
    assert lock.length == 2
    assert lock.extra["type"] == "uint32"
    assert lock.extra["endianness"] == "little"

    input_regs = get_registers_by_function("04")
    serial = next(r for r in input_regs if r.name == "serial_number")
    assert serial.length == 6
    assert serial.extra["encoding"] == "ascii"


def test_decode_multi_register_string() -> None:
    """Multi-register strings decode without applying scaling."""
    reg = RegisterDef(
        function="holding",
        address=0,
        name="device_name",
        access="ro",
        length=3,
        extra={"type": "string"},
        multiplier=2,
        resolution=1,
    )
    raw = [0x4142, 0x4344, 0x4500]  # "ABCDE"
    assert reg.decode(raw) == "ABCDE"


def test_decode_multi_register_number_scaled_once() -> None:
    """Numeric multi-register values apply multiplier/resolution exactly once."""
    reg = RegisterDef(
        function="holding",
        address=0,
        name="counter",
        access="ro",
        length=2,
        extra={"type": "int32"},
        multiplier=10,
        resolution=1,
    )
    raw = [0x0000, 0x0001]
    assert reg.decode(raw) == 10


def test_decode_bitmask_ignores_scaling() -> None:
    """Bitmask registers return labels without scaling the raw value."""
    reg = RegisterDef(
        function="holding",
        address=0,
        name="flags",
        access="ro",
        enum={1: "A", 2: "B", 4: "C"},
        extra={"bitmask": True},
        multiplier=2,
        resolution=1,
    )
    assert reg.decode(5) == ["A", "C"]


def test_function_aliases() -> None:
    """Aliases with spaces/underscores should resolve to correct functions."""
    aliases = {
        "coil_registers": "01",
        "discrete_inputs": "02",
        "holding_registers": "03",
        "input_registers": "04",
        "input registers": "04",
    }
    for alias, code in aliases.items():
        alias_regs = get_registers_by_function(alias)
        code_regs = get_registers_by_function(code)
        assert {r.address for r in alias_regs} == {r.address for r in code_regs}


def test_register_cache_invalidation(tmp_path, monkeypatch) -> None:
    """Ensure register file caching and invalidation behave correctly."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    # Use a temporary copy of the register file so we can modify it
    path = tmp_path / "regs.json"
    path.write_text(loader._REGISTERS_PATH.read_text())
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    read_calls = 0
    hash_calls = 0
    real_read_text = Path.read_text
    real_compute_hash = loader._compute_file_hash

    def spy_read(self, *args, **kwargs):
        nonlocal read_calls
        read_calls += 1
        text = real_read_text(self, *args, **kwargs)
        json.loads(text)
        return text

    def spy_hash(file_path, mtime):
        nonlocal hash_calls
        hash_calls += 1
        return real_compute_hash(file_path, mtime)

    # Spy on read_text and hash computation to count disk accesses
    monkeypatch.setattr(Path, "read_text", spy_read)
    monkeypatch.setattr(loader, "_compute_file_hash", spy_hash)

    loader.clear_cache()

    # Initial load populates cache
    hash_before = loader.get_registers_hash()
    loader.get_all_registers()
    loader.get_all_registers()

    # The file and hash should only be computed once thanks to caching
    assert read_calls == 1
    assert hash_calls == 1

    # Modify the file to invalidate caches
    path.write_text(real_read_text(path) + "\n")

    loader.get_all_registers()
    hash_after = loader.get_registers_hash()

    # After modification both read and hash are recomputed
    assert read_calls == 2
    assert hash_calls == 2
    assert hash_before != hash_after


def test_compute_file_hash_uses_cache(tmp_path, monkeypatch) -> None:
    """_compute_file_hash should avoid re-reading unchanged files."""

    import custom_components.thessla_green_modbus.registers.loader as loader
    import os

    path = tmp_path / "regs.json"
    path.write_text("data")
    mtime = path.stat().st_mtime

    read_calls = 0
    real_read_bytes = Path.read_bytes

    def spy_read_bytes(self):
        nonlocal read_calls
        read_calls += 1
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", spy_read_bytes)

    digest1 = loader._compute_file_hash(path, mtime)
    digest2 = loader._compute_file_hash(path, mtime)

    assert digest1 == digest2
    assert read_calls == 1

    path.write_text("data2")
    os.utime(path, (mtime + 1, mtime + 1))
    mtime2 = path.stat().st_mtime
    loader._compute_file_hash(path, mtime2)

    assert read_calls == 2

def test_registers_reload_on_file_change(tmp_path, monkeypatch) -> None:
    """Changing the register JSON file triggers a reload."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    path = tmp_path / "regs.json"
    path.write_text(loader._REGISTERS_PATH.read_text())
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    loader.clear_cache()

    original = loader.get_all_registers()
    assert not any(r.name == "cache_test_marker" for r in original)

    data = json.loads(path.read_text())
    data["registers"][0]["name"] = "cache_test_marker"
    path.write_text(json.dumps(data))

    updated = loader.get_all_registers()
    assert any(r.name == "cache_test_marker" for r in updated)


def test_clear_cache_resets_file_hash(tmp_path, monkeypatch) -> None:
    """clear_cache should reset the cached file hash."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    path = tmp_path / "regs.json"
    path.write_text(loader._REGISTERS_PATH.read_text())
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    hash_calls = 0
    real_compute_hash = loader._compute_file_hash

    def spy_hash(file_path, mtime):
        nonlocal hash_calls
        hash_calls += 1
        return real_compute_hash(file_path, mtime)

    monkeypatch.setattr(loader, "_compute_file_hash", spy_hash)

    loader.clear_cache()

    # First load computes hash once
    loader.get_all_registers()
    loader.get_all_registers()
    assert hash_calls == 1

    # Clearing the cache forces a re-computation
    loader.clear_cache()
    loader.get_all_registers()
    assert hash_calls == 2


@pytest.mark.parametrize(
    "registers",
    [
        [
            {"function": "01", "address_dec": 1, "name": "dup1", "access": "R"},
            {"function": "01", "address_dec": 1, "name": "dup2", "access": "R"},
        ],
        [
            {"function": "01", "address_dec": 1, "name": "dup", "access": "R"},
            {"function": "02", "address_dec": 2, "name": "dup", "access": "R"},
        ],
    ],
)
def test_duplicate_registers_raise_error(tmp_path, monkeypatch, registers) -> None:
    """Duplicate names or addresses should raise an error."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    path = tmp_path / "regs.json"
    path.write_text(json.dumps({"registers": registers}))
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    with pytest.raises(ValueError):
        loader._load_registers_from_file(path, mtime=0, file_hash="")


@pytest.mark.parametrize(
    "register",
    [
        {
            "function": "03",
            "address_dec": 1,
            "address_hex": "0x2",
            "name": "bad_addr",
            "access": "R",
        },
        {
            "function": "03",
            "address_dec": 0,
            "address_hex": "0x0",
            "name": "bad_len",
            "access": "R",
            "length": 1,
            "extra": {"type": "uint32"},
        },
        {
            "function": "01",
            "address_dec": 0,
            "address_hex": "0x0",
            "name": "bad_access",
            "access": "R/W",
        },
        {
            "function": "03",
            "address_dec": 0,
            "address_hex": "0x0",
            "name": "bad_bits",
            "access": "R",
            "bits": ["a"],
        },
        {
            "function": "03",
            "address_dec": 0,
            "address_hex": "0x0",
            "name": "bad_string_len",
            "access": "R",
            "length": 0,
            "extra": {"type": "string"},
        },
        {
            "function": "03",
            "address_dec": 0,
            "address_hex": "0x0",
            "name": "too_many_bits",
            "access": "R",
            "extra": {"bitmask": 0b11},
            "bits": ["a", "b", "c"],
        },
    ],
)
def test_invalid_registers_rejected(tmp_path, monkeypatch, register) -> None:
    """Registers violating schema constraints should raise an error."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    path = tmp_path / "regs.json"
    path.write_text(json.dumps({"registers": [register]}))
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    with pytest.raises(ValueError):
        loader._load_registers_from_file(path, mtime=0, file_hash="")


def test_bits_within_bitmask_width(tmp_path, monkeypatch) -> None:
    """Registers with bits not exceeding bitmask width should load."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    reg = {
        "function": "03",
        "address_dec": 0,
        "address_hex": "0x0",
        "name": "good_bits",
        "access": "R",
        "extra": {"bitmask": 0b11},
        "bits": ["a", "b"],
    }
    path = tmp_path / "regs.json"
    path.write_text(json.dumps({"registers": [reg]}))
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    loader._load_registers_from_file(path, file_hash="", mtime=0)


def test_missing_register_file_raises_runtime_error(tmp_path) -> None:
    """Missing register definition file should raise RuntimeError."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    path = tmp_path / "regs.json"
    with pytest.raises(RuntimeError) as exc:
        loader._load_registers_from_file(path, mtime=0, file_hash="")
    assert str(path) in str(exc.value)


def test_invalid_register_file_raises_runtime_error(tmp_path) -> None:
    """Invalid register definition file should raise RuntimeError."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    path = tmp_path / "regs.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        loader._load_registers_from_file(path, mtime=0, file_hash="")
    assert str(path) in str(exc.value)


def test_register_file_sorted() -> None:
    """Ensure register JSON is sorted and loader preserves ordering."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    data = json.loads(loader._REGISTERS_PATH.read_text(encoding="utf-8"))
    regs = data["registers"]
    keys = [(str(r["function"]), int(r["address_dec"])) for r in regs]
    assert keys == sorted(keys)


def test_special_modes_invalid_json(monkeypatch) -> None:
    """Loader falls back to empty special mode enum on invalid file."""

    import importlib
    from pathlib import Path

    import custom_components.thessla_green_modbus.registers.loader as loader

    special_path = loader._SPECIAL_MODES_PATH
    real_read_text = Path.read_text

    def bad_read(self, *args, **kwargs):  # pragma: no cover - simple stub
        if self == special_path:
            return "{"
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read)

    loader = importlib.reload(loader)
    assert loader._SPECIAL_MODES_ENUM == {}  # nosec B101

    monkeypatch.setattr(Path, "read_text", real_read_text)
    importlib.reload(loader)


def test_get_all_registers_sorted(monkeypatch, tmp_path) -> None:
    """get_all_registers should order registers by function then address."""

    import custom_components.thessla_green_modbus.registers.loader as loader

    regs = [
        {
            "function": "03",
            "address_dec": 2,
            "address_hex": "0x0002",
            "name": "reg_c",
            "access": "R",
        },
        {
            "function": "01",
            "address_dec": 1,
            "address_hex": "0x0001",
            "name": "reg_a",
            "access": "R",
        },
        {
            "function": "03",
            "address_dec": 1,
            "address_hex": "0x0001",
            "name": "reg_b",
            "access": "R",
        },
    ]

    path = tmp_path / "regs.json"
    path.write_text(json.dumps({"registers": regs}))
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    loader.clear_cache()
    ordered = loader.get_all_registers()
    keys = [(r.function, r.address) for r in ordered]
    assert keys == sorted(keys)
