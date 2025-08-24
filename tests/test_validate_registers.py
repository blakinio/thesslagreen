"""Tests for tools.validate_registers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
                "access": "R/W",
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
                "access": "R/W",
            },
            {
                "function": "03",
                "address_dec": 2,
                "address_hex": "0x0002",
                "name": "dup",
                "access": "R/W",
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
                "access": "R/W",
            },
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "second",
                "access": "R/W",
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
                "access": "R/W",
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
                "access": "R/W",
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
                "access": "R/W",
            }
        ],
    )

    with pytest.raises(SystemExit):
        validate_registers.main(path)


def test_validator_rejects_bits_without_bitmask(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "function": "03",
                "address_dec": 1,
                "address_hex": "0x0001",
                "name": "bad_bits",
                "access": "R/W",
                "bits": [{"name": "a"}],
            }
        ],
    )

    with pytest.raises(SystemExit):
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
                "access": "R/W",
                "extra": {"bitmask": 0b1},
                "bits": [{"name": "BadName"}],
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
                "access": "R/W",
                "extra": {"bitmask": 0b1},
                "bits": [{"name": "a", "index": 1}],
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
                "access": "R/W",
                "extra": {"bitmask": 0xFFFF},
                "bits": [{"name": f"b{i}"} for i in range(17)],
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
                "access": "R/W",
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
                "access": "R/W",
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
                "access": "R/W",
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
                "access": "R/W",
                "extra": {"bitmask": 0b1},
                "bits": ["BadBit"],
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
                "access": "R/W",
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
                "access": "R/W",
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
                "access": "R/W",
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
                "access": "R/W",
                "type": "u32",
            }
        ],
    )

    regs = validate_registers.validate(path)
    reg = regs[0]
    assert reg.length == 2
    assert (reg.extra or {}).get("type") == "u32"

