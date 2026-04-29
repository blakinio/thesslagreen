"""Pydantic models describing register definitions.

This module validates the raw JSON register description bundled with the
integration.  The previous implementation had become a little tangled due to
multiple rounds of feature additions.  The file is rewritten here to add a few
new capabilities while keeping the validation logic focused and explicit.

Key features implemented:

* ``function`` accepts integers or strings and is normalised to the canonical
  integer form (``1`` … ``4``).
* ``address_dec`` may be provided as either an integer or string.
* ``length`` accepts ``count`` as an alias.
* A top level ``type`` field is supported.  It accepts shorthand identifiers
  (``u16``, ``i16`` … ``f64``, ``string``, ``bitmask``) and the expected
  register count is enforced or defaulted.
"""

from __future__ import annotations

import logging
import re
from enum import StrEnum
from typing import Any, Literal, cast

import pydantic
from pydantic import BaseModel, ConfigDict, Field

from ..utils import _normalise_name

_LOGGER = logging.getLogger(__name__)

RootModel = pydantic.RootModel
model_validator = pydantic.model_validator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_function(fn: int | str) -> int:
    """Return canonical integer Modbus function code.

    String aliases like ``"coil_registers"`` or zero‑padded values are mapped
    to their numeric equivalents.  Values outside the ``1``–``4`` range raise a
    ``ValueError``.
    """

    mapping = {
        "coil": 1,
        "coils": 1,
        "coil_registers": 1,
        "coilregisters": 1,
        "discrete": 2,
        "discrete_input": 2,
        "discrete_inputs": 2,
        "discreteinput": 2,
        "discreteinputs": 2,
        "holding": 3,
        "holding_register": 3,
        "holding_registers": 3,
        "holdingregister": 3,
        "holdingregisters": 3,
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
        except (TypeError, ValueError) as err:
            raise ValueError(f"unknown function code: {fn}") from err

    if fn not in {1, 2, 3, 4}:
        raise ValueError(f"unknown function code: {fn}")

    return fn


class RegisterType(StrEnum):
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


# Expected register counts for the shorthand types above
_TYPE_LENGTHS: dict[str, int | None] = {
    "u16": 1,
    "i16": 1,
    "bitmask": 1,
    "u32": 2,
    "i32": 2,
    "f32": 2,
    "u64": 4,
    "i64": 4,
    "f64": 4,
    "string": None,  # variable length
}


def _normalise_access(access: Any) -> str:
    """Return canonical access value."""
    if access in {"R/-", "R"}:
        return "R"
    if access in {"R/W", "RW"}:
        return "RW"
    if access == "W":
        return "W"
    raise ValueError("access must be one of 'R', 'RW', 'W'")


def _normalise_address_dec(addr_dec: Any) -> int:
    """Normalize decimal register address representation."""
    if isinstance(addr_dec, str):
        if not re.fullmatch(r"[0-9]+", addr_dec):
            _LOGGER.error("Register address must be decimal: %s", addr_dec)
            raise ValueError("Register address must be decimal")
        return int(addr_dec)
    if not isinstance(addr_dec, int) or isinstance(addr_dec, bool):
        raise ValueError("address_dec must be int or str")
    return addr_dec


def _normalise_type_and_extra(data: dict[str, Any]) -> None:
    """Sync top-level type field with nested extra metadata."""
    typ = data.pop("type", None)
    extra = data.get("extra")
    if typ is None and isinstance(extra, dict):
        typ = extra.get("type")
    if extra is None:
        extra = {}
    if typ is not None:
        extra.setdefault("type", typ)
        data["type"] = typ
    if extra:
        data["extra"] = extra


def _validate_scaling_metadata(data: dict[str, Any]) -> None:
    """Apply default scaling metadata values."""
    if data.get("multiplier") is None:
        data["multiplier"] = 1
    if data.get("resolution") is None:
        data["resolution"] = 1


def _validate_type_length(typ: Any, length: int | None) -> int | None:
    """Validate register length against type and return default if needed."""
    if typ is None:
        return None
    if typ in {"uint", "int", "float"}:
        raise ValueError("type aliases are not allowed")
    expected = _TYPE_LENGTHS.get(typ)
    if expected is None:
        if length is None or length < 1:
            raise ValueError("string type requires length >= 1")
        return None
    if length is not None and length != expected:
        raise ValueError("length does not match type")
    return expected if length is None else None


def _validate_enum_mapping(enum: dict[str, Any] | None) -> None:
    if enum is None:
        return
    if not isinstance(enum, dict):
        raise ValueError("enum must be a mapping")
    for k, v in enum.items():
        try:
            int(k)
        except (TypeError, ValueError):
            raise ValueError("enum keys must be numeric") from None
        if not isinstance(v, str):
            raise ValueError("enum values must be strings")


def _validate_numeric_bounds(min_val: float | None, max_val: float | None, default: float | None) -> None:
    if min_val is not None and max_val is not None and min_val > max_val:
        raise ValueError("min greater than max")
    if default is not None:
        if min_val is not None and default < min_val:
            raise ValueError("default below min")
        if max_val is not None and default > max_val:
            raise ValueError("default above max")


def _validate_bits_and_mask(bits: list[Any] | None, extra: dict[str, Any] | None) -> None:
    seen_indices: set[int] = set()
    if bits is not None:
        if len(bits) > 16:
            raise ValueError("bits exceed 16 entries")
        for bit in bits:
            if not isinstance(bit, dict):
                raise ValueError("bits entries must be objects")
            if "index" not in bit or "name" not in bit:
                raise ValueError("bits entries must have index and name")
            idx = bit["index"]
            name = bit["name"]
            if not isinstance(idx, int) or isinstance(idx, bool):
                raise ValueError("bit index must be an integer")
            if not 0 <= idx <= 15:
                raise ValueError("bit index out of range")
            if idx in seen_indices:
                raise ValueError("bit indices must be unique")
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]+", name):
                raise ValueError("bit name must be snake_case")
            seen_indices.add(idx)

    bitmask_val = extra.get("bitmask") if isinstance(extra, dict) else None
    mask_int: int | None = None
    if isinstance(bitmask_val, str):
        if not re.fullmatch(r"[0-9]+", bitmask_val):
            raise ValueError("bitmask must be decimal digits")
        mask_int = int(bitmask_val)
    elif isinstance(bitmask_val, int) and not isinstance(bitmask_val, bool):
        mask_int = bitmask_val

    if mask_int is not None and max(seen_indices, default=-1) >= mask_int.bit_length():
        raise ValueError("bits exceed bitmask width")


