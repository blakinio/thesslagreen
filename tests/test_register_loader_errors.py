"""Split register loader tests."""

import json
from pathlib import Path

import pytest
from custom_components.thessla_green_modbus.registers.parser import load_registers_from_file


def _add_desc(reg: dict) -> dict:
    return {
        **reg,
        "description": reg.get("description", "desc"),
        "description_en": reg.get("description_en", "desc"),
    }


def _write(path: Path, regs: list[dict]) -> None:
    path.write_text(json.dumps({"registers": [_add_desc(r) for r in regs]}))


def test_duplicate_registers_raise_error(tmp_path, registers) -> None:
    """Duplicate names or addresses should raise an error."""

    path = tmp_path / "regs.json"
    _write(path, registers)

    with pytest.raises(ValueError):
        load_registers_from_file(path)


def test_invalid_registers_rejected(tmp_path, register) -> None:
    """Registers violating schema constraints should raise an error."""

    path = tmp_path / "regs.json"
    _write(path, [register])

    with pytest.raises(ValueError):
        load_registers_from_file(path)


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

    load_registers_from_file(path)


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
        load_registers_from_file(path)


def test_missing_register_file_raises_runtime_error(tmp_path) -> None:
    """Missing register definition file should raise RuntimeError."""

    path = tmp_path / "regs.json"
    with pytest.raises(RuntimeError) as exc:
        load_registers_from_file(path)
    assert str(path) in str(exc.value)


def test_invalid_register_file_raises_runtime_error(tmp_path) -> None:
    """Invalid register definition file should raise RuntimeError."""

    path = tmp_path / "regs.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        load_registers_from_file(path)
    assert str(path) in str(exc.value)


def test_special_modes_invalid_json(monkeypatch) -> None:
    """Parser falls back to empty special mode enum on invalid file."""

    import importlib
    from pathlib import Path

    from custom_components.thessla_green_modbus.registers import parser as parser_module

    special_path = parser_module._SPECIAL_MODES_PATH
    real_read_text = Path.read_text

    def bad_read(self, *args, **kwargs):  # pragma: no cover - simple stub
        if self == special_path:
            return "{"
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read)

    parser_module = importlib.import_module(
        "custom_components.thessla_green_modbus.registers.parser"
    )
    parser_module = importlib.reload(parser_module)
    assert parser_module._SPECIAL_MODES_ENUM == {}  # nosec B101

    monkeypatch.setattr(Path, "read_text", real_read_text)
    importlib.reload(parser_module)
