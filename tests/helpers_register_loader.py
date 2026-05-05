"""Shared fixtures for register-loader tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def registers() -> list[list[dict[str, object]]]:
    """Duplicate register scenarios used by validation tests."""
    return [
        [
            {"function": "01", "address_dec": 1, "name": "dup1", "access": "R"},
            {"function": "01", "address_dec": 1, "name": "dup2", "access": "R"},
        ],
        [
            {"function": "01", "address_dec": 1, "name": "dup", "access": "R"},
            {"function": "02", "address_dec": 2, "name": "dup", "access": "R"},
        ],
    ]


@pytest.fixture
def register() -> list[dict[str, object]]:
    """Invalid register schema scenarios used by validation tests."""
    return [
        {
            "function": "03",
            "address_dec": 0,
            "name": "bad_len",
            "access": "R",
            "length": 1,
            "extra": {"type": "u32"},
        },
        {"function": "01", "address_dec": 0, "name": "bad_access", "access": "RW"},
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
    ]


@pytest.fixture
def reg() -> list[dict[str, str]]:
    """Missing-description scenarios used by validation tests."""
    return [
        {"description_en": "en"},
        {"description": "pl"},
        {"description": "", "description_en": "en"},
        {"description": "pl", "description_en": ""},
    ]
