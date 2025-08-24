from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

import pydantic

from ..utils import _normalise_name


def _normalise_function(fn: int | str) -> int:
    """Return canonical integer Modbus function code.

    String aliases like ``"coil_registers"`` or zero-padded values are mapped to
    their numeric equivalents. Values outside the 1–4 range raise ``ValueError``.
    """

    mapping = {
        "coil": 1,
        "coils": 1,
        "coil_registers": 1,
        "discrete": 2,
        "discrete_input": 2,
        "discrete_inputs": 2,
        "holding": 3,
        "holding_register": 3,
        "holding_registers": 3,
        "input": 4,
        "input_register": 4,
        "input_registers": 4,
        "inputregister": 4,
        "inputregisters": 4,
    }

    if isinstance(fn, str):
        key = fn.lower().replace(" ", "_")
        fn = mapping.get(key, fn)
        try:
            fn = int(fn)
        except (TypeError, ValueError) as err:  # pragma: no cover - defensive
            raise ValueError(f"unknown function code: {fn}") from err

    if fn not in {1, 2, 3, 4}:  # pragma: no cover - defensive
        raise ValueError(f"unknown function code: {fn}")

    return fn


class RegisterType(str, Enum):
    """Supported register data types."""

    U16 = "u16"
    I16 = "i16"
    U32 = "u32"
    I32 = "i32"
    F32 = "f32"
    U64 = "u64"
    I64 = "i64"
    F64 = "f64"
    STRING = "string"
    BITMASK = "bitmask"


class RegisterDefinition(pydantic.BaseModel):
    """Schema describing a raw register definition from JSON."""

    function: int
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


    @pydantic.model_validator(mode="before")
    @classmethod
    def _normalise_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        # Allow string/int function codes and normalise them early
        if "function" in data:
            data["function"] = _normalise_function(data["function"])
        return data
    @pydantic.field_validator("function", mode="before")
    @classmethod
    def normalise_function(cls, v: Any) -> str:
        """Accept numeric/alias function codes and normalise to two digits."""
        if isinstance(v, int):
            if 1 <= v <= 4:
                return f"{v:02d}"
            raise ValueError("function code must be between 1 and 4")
        if isinstance(v, str):
            v = _normalise_function(v)
            if v.isdigit():
                iv = int(v)
                if 1 <= iv <= 4:
                    return f"{iv:02d}"
            return v
        raise TypeError("function code must be str or int")

    @pydantic.model_validator(mode="after")
    def check_consistency(self) -> "RegisterDefinition":  # pragma: no cover
        if int(self.address_hex, 16) != self.address_dec:
            raise ValueError("address_hex does not match address_dec")

        typ = (self.extra or {}).get("type")
        if typ is not None:
            try:
                reg_type = RegisterType(typ)
            except ValueError as err:
                raise ValueError(f"unsupported type: {typ}") from err
        else:
            reg_type = None

        type_lengths = {
            RegisterType.U16: 1,
            RegisterType.I16: 1,
            RegisterType.BITMASK: 1,
            RegisterType.U32: 2,
            RegisterType.I32: 2,
            RegisterType.F32: 2,
            RegisterType.U64: 4,
            RegisterType.I64: 4,
            RegisterType.F64: 4,
        }

        if typ in {"uint", "int", "float"}:
            raise ValueError("type aliases are not allowed")
        if reg_type == RegisterType.STRING or typ == "string":
            if self.length < 1:
                raise ValueError("string type requires length >= 1")
        elif reg_type in type_lengths:
            expected = type_lengths[reg_type]
            if self.length != expected:
                raise ValueError("length does not match type")

        if self.function in {1, 2} and self.access not in {"R", "R/-"}:
            raise ValueError("read-only functions must have R access")

        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min greater than max")
        if self.default is not None:
            if self.min is not None and self.default < self.min:
                raise ValueError("default below min")
            if self.max is not None and self.default > self.max:
                raise ValueError("default above max")

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
            if len(self.bits) > 16:
                raise ValueError("bits exceed 16 entries")
            for idx, bit in enumerate(self.bits):
                if idx > 15:
                    raise ValueError("bit index out of range")
                name = bit.get("name") if isinstance(bit, dict) else str(bit)
                if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]+", name):
                    raise ValueError("bit names must be snake_case")

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
        seen_pairs: set[tuple[int, int]] = set()
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

