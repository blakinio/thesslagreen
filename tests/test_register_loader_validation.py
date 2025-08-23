from __future__ import annotations

import json
import re
from importlib import resources
from typing import Literal

import pydantic
import pytest
from custom_components.thessla_green_modbus.registers.loader import _validate_item


class Register(pydantic.BaseModel):
    function: Literal["01", "02", "03", "04"]
    address_dec: int
    address_hex: str
    name: str
    access: Literal["R/-", "R/W", "R", "W"]
    unit: str | None = None
    enum: dict[str, int | str] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    description: str | None = None

    model_config = pydantic.ConfigDict(extra="allow")

    @pydantic.model_validator(mode="after")
    def check_address(self) -> "Register":
        assert int(self.address_hex, 16) == self.address_dec
        return self

    @pydantic.field_validator("name")
    @classmethod
    def name_is_snake(cls, v: str) -> str:
        assert re.fullmatch(r"[a-z0-9_]+", v)
        return v


EXPECTED = {
    "01": {"min": 5, "max": 15, "count": 8},
    "02": {"min": 0, "max": 21, "count": 16},
    "03": {"min": 0, "max": 8444, "count": 270},
    "04": {"min": 0, "max": 298, "count": 24},
}


def test_register_file_valid() -> None:
    """Validate register JSON structure and completeness."""

    json_file = (
        resources.files("custom_components.thessla_green_modbus.registers")
        .joinpath("thessla_green_registers_full.json")
    )
    data = json.loads(json_file.read_text(encoding="utf-8"))
    registers = data.get("registers", data)

    parsed = [Register(**item) for item in registers]

    by_fn: dict[str, list[int]] = {}
    for reg in parsed:
        by_fn.setdefault(reg.function, []).append(reg.address_dec)

    for fn, spec in EXPECTED.items():
        addrs = by_fn.get(fn, [])
        assert len(addrs) == spec["count"]
        assert min(addrs) == spec["min"]
        assert max(addrs) == spec["max"]


def test_validate_item_rejects_unknown_function() -> None:
    """Unknown function codes should be rejected."""

    bad = {"name": "x", "function": "05", "address_dec": 0, "access": "R/W"}
    with pytest.raises(ValueError):
        _validate_item(bad)


def test_validate_item_rejects_unknown_access() -> None:
    """Unexpected access types should raise an error."""

    bad = {"name": "x", "function": "03", "address_dec": 0, "access": "RW"}
    with pytest.raises(ValueError):
        _validate_item(bad)
