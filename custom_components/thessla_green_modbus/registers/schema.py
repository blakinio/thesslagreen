from __future__ import annotations

"""Pydantic models describing register definitions.

This module validates the raw JSON register description bundled with the
integration.  The previous implementation had become a little tangled due to
multiple rounds of feature additions.  The file is rewritten here to add a few
new capabilities while keeping the validation logic focused and explicit.

Key features implemented:

* ``function`` and ``address_dec`` may be provided as either integers or
  strings (decimal or hexadecimal).  Values are normalised to integers and a
  canonical hexadecimal representation is stored in ``address_hex``.
* ``length`` accepts ``count`` as an alias.
* Shorthand type identifiers (``u16``, ``i16`` … ``f64``, ``string``,
  ``bitmask``) are mapped to the existing ``extra["type"]`` representation and
  the expected register word count is enforced.
"""

import re
from enum import Enum
from typing import Any, Literal

import pydantic

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

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @pydantic.model_validator(mode="before")
    @classmethod
    def _normalise_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Normalise raw input from JSON.

        * ``function`` and ``address_dec`` accept ``int`` or ``str`` (decimal or
          hexadecimal) and are converted to integers.  ``address_hex`` is
          canonicalised to a ``0x`` prefixed lowercase string.
        * ``count`` may be supplied instead of ``length``.
        * A top level ``type`` key is translated into ``extra['type']`` and the
          expected ``length`` is enforced or filled in.
        """

        # Allow ``count`` as an alias for ``length``
        if "count" in data and "length" not in data:
            data["length"] = data.pop("count")

        # Normalise function code
        if "function" in data:
            data["function"] = _normalise_function(data["function"])

        # Normalise address
        if "address_dec" in data:
            addr_dec = data["address_dec"]
            if isinstance(addr_dec, str):
                addr_dec = int(addr_dec, 0)
            elif not isinstance(addr_dec, int) or isinstance(addr_dec, bool):
                raise TypeError("address_dec must be int or str")
            data["address_dec"] = addr_dec

            # Canonical hex representation
            addr_hex = data.get("address_hex")
            if isinstance(addr_hex, int):
                addr_hex = hex(addr_hex)
            elif isinstance(addr_hex, str):
                addr_hex = hex(int(addr_hex, 0))
            else:
                addr_hex = hex(addr_dec)
            data["address_hex"] = addr_hex

        # Map shorthand ``type`` field
        typ = data.pop("type", None)
        if typ is not None:
            extra = data.setdefault("extra", {})
            extra["type"] = typ

        # Validate type and enforce/default length
        extra = data.get("extra") or {}
        typ = extra.get("type")
        if typ is not None:
            if typ in {"uint", "int", "float"}:
                raise ValueError("type aliases are not allowed")

            if typ in _TYPE_LENGTHS:
                expected = _TYPE_LENGTHS[typ]
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

        return data

    @pydantic.field_validator("function")
    @classmethod
    def _check_function(cls, v: int) -> int:  # pragma: no cover - defensive
        if not 1 <= v <= 4:
            raise ValueError("function code must be between 1 and 4")
        return v

    # ------------------------------------------------------------------
    # Additional consistency checks
    # ------------------------------------------------------------------

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
        if reg_type == RegisterType.STRING:
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
                raise ValueError("bits exceed 16 entries")

            seen_indices: set[int] = set()
            for bit in self.bits:
                if not isinstance(bit, dict):
                    raise ValueError("bits entries must be objects")
                if "index" not in bit or "name" not in bit:
                    raise ValueError("bits entries must have index and name")

                index = bit["index"]
                name = bit["name"]

                if not isinstance(index, int) or isinstance(index, bool):
                    raise ValueError("bit index must be an integer")
                if not 0 <= index <= 15:
                    raise ValueError("bit index out of range")
                if index in seen_indices:
                    raise ValueError("bit indices must be unique")
                seen_indices.add(index)

                if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]+", name):
                    raise ValueError("bit name must be snake_case")

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
            if mask_int is not None and max(seen_indices, default=-1) >= mask_int.bit_length():
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

