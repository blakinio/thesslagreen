from __future__ import annotations

import re
from typing import Any, Literal

import pydantic

from ..utils import _normalise_name


def _normalise_function(fn: str) -> str:
    """Normalise function codes to two-digit strings."""
    mapping = {
        "coil": "01",
        "coils": "01",
        "coil_registers": "01",
        "discrete_input": "02",
        "discrete_inputs": "02",
        "holding_register": "03",
        "holding_registers": "03",
        "input_register": "04",
        "input_registers": "04",
        "inputregister": "04",
        "inputregisters": "04",
    }
    key = fn.lower().replace(" ", "_")
    return mapping.get(key, fn)


class RegisterDefinition(pydantic.BaseModel):
    """Schema describing a raw register definition from JSON."""

    function: Literal["01", "02", "03", "04"]
    address_dec: int
    address_hex: str
    name: str
    access: Literal["R/-", "R/W", "R", "W"]
    unit: str | None = None
    enum: dict[str, Any] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    description: str | None = None
    description_en: str | None = None
    min: float | None = None
    max: float | None = None
    default: float | None = None
    notes: str | None = None
    information: str | None = None
    extra: dict[str, Any] | None = None
    length: int = 1
    bcd: bool = False
    bits: list[Any] | None = None

    model_config = pydantic.ConfigDict(extra="allow")  # pragma: no cover

    @pydantic.model_validator(mode="after")
    def check_consistency(self) -> "RegisterDefinition":  # pragma: no cover
        if int(self.address_hex, 16) != self.address_dec:
            raise ValueError("address_hex does not match address_dec")

        typ = (self.extra or {}).get("type")
        if typ == "string":
            if self.length < 1:
                raise ValueError("string type requires length >= 1")
        else:
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

        if self.bits is not None:
            if not (self.extra and self.extra.get("bitmask")):
                raise ValueError("bits provided without extra.bitmask")

            if len(self.bits) > 16:
                raise ValueError("bits index out of range")

            for idx, bit in enumerate(self.bits):
                if not isinstance(bit, dict):
                    raise ValueError("bits entries must be objects")

                name = bit.get("name")
                if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]+", name):
                    raise ValueError("bit name must be snake_case")

                index = bit.get("index", idx)
                if not isinstance(index, int) or isinstance(index, bool):
                    raise ValueError("bit index must be an integer")
                if index != idx:
                    raise ValueError("bits must be in implicit index order")
                if not 0 <= index <= 15:
                    raise ValueError("bit index out of range")

            bitmask_val = self.extra.get("bitmask") if self.extra else None
            mask_int: int | None = None
            if isinstance(bitmask_val, str):
                try:
                    mask_int = int(bitmask_val, 0)
                except ValueError:
                    mask_int = None
            elif isinstance(bitmask_val, int) and not isinstance(bitmask_val, bool):
                mask_int = bitmask_val
            if mask_int is not None and len(self.bits) > mask_int.bit_length():
                raise ValueError("bits exceed bitmask width")

        return self

    @pydantic.field_validator("name")
    @classmethod
    def name_is_snake(cls, v: str) -> str:  # pragma: no cover
        if not re.fullmatch(r"[a-z0-9_]+", v):
            raise ValueError("name must be snake_case")
        return v


class RegisterList(pydantic.RootModel[list[RegisterDefinition]]):
    """Container model to validate a list of registers."""

    @pydantic.model_validator(mode="after")
    def unique(self) -> "RegisterList":  # pragma: no cover
        seen_pairs: set[tuple[str, int]] = set()
        seen_names: set[str] = set()
        for reg in self.root:
            fn = _normalise_function(reg.function)
            name = _normalise_name(reg.name)
            pair = (fn, reg.address_dec)
            if pair in seen_pairs:
                raise ValueError(f"duplicate register pair: {pair}")
            if name in seen_names:
                raise ValueError(f"duplicate register name: {name}")
            seen_pairs.add(pair)
            seen_names.add(name)
        return self

