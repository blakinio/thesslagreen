"""Tests for JSON register loader."""

# ruff: noqa: E402

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
const_module.MAX_BATCH_REGISTERS = 16
sys.modules.setdefault("custom_components.thessla_green_modbus.const", const_module)

from custom_components.thessla_green_modbus.registers.loader import (
    _REGISTERS_PATH,
    _SPECIAL_MODES_PATH,
    RegisterDef,
    _load_registers_from_file,
    clear_cache,
    get_all_registers,
    get_registers_by_function,
    load_registers,
    registers_sha256,
)


def _add_desc(reg: dict) -> dict:
    return {
        **reg,
        "description": reg.get("description", "desc"),
        "description_en": reg.get("description_en", "desc"),
    }


def _write(path: Path, regs: list[dict]) -> None:
    path.write_text(json.dumps({"registers": [_add_desc(r) for r in regs]}))


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


def test_default_multiplier_resolution(tmp_path) -> None:
    """Omitted multiplier/resolution fields default to 1."""

    reg = {
        "function": "03",
        "address_dec": 0,
        "name": "noscale",
        "access": "R",
    }

    path = tmp_path / "regs.json"
    _write(path, [reg])

    loaded = _load_registers_from_file(path, mtime=0, file_hash="")[0]
    assert loaded.multiplier == 1
    assert loaded.resolution == 1


def test_multi_register_metadata() -> None:
    """Registers spanning multiple words expose length and type info."""

    holding_regs = get_registers_by_function("03")
    device_name = next(r for r in holding_regs if r.name == "device_name")
    assert device_name.length == 8
    assert device_name.extra["type"] == "string"

    lock = next(r for r in holding_regs if r.name == "lock_pass")
    assert lock.length == 2
    assert lock.extra["type"] == "u32"
    assert lock.extra["endianness"] == "little"

    input_regs = get_registers_by_function("04")
    serial = next(r for r in input_regs if r.name == "serial_number")
    assert serial.length == 6
    assert serial.extra["encoding"] == "ascii"


def test_decode_multi_register_string() -> None:
    """Multi-register strings decode without applying scaling."""
    reg = RegisterDef(
        function=3,
        address=0,
        name="device_name",
        access="ro",
        length=3,
        extra={"type": "string"},
        multiplier=2,
        resolution=1,
    )
    raw = [16706, 17220, 17664]  # "ABCDE"
    assert reg.decode(raw) == "ABCDE"


def test_decode_multi_register_number_scaled_once() -> None:
    """Numeric multi-register values apply multiplier/resolution exactly once."""
    reg = RegisterDef(
        function=3,
        address=0,
        name="counter",
        access="ro",
        length=2,
        extra={"type": "i32"},
        multiplier=10,
        resolution=1,
    )
    raw = [0, 1]
    assert reg.decode(raw) == 10


