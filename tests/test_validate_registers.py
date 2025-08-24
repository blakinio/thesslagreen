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
                "extra": {"type": "uint32"},
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
                "bits": ["a"],
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

