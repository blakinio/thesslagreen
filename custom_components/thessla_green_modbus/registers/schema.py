"""Pydantic models describing register definitions.

This module validates the raw JSON register description bundled with the
integration.  The previous implementation had become a little tangled due to
multiple rounds of feature additions.  The file is rewritten here to add a few
new capabilities while keeping the validation logic focused and explicit.

Key features implemented:

* ``function`` accepts integers or strings and is normalised to the canonical
  integer form (``1`` … ``4``).
* ``address_dec`` may be provided as either an integer or string.  A canonical
  ``0x`` prefixed form is stored in ``address_hex`` and the two representations
  are cross‑checked for consistency.
* ``length`` accepts ``count`` as an alias.
* A top level ``type`` field is supported.  It accepts shorthand identifiers
  (``u16``, ``i16`` … ``f64``, ``string``, ``bitmask``) and the expected
  register count is enforced or defaulted.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

import pydantic
from pydantic import Field, model_validator, root_validator, validator

from ..utils import _normalise_name

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


class RegisterDefinition(pydantic.BaseModel):
    """Schema describing a raw register definition from JSON."""

    function: int
    address_dec: int
    address_hex: str
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

    class Config:  # pragma: no cover - keep behaviour aligned with v2 version
        extra = "allow"

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @root_validator(pre=True)
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
            if access in {"R/-", "R"}:
                data["access"] = "R"
            elif access in {"R/W", "RW"}:
                data["access"] = "RW"
            elif access == "W":
                data["access"] = "W"
            else:
                raise ValueError("access must be one of 'R', 'RW', 'W'")

        # Normalise address_dec
        addr_dec = data.get("address_dec")
        if addr_dec is not None:
            if isinstance(addr_dec, str):
                addr_dec = int(addr_dec, 0)
            elif not isinstance(addr_dec, int) or isinstance(addr_dec, bool):
                raise TypeError("address_dec must be int or str")
            data["address_dec"] = addr_dec

        # Normalise address_hex
        addr_hex = data.get("address_hex")
        if addr_hex is not None:
            if isinstance(addr_hex, str):
                addr_hex = addr_hex.lower()
                addr_hex = addr_hex[2:] if addr_hex.startswith("0x") else addr_hex
                addr_hex_int = int(addr_hex, 16)
            elif isinstance(addr_hex, int) and not isinstance(addr_hex, bool):
                addr_hex_int = addr_hex
            else:  # pragma: no cover - defensive
                raise TypeError("address_hex must be str or int")
            data["address_hex"] = hex(addr_hex_int)
        elif addr_dec is not None:
            data["address_hex"] = hex(addr_dec)

        # Handle type field (may be top level or inside extra)
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

        # Enforce/default length based on type
        typ = data.get("type")
        if typ is not None:
            if typ in {"uint", "int", "float"}:
                raise ValueError("type aliases are not allowed")
            expected = _TYPE_LENGTHS.get(typ)
            if expected is None:  # string type
                length = data.get("length")
                if length is None or length < 1:
                    raise ValueError("string type requires length >= 1")
            else:
                if "length" in data:
                    if data["length"] != expected:
                        raise ValueError("length does not match type")
                else:
                    data["length"] = expected

        if data.get("multiplier") is None:
            data["multiplier"] = 1
        if data.get("resolution") is None:
            data["resolution"] = 1

        return data

    @validator("function")
    def _check_function(cls, v: int) -> int:  # pragma: no cover - defensive
        if v not in {1, 2, 3, 4}:
            raise ValueError("function code must be between 1 and 4")
        return v

    @root_validator(skip_on_failure=True)
    def _check_access(cls, values: dict[str, Any]) -> dict[str, Any]:
        function = values.get("function")
        access = values.get("access")
        if function in {1, 2} and access != "R":
            raise ValueError("read-only functions must have R access")
        return values

    # ------------------------------------------------------------------
    # Additional consistency checks
    # ------------------------------------------------------------------

    @root_validator(skip_on_failure=True)
    def check_consistency(cls, values: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
        address_hex = values.get("address_hex")
        address_dec = values.get("address_dec")
        if address_hex is not None and address_dec is not None:
            if int(address_hex, 16) != address_dec:
                raise ValueError("address_hex does not match address_dec")

        reg_type = values.get("type")
        length = values.get("length")
        if reg_type is not None:
            try:
                reg_enum = RegisterType(reg_type)
            except ValueError as err:  # pragma: no cover - defensive
                raise ValueError(f"unsupported type: {reg_type}") from err
            expected = _TYPE_LENGTHS.get(reg_enum.value)
            if expected is None:
                if length is None or length < 1:
                    raise ValueError("string type requires length >= 1")
            elif length != expected:
                raise ValueError("length does not match type")

        enum_vals = values.get("enum")
        if enum_vals is not None:
            if not isinstance(enum_vals, dict):
                raise ValueError("enum must be a mapping")
            for k, v in enum_vals.items():
                try:
                    int(k)
                except (TypeError, ValueError):
                    raise ValueError("enum keys must be numeric") from None
                if not isinstance(v, str):
                    raise ValueError("enum values must be strings")

        bits = values.get("bits")
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

        extra = values.get("extra")
        bitmask_val = extra.get("bitmask") if isinstance(extra, dict) else None
        mask_int: int | None = None
        if isinstance(bitmask_val, str):
            try:
                mask_int = int(bitmask_val, 0)
            except ValueError:
                mask_int = None
        elif isinstance(bitmask_val, int) and not isinstance(bitmask_val, bool):
            mask_int = bitmask_val

        if mask_int is not None and max(seen_indices, default=-1) >= mask_int.bit_length():
            raise ValueError("bits exceed bitmask width")

        min_val = values.get("min")
        max_val = values.get("max")
        default_val = values.get("default")
        if min_val is not None and max_val is not None and min_val > max_val:
            raise ValueError("min greater than max")
        if default_val is not None:
            if min_val is not None and default_val < min_val:
                raise ValueError("default below min")
            if max_val is not None and default_val > max_val:
                raise ValueError("default above max")
        return values

    @validator("name")
    def name_is_snake(cls, v: str) -> str:  # pragma: no cover
        if not re.fullmatch(r"[a-z0-9_]+", v):
            raise ValueError("name must be snake_case")
        return v


class RegisterList(pydantic.RootModel[list[RegisterDefinition]]):
    """Container model to validate a list of registers."""

    root: list[RegisterDefinition]

    @model_validator(mode="after")
    def unique(self) -> "RegisterList":  # pragma: no cover
        registers = self.root
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
