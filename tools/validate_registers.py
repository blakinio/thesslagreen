#!/usr/bin/env python3
"""Validate register definitions in the bundled JSON file."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import pydantic


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)


class Register(pydantic.BaseModel):
    """Schema for a single register entry."""

    function: Literal["01", "02", "03", "04"]
    address_dec: int
    address_hex: str
    name: str
    access: Literal["R/-", "R/W", "R", "W"]
    extra: dict[str, Any] | None = None
    length: int = 1
    bits: list[Any] | None = None

    model_config = pydantic.ConfigDict(extra="allow")  # pragma: no cover

    @pydantic.field_validator("name")
    @classmethod
    def name_is_snake(cls, v: str) -> str:  # pragma: no cover
        if not re.fullmatch(r"[a-z0-9_]+", v):
            raise ValueError("name must be snake_case")
        return v

    @pydantic.model_validator(mode="after")
    def check_consistency(self) -> "Register":  # pragma: no cover
        if int(self.address_hex, 16) != self.address_dec:
            raise ValueError("address_hex does not match address_dec")

        typ = (self.extra or {}).get("type")
        expected_len = {
            "uint32": 2,
            "int32": 2,
            "float32": 2,
            "uint64": 4,
            "int64": 4,
            "float64": 4,
        }.get(typ)
        if expected_len is not None and self.length != expected_len:
            raise ValueError("length does not match type")

        if self.function in {"01", "02"} and self.access not in {"R", "R/-"}:
            raise ValueError("read-only functions must have R access")

        if self.bits is not None and not (self.extra and self.extra.get("bitmask")):
            raise ValueError("bits provided without extra.bitmask")

        return self


def validate(path: Path) -> list[Register]:
    """Validate ``path`` and return the parsed register definitions."""

    data = json.loads(path.read_text(encoding="utf-8"))
    registers = data.get("registers", data)
    parsed = [Register.model_validate(reg) for reg in registers]

    name_counts = Counter(r.name for r in parsed)
    dup_names = [name for name, count in name_counts.items() if count > 1]

    pair_counts = Counter((r.function, r.address_dec) for r in parsed)
    dup_pairs = [pair for pair, count in pair_counts.items() if count > 1]

    if dup_names or dup_pairs:
        errors: list[str] = []
        if dup_names:
            errors.append(f"duplicate names: {sorted(dup_names)}")
        if dup_pairs:
            errors.append(
                f"duplicate (function, address_dec) pairs: {sorted(dup_pairs)}"
            )
        raise ValueError("; ".join(errors))

    return parsed


def main(path: Path = JSON_PATH) -> None:
    """Validate registers file, exiting with status 1 on error."""

    try:
        validate(path)
    except Exception as err:  # pragma: no cover - error path
        print(err)
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