class RegisterDefinition(BaseModel):
    """Schema describing a raw register definition from JSON."""

    function: int
    address_dec: int
    name: str
    access: Literal["R", "RW", "W"]
    unit: str | None = None
    enum: dict[str, Any] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    description: str = Field(min_length=1)
    description_en: str = Field(min_length=1)
    min: float | None = None
    max: float | None = None
    default: float | None = None
    notes: str | None = None
    information: str | None = None
    extra: dict[str, Any] | None = None
    length: int = Field(1)
    bcd: bool = False
    bits: list[Any] | None = None
    type: RegisterType | None = None

    if hasattr(pydantic, "field_validator"):
        model_config = ConfigDict(extra="allow")
    else:

        class Config:
            extra = "allow"

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @model_validator(mode="before")
    @classmethod
    def _normalise_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Normalise raw input from JSON."""

        if "length" not in data and "count" in data:
            data["length"] = data["count"]

        # Normalise function code -> canonical integer
        if "function" in data:
            fn_int = _normalise_function(data["function"])
            data["function"] = fn_int

        # Normalise access values to canonical form
        access = data.get("access")
        if access is not None:
            data["access"] = _normalise_access(access)

        # Normalise address_dec (decimal-only in manufacturer register specification)
        addr_dec = data.get("address_dec")
        if addr_dec is not None:
            data["address_dec"] = _normalise_address_dec(addr_dec)

        _normalise_type_and_extra(data)
        expected_len = _validate_type_length(data.get("type"), data.get("length"))
        if expected_len is not None:
            data["length"] = expected_len
        _validate_scaling_metadata(data)

        return data

    if hasattr(pydantic, "field_validator"):

        @pydantic.field_validator("function")
        @classmethod
        def _check_function(cls, v: int) -> int:
            if v not in {1, 2, 3, 4}:
                raise ValueError("function code must be between 1 and 4")
            return v

    else:

        @pydantic.validator("function")
        def _check_function(cls, v: int) -> int:
            if v not in {1, 2, 3, 4}:
                raise ValueError("function code must be between 1 and 4")
            return v

    if hasattr(pydantic, "model_validator"):

        @model_validator(mode="after")
        def _check_access(self) -> RegisterDefinition:
            if self.function in {1, 2} and self.access != "R":
                raise ValueError("read-only functions must have R access")
            return self

    else:

        @pydantic.root_validator
        def _check_access(cls, values: dict[str, Any]) -> dict[str, Any]:
            function = values.get("function")
            access = values.get("access")
            if function in {1, 2} and access != "R":
                raise ValueError("read-only functions must have R access")
            return values

    # ------------------------------------------------------------------
    # Additional consistency checks
    # ------------------------------------------------------------------

    if hasattr(pydantic, "model_validator"):

        @model_validator(mode="after")
        def check_consistency(self) -> RegisterDefinition:
            if self.type is not None:
                try:
                    reg_enum = RegisterType(self.type)
                except ValueError as err:
                    raise ValueError(f"unsupported type: {self.type}") from err
                expected = _TYPE_LENGTHS.get(reg_enum.value)
                if expected is None:
                    if self.length is None or self.length < 1:
                        raise ValueError("string type requires length >= 1")
                elif self.length != expected:
                    raise ValueError("length does not match type")

            _validate_enum_mapping(self.enum)
            _validate_bits_and_mask(self.bits, self.extra)
            _validate_numeric_bounds(self.min, self.max, self.default)
            return self

    else:

        @pydantic.root_validator
        def check_consistency(cls, values: dict[str, Any]) -> dict[str, Any]:
            reg_type = values.get("type")
            length = values.get("length")
            if reg_type is not None:
                try:
                    reg_enum = RegisterType(reg_type)
                except ValueError as err:
                    raise ValueError(f"unsupported type: {reg_type}") from err
                expected = _TYPE_LENGTHS.get(reg_enum.value)
                if expected is None:
                    if length is None or length < 1:
                        raise ValueError("string type requires length >= 1")
                elif length != expected:
                    raise ValueError("length does not match type")

            _validate_enum_mapping(values.get("enum"))
            _validate_bits_and_mask(values.get("bits"), values.get("extra"))
            _validate_numeric_bounds(values.get("min"), values.get("max"), values.get("default"))
            return values

    if hasattr(pydantic, "field_validator"):

        @pydantic.field_validator("name")
        @classmethod
        def name_is_snake(cls, v: str) -> str:
            if not re.fullmatch(r"[a-z0-9_]+", v):
                raise ValueError("name must be snake_case")
            return v

    else:

        @pydantic.validator("name")
        def name_is_snake(cls, v: str) -> str:
            if not re.fullmatch(r"[a-z0-9_]+", v):
                raise ValueError("name must be snake_case")
            return v


if hasattr(pydantic, "RootModel"):

    class RegisterList(RootModel[list[RegisterDefinition]]):  # type: ignore[valid-type,misc]
        """Container model to validate a list of registers."""

        @property
        def registers(self) -> list[RegisterDefinition]:
            return cast(list[RegisterDefinition], self.root)

        if hasattr(pydantic, "model_validator"):

            @model_validator(mode="after")
            def unique(self) -> RegisterList:
                registers = self.registers
                seen_pairs: set[tuple[int, int]] = set()
                seen_names: set[str] = set()
                for reg in registers:
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

else:

    class RegisterList(RootModel):  # type: ignore[no-redef,valid-type,misc]
        """Container model to validate a list of registers."""

        __root__: list[RegisterDefinition]

        @property
        def registers(self) -> list[RegisterDefinition]:
            return self.__root__

        @pydantic.root_validator
        def unique(cls, values: dict[str, Any]) -> dict[str, Any]:
            registers = values.get("__root__", [])
            seen_pairs: set[tuple[int, int]] = set()
            seen_names: set[str] = set()
            for reg in registers:
                fn = _normalise_function(reg.function)
                name = _normalise_name(reg.name)
                pair = (fn, reg.address_dec)
                if pair in seen_pairs:
                    raise ValueError(f"duplicate register pair: {pair}")
                if name in seen_names:
                    raise ValueError(f"duplicate register name: {name}")
                seen_pairs.add(pair)
                seen_names.add(name)
            return values