def test_decode_bitmask_ignores_scaling() -> None:
    """Bitmask registers return labels without scaling the raw value."""
    reg = RegisterDef(
        function=3,
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

    # Use a temporary copy of the register file so we can modify it
    path = tmp_path / "regs.json"
    path.write_text(_REGISTERS_PATH.read_text())

    read_calls = 0
    hash_calls = 0
    real_read_text = Path.read_text
    real_read_bytes = Path.read_bytes

    def spy_read(self, *args, **kwargs):
        nonlocal read_calls
        read_calls += 1
        text = real_read_text(self, *args, **kwargs)
        json.loads(text)
        return text

    def spy_read_bytes(self):
        nonlocal hash_calls
        hash_calls += 1
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_text", spy_read)
    monkeypatch.setattr(Path, "read_bytes", spy_read_bytes)

    clear_cache()

    hash_before = registers_sha256(path)
    load_registers(path)
    load_registers(path)

    assert read_calls == 1
    assert hash_calls == 1

    path.write_text(real_read_text(path) + "\n")

    load_registers(path)
    hash_after = registers_sha256(path)

    assert read_calls == 2
    assert hash_calls == 2
    assert hash_before != hash_after


def test_registers_sha256_uses_cache(tmp_path, monkeypatch) -> None:
    """registers_sha256 should avoid re-reading unchanged files."""

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

    digest1 = registers_sha256(path)
    digest2 = registers_sha256(path)

    assert digest1 == digest2
    assert read_calls == 1

    path.write_text("data2")
    os.utime(path, (mtime + 1, mtime + 1))
    registers_sha256(path)

    assert read_calls == 2


def test_registers_reload_on_file_change(tmp_path) -> None:
    """Changing the register JSON file triggers a reload."""

    path = tmp_path / "regs.json"
    path.write_text(_REGISTERS_PATH.read_text())

    clear_cache()

    original = load_registers(path)
    assert not any(r.name == "cache_test_marker" for r in original)

    data = json.loads(path.read_text())
    data["registers"][0]["name"] = "cache_test_marker"
    path.write_text(json.dumps(data))

    updated = load_registers(path)
    assert any(r.name == "cache_test_marker" for r in updated)


def test_clear_cache_resets_file_hash(tmp_path, monkeypatch) -> None:
    """clear_cache should reset the cached file hash."""

    path = tmp_path / "regs.json"
    path.write_text(_REGISTERS_PATH.read_text())

    hash_calls = 0
    real_read_bytes = Path.read_bytes

    def spy_read_bytes(self):
        nonlocal hash_calls
        hash_calls += 1
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", spy_read_bytes)

    clear_cache()

    # First load computes hash once
    load_registers(path)
    load_registers(path)
    assert hash_calls == 1

    # Clearing the cache forces a re-computation
    clear_cache()
    load_registers(path)
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
def test_duplicate_registers_raise_error(tmp_path, registers) -> None:
    """Duplicate names or addresses should raise an error."""

    path = tmp_path / "regs.json"
    _write(path, registers)

    with pytest.raises(ValueError):
        _load_registers_from_file(path, mtime=0, file_hash="")


@pytest.mark.parametrize(
    "register",
    [
        {
            "function": "03",
            "address_dec": 1,
            "name": "bad_addr",
            "access": "R",
        },
        {
            "function": "03",
            "address_dec": 0,
            "name": "bad_len",
            "access": "R",
            "length": 1,
            "extra": {"type": "u32"},
        },
        {
            "function": "01",
            "address_dec": 0,
            "name": "bad_access",
            "access": "RW",
        },
        {
            "function": "03",
            "address_dec": 0,
            "name": "bad_bits",
            "access": "R",
            "bits": [{"name": "a"}],
        },
        {
            "function": "03",
            "address_dec": 0,
            "name": "bad_string_len",
            "access": "R",
            "length": 0,
            "extra": {"type": "string"},
        },
        {
            "function": "03",
            "address_dec": 0,
            "name": "bad_bit_name",
            "access": "R",
            "extra": {"bitmask": 0b1},
            "bits": [{"name": "BadName", "index": 0}],
        },
        {
            "function": "03",
            "address_dec": 0,
            "name": "bit_index_out_of_range",
            "access": "R",
            "extra": {"bitmask": 65535},
            "bits": [{"name": f"b{i}", "index": i} for i in range(17)],
        },
    ],
)
def test_invalid_registers_rejected(tmp_path, register) -> None:
    """Registers violating schema constraints should raise an error."""

    path = tmp_path / "regs.json"
    _write(path, [register])

    with pytest.raises(ValueError):
        _load_registers_from_file(path, mtime=0, file_hash="")


def test_bits_within_bitmask_width(tmp_path) -> None:
    """Registers with bits not exceeding bitmask width should load."""

    reg = {
        "function": "03",
        "address_dec": 0,
        "name": "good_bits",
        "access": "R",
        "extra": {"bitmask": 0b11},
        "bits": [{"name": "a", "index": 0}, {"name": "b", "index": 1}],
    }
    path = tmp_path / "regs.json"
    _write(path, [reg])

    _load_registers_from_file(path, file_hash="", mtime=0)


@pytest.mark.parametrize(
    "reg",
    [
        {"description_en": "en"},
        {"description": "pl"},
        {"description": "", "description_en": "en"},
        {"description": "pl", "description_en": ""},
    ],
)
def test_missing_descriptions_rejected(tmp_path, reg) -> None:
    base = {
        "function": "03",
        "address_dec": 0,
        "name": "no_desc",
        "access": "R",
    }
    base.update(reg)
    path = tmp_path / "regs.json"
    path.write_text(json.dumps({"registers": [base]}))

    with pytest.raises(ValueError):
        _load_registers_from_file(path, mtime=0, file_hash="")


def test_missing_register_file_raises_runtime_error(tmp_path) -> None:
    """Missing register definition file should raise RuntimeError."""

    path = tmp_path / "regs.json"
    with pytest.raises(RuntimeError) as exc:
        _load_registers_from_file(path, mtime=0, file_hash="")
    assert str(path) in str(exc.value)


def test_invalid_register_file_raises_runtime_error(tmp_path) -> None:
    """Invalid register definition file should raise RuntimeError."""

    path = tmp_path / "regs.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        _load_registers_from_file(path, mtime=0, file_hash="")
    assert str(path) in str(exc.value)


def test_register_file_sorted() -> None:
    """Ensure register JSON is sorted and loader preserves ordering."""

    data = json.loads(_REGISTERS_PATH.read_text(encoding="utf-8"))
    regs = data["registers"]
    keys = [(str(r["function"]), int(r["address_dec"])) for r in regs]
    assert keys == sorted(keys)


def test_special_modes_invalid_json(monkeypatch) -> None:
    """Loader falls back to empty special mode enum on invalid file."""

    import importlib
    from pathlib import Path

    special_path = _SPECIAL_MODES_PATH
    real_read_text = Path.read_text

    def bad_read(self, *args, **kwargs):  # pragma: no cover - simple stub
        if self == special_path:
            return "{"
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read)

    loader_module = importlib.import_module(
        "custom_components.thessla_green_modbus.registers.loader"
    )
    loader_module = importlib.reload(loader_module)
    assert loader_module._SPECIAL_MODES_ENUM == {}  # nosec B101

    monkeypatch.setattr(Path, "read_text", real_read_text)
    importlib.reload(loader_module)


def test_get_all_registers_sorted(tmp_path) -> None:
    """get_all_registers should order registers by function then address."""

    regs = [
        {
            "function": "03",
            "address_dec": 2,
            "name": "reg_c",
            "access": "R",
        },
        {
            "function": "01",
            "address_dec": 1,
            "name": "reg_a",
            "access": "R",
        },
        {
            "function": "03",
            "address_dec": 1,
            "name": "reg_b",
            "access": "R",
        },
    ]

    path = tmp_path / "regs.json"
    _write(path, regs)

    clear_cache()
    ordered = get_all_registers(path)
    keys = [(r.function, r.address) for r in ordered]
    assert keys == sorted(keys)
