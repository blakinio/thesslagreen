"""Tests for tools.validate_registers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.thessla_green_modbus.registers.schema import RegisterType
from tools import validate_registers


def _write(tmp_path: Path, regs: list[dict]) -> Path:
    path = tmp_path / "regs.json"
    path.write_text(json.dumps({"registers": regs}))
    return path


def test_validator_accepts_valid(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "valid_reg",
                "access": "RW",
            }
        ],
    )

    validate_registers.main(path)


def test_validator_rejects_duplicate_name(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "dup",
                "access": "RW",
            },
            {
                "function": "03",
                "address_dec": 2,
                "address_hex": "0x0002",
                "name": "dup",
                "access": "RW",
            },
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_duplicate_pair(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "first",
                "access": "RW",
            },
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "second",
                "access": "RW",
            },
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_bad_hex(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0002",
                "name": "bad_hex",
                "access": "RW",
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_length_mismatch(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bad_len",
                "access": "RW",
                "length": 1,
                "extra": {"type": "u32"},
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_function_access_mismatch(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "01",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bad_access",
                "access": "RW",
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_accepts_bits_without_bitmask(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bits_only",
                "access": "RW",
                "bits": [{"name": "a", "index": 0}],
            }
        ],
    )

    validate_registers.main(path)


def test_validator_rejects_bit_name(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bad_bit_name",
                "access": "RW",
                "extra": {"bitmask": 0b1},
                "bits": [{"name": "BadName", "index": 0}],
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_bit_index(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bad_bit_index",
                "access": "RW",
                "extra": {"bitmask": 0b1},
                "bits": [{"name": "a", "index": 16}],
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_missing_bit_index(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "missing_bit_index",
                "access": "RW",
                "extra": {"bitmask": 0b1},
                "bits": [{"name": "a"}],
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_non_mapping_bit(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "non_mapping_bit",
                "access": "RW",
                "extra": {"bitmask": 0b1},
                "bits": ["a"],
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_missing_bit_name(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "missing_bit_name",
                "access": "RW",
                "extra": {"bitmask": 0b1},
                "bits": [{"index": 0}],
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_duplicate_bit_index(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "dup_bit_index",
                "access": "RW",
                "extra": {"bitmask": 0b11},
                "bits": [
                    {"name": "a", "index": 0},
                    {"name": "b", "index": 0},
                ],
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_bit_index_out_of_range(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bit_index_out_of_range",
                "access": "RW",
                "extra": {"bitmask": 0xFFFF},
                "bits": [{"name": f"b{i}", "index": i} for i in range(17)],
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_non_snake_case(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "NotSnake",
                "access": "RW",
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_accepts_numeric_function_code(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": 3,
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "numeric_fn",
                "access": "RW",
            }
        ],
    )

    validate_registers.main(path)


def test_validator_rejects_type_alias(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bad_type",
                "access": "RW",
                "extra": {"type": "uint"},
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_bad_bit_name(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bad_bit_name",
                "access": "RW",
                "extra": {"bitmask": 0b1},
                "bits": [{"name": "BadBit", "index": 0}],
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_min_max_mismatch(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bad_range",
                "access": "RW",
                "min": 5,
                "max": 1,
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_accepts_string_address_dec(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": 3,
                "address_dec": "0x1",
                "address_hex": "0x0001",
                "name": "addr_str",
                "access": "RW",
            }
        ],
    )

    regs = validate_registers.validate(path)
    assert regs[0].address_dec == 1
    assert regs[0].address_hex == "0x1"


def test_accepts_count_alias(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "count_alias",
                "access": "RW",
                "count": 2,
                "extra": {"type": "u32"},
            }
        ],
    )

    regs = validate_registers.validate(path)
    assert regs[0].length == 2


def test_accepts_shorthand_type(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "shorthand",
                "access": "RW",
                "type": "u32",
            }
        ],
    )

    regs = validate_registers.validate(path)
    reg = regs[0]
    assert reg.length == 2
    assert reg.type == RegisterType.U32

