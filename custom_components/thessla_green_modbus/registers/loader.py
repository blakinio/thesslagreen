"""Loader for Modbus register definitions.

This module reads the bundled ``thessla_green_registers_full.json`` file and
exposes a small helper API used by the integration and the tests.  The JSON file
contains the canonical list of registers together with metadata describing how a
raw register value should be interpreted.

Only a fairly small subset of the original project is required for the unit
tests in this kata, therefore the implementation below purposely focuses on the
features that are exercised in the tests: parsing of the JSON file, decoding of
values using ``enum``/``multiplier``/``resolution`` information, optional BCD
time handling for schedule registers and grouping of addresses for efficient
reads.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import struct
import importlib.resources as resources
from dataclasses import dataclass
from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Sequence

import pydantic

from ..schedule_helpers import bcd_to_time, time_to_bcd
from ..utils import _to_snake_case

_LOGGER = logging.getLogger(__name__)

# Path to the bundled register definition file.  Tests patch this constant to
# supply temporary files, therefore it must be a module level variable instead
# of being computed inside helper functions.
_REGISTERS_PATH = resources.files(__package__).joinpath(
    "thessla_green_registers_full.json"
)
# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Register:
    """Definition of a single Modbus register."""

    function: str
    address: int
    name: str
    access: str
    description: str | None = None
    unit: str | None = None
    multiplier: float | None = None
    resolution: float | None = None
    min: float | None = None
    max: float | None = None
    default: float | None = None
    enum: dict[int | str, Any] | None = None
    notes: str | None = None
    information: str | None = None
    extra: dict[str, Any] | None = None
    length: int = 1
    bcd: bool = False

    # ------------------------------------------------------------------
    # Value helpers
    # ------------------------------------------------------------------
    def decode(self, raw: int | Sequence[int]) -> Any:
        """Decode ``raw`` according to the register metadata."""

        if self.length > 1 and isinstance(raw, Sequence):
            raw_list = list(raw)
            if all(v == 0x8000 for v in raw_list):
                return None

            if self.extra and self.extra.get("type") == "string":
                encoding = self.extra.get("encoding", "ascii")
                data = bytearray()
                for word in raw_list:
                    data.extend(word.to_bytes(2, "big"))
                return data.rstrip(b"\x00").decode(encoding)

            endianness = "big"
            if self.extra:
                endianness = self.extra.get("endianness", "big")
            words = raw_list if endianness == "big" else list(reversed(raw_list))
            data = b"".join(w.to_bytes(2, "big") for w in words)

            typ = self.extra.get("type") if self.extra else None
            if typ == "float32":
                value = struct.unpack(">f" if endianness == "big" else "<f", data)[0]
            elif typ == "float64":
                value = struct.unpack(">d" if endianness == "big" else "<d", data)[0]
            elif typ == "int32":
                value = int.from_bytes(data, "big", signed=True)
            elif typ == "uint32":
                value = int.from_bytes(data, "big", signed=False)
            else:
                value = int.from_bytes(data, "big", signed=False)

            if self.multiplier is not None:
                value = value * self.multiplier
            if self.resolution is not None:
                steps = round(value / self.resolution)
                value = steps * self.resolution
            return value

        if isinstance(raw, Sequence):
            # Defensive: unexpected sequence for single register
            raw = raw[0]

        if raw == 0x8000:
            return None

        if self.extra and self.extra.get("bitmask") and self.enum:
            flags: list[Any] = []
            for key, label in sorted(
                ((int(k), v) for k, v in self.enum.items()), key=lambda x: x[0]
            ):
                if raw & key:
                    flags.append(label)
            return flags

        if self.enum is not None:
            if raw in self.enum:
                return self.enum[raw]
            if str(raw) in self.enum:
                return self.enum[str(raw)]

        value: Any = raw
        if self.length > 1 and self.extra and self.extra.get("type"):
            dtype = self.extra["type"]
            byte_len = self.length * 2
            raw_bytes = raw.to_bytes(byte_len, "big", signed=False)
            if dtype == "float32":
                value = struct.unpack(">f", raw_bytes)[0]
            elif dtype == "int32":
                value = struct.unpack(">i", raw_bytes)[0]
            elif dtype == "uint32":
                value = struct.unpack(">I", raw_bytes)[0]
            elif dtype == "int64":
                value = struct.unpack(">q", raw_bytes)[0]
            elif dtype == "uint64":
                value = struct.unpack(">Q", raw_bytes)[0]
        if self.multiplier is not None:
            value = value * self.multiplier
        if self.resolution is not None:
            steps = round(value / self.resolution)
            value = steps * self.resolution

        if self.extra and self.extra.get("aatt"):
            airflow = (raw >> 8) & 0xFF
            temp = (raw & 0xFF) / 2
            return airflow, temp

        if self.bcd:
            try:
                t = bcd_to_time(raw)
            except Exception:  # pragma: no cover - defensive
                return value
            return f"{t.hour:02d}:{t.minute:02d}"

        return value

    def encode(self, value: Any) -> int | list[int]:
        """Encode ``value`` into the raw register representation."""

        if self.length > 1:
            if self.extra and self.extra.get("type") == "string":
                encoding = self.extra.get("encoding", "ascii")
                data = str(value).encode(encoding)
                data = data.ljust(self.length * 2, b"\x00")
                return [int.from_bytes(data[i:i+2], "big") for i in range(0, self.length * 2, 2)]

            endianness = "big"
            if self.extra:
                endianness = self.extra.get("endianness", "big")

            raw_val: Any = value
            if self.enum and isinstance(value, str):
                for k, v in self.enum.items():
                    if v == value:
                        raw_val = int(k)
                        break
            if self.multiplier is not None:
                raw_val = int(round(float(raw_val) / self.multiplier))
            if self.resolution is not None:
                step = self.resolution
                raw_val = int(round(float(raw_val) / step) * step)

            typ = self.extra.get("type") if self.extra else None
            if typ == "float32":
                data = struct.pack(">f" if endianness == "big" else "<f", float(raw_val))
            elif typ == "float64":
                data = struct.pack(">d" if endianness == "big" else "<d", float(raw_val))
            elif typ == "int32":
                data = int(raw_val).to_bytes(4, "big", signed=True)
            elif typ == "uint32":
                data = int(raw_val).to_bytes(4, "big", signed=False)
            else:
                data = int(raw_val).to_bytes(self.length * 2, "big", signed=False)

            words = [int.from_bytes(data[i:i+2], "big") for i in range(0, len(data), 2)]
            if endianness == "little":
                words = list(reversed(words))
            return words

        if self.extra and self.extra.get("bitmask") and self.enum:
            raw_int = 0
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    for k, v in self.enum.items():
                        if v == item:
                            raw_int |= int(k)
                            break
                return raw_int
            if isinstance(value, str):
                for k, v in self.enum.items():
                    if v == value:
                        return int(k)
            return int(value)

        if self.bcd:
            if isinstance(value, str):
                hours, minutes = (int(x) for x in value.split(":"))
            elif isinstance(value, int):
                hours, minutes = divmod(value, 60)
            elif isinstance(value, (tuple, list)):
                hours, minutes = int(value[0]), int(value[1])
            else:  # pragma: no cover - defensive
                raise ValueError(f"Unsupported BCD value: {value}")
            return time_to_bcd(time(hours, minutes))

        if self.extra and self.extra.get("aatt"):
            airflow, temp = (
                value if isinstance(value, (list, tuple)) else (value["airflow"], value["temp"])
            )  # type: ignore[index]
            return (int(airflow) << 8) | (int(round(float(temp) * 2)) & 0xFF)

        raw: Any = value
        if self.enum and isinstance(value, str):
            for k, v in self.enum.items():
                if v == value:
                    raw = int(k)
                    break
        if self.multiplier is not None:
            raw = int(round(float(raw) / self.multiplier))
        if self.resolution is not None:
            step = self.resolution
            raw = int(round(float(raw) / step) * step)
        if self.length > 1 and self.extra and self.extra.get("type"):
            dtype = self.extra["type"]
            if dtype == "float32":
                return int.from_bytes(struct.pack(">f", float(raw)), "big")
            if dtype == "int32":
                return int.from_bytes(struct.pack(">i", int(raw)), "big")
            if dtype == "uint32":
                return int.from_bytes(struct.pack(">I", int(raw)), "big")
            if dtype == "int64":
                return int.from_bytes(struct.pack(">q", int(raw)), "big")
            if dtype == "uint64":
                return int.from_bytes(struct.pack(">Q", int(raw)), "big")
        return int(raw)


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

_SPECIAL_MODES_PATH = Path(__file__).resolve().parents[1] / "options" / "special_modes.json"
try:  # pragma: no cover - defensive
    _SPECIAL_MODES_ENUM = {
        key.split("_")[-1]: idx
        for idx, key in enumerate(json.loads(_SPECIAL_MODES_PATH.read_text()))
    }
except Exception:  # pragma: no cover - defensive
    _SPECIAL_MODES_ENUM: dict[str, int] = {}


def _normalise_function(fn: str) -> str:
    mapping = {
        # Function code 01: coils
        "01": "01",
        "1": "01",
        "coil": "01",
        "coil register": "01",
        "coil registers": "01",
        "coil_register": "01",
        "coil_registers": "01",
        "coils": "01",
        # Function code 02: discrete inputs
        "02": "02",
        "2": "02",
        "discrete": "02",
        "discrete input": "02",
        "discrete inputs": "02",
        "discrete_input": "02",
        "discrete_inputs": "02",
        "discreteinput": "02",
        "discreteinputs": "02",
        # Function code 03: holding registers
        "03": "03",
        "3": "03",
        "holding": "03",
        "holding register": "03",
        "holding registers": "03",
        "holding_register": "03",
        "holding_registers": "03",
        "holdingregister": "03",
        "holdingregisters": "03",
        # Function code 04: input registers
        "04": "04",
        "4": "04",
        "input": "04",
        "input register": "04",
        "input registers": "04",
        "input_register": "04",
        "input_registers": "04",
        "inputregister": "04",
        "inputregisters": "04",
    }
    return mapping.get(fn.lower(), fn)


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
    min: float | None = None
    max: float | None = None
    default: float | None = None
    notes: str | None = None
    information: str | None = None
    extra: dict[str, Any] | None = None
    length: int = 1
    bcd: bool = False

    # ``model_config`` and the validators below are used by Pydantic at runtime
    # to validate register definitions.  They appear unused to vulture because
    # they are referenced through Pydantic's internal mechanisms.
    model_config = pydantic.ConfigDict(extra="allow")

    @pydantic.model_validator(mode="after")
    def check_address(self) -> "RegisterDefinition":
        if int(self.address_hex, 16) != self.address_dec:
            raise ValueError("address_hex does not match address_dec")
        return self

    @pydantic.field_validator("name")
    @classmethod
    def name_is_snake(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]+", v):
            raise ValueError("name must be snake_case")
        return v


def _normalise_name(name: str) -> str:
    """Convert register names to ``snake_case`` and fix known typos."""

    fixes = {
        "duct_warter_heater_pump": "duct_water_heater_pump",
        "required_temp": "required_temperature",
        "specialmode": "special_mode",
    }
    snake = _to_snake_case(name)
    return fixes.get(snake, snake)



# ---------------------------------------------------------------------------
# Register loading helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_registers_from_file(
    path: Path, *, file_hash: str
) -> list[Register]:
    """Load register definitions from ``path``.

    ``file_hash`` is only used to invalidate the cache when the underlying file
    content changes.  It is marked as a keyword-only argument to ensure callers
    pass it explicitly which makes the intention clearer.
    """

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:  # pragma: no cover - sanity check
        _LOGGER.error("Register definition file missing: %s", path)
        return []
    except Exception:  # pragma: no cover - defensive
        _LOGGER.exception("Failed to read register definitions from %s", path)
        return []

    items = raw.get("registers", raw) if isinstance(raw, dict) else raw

    registers: list[Register] = []
    seen_pairs: set[tuple[str, int]] = set()
    seen_names: set[str] = set()

    for item in items:
        parsed = RegisterDefinition.model_validate(item)

        function = _normalise_function(parsed.function)
        raw_address = int(parsed.address_dec)

        address = raw_address
        if function == "02":
            address -= 1
        elif function == "03" and address >= 111:
            address -= 111

        name = _normalise_name(parsed.name)

        pair = (function, raw_address)
        if pair in seen_pairs:
            raise ValueError(f"duplicate register pair: {pair}")
        if name in seen_names:
            raise ValueError(f"duplicate register name: {name}")
        seen_pairs.add(pair)
        seen_names.add(name)

        enum_map = parsed.enum
        if name == "special_mode":
            enum_map = _SPECIAL_MODES_ENUM
        elif enum_map:
            if all(isinstance(k, (int, float)) or str(k).isdigit() for k in enum_map):
                enum_map = {int(k): v for k, v in enum_map.items()}
            elif all(
                isinstance(v, (int, float)) or str(v).isdigit() for v in enum_map.values()
            ):
                enum_map = {int(v): k for k, v in enum_map.items()}

        multiplier = parsed.multiplier
        resolution = parsed.resolution

        registers.append(
            Register(
                function=function,
                address=address,
                name=name,
                access=str(parsed.access),
                description=parsed.description,
                unit=parsed.unit,
                multiplier=multiplier,
                resolution=resolution,
                min=parsed.min,
                max=parsed.max,
                default=parsed.default,
                enum=enum_map,
                notes=parsed.notes,
                information=parsed.information,
                extra=parsed.extra,
                length=int(parsed.length),
                bcd=bool(parsed.bcd),
            )
        )

    return registers


def _compute_file_hash() -> str:
    """Return the SHA256 hash of the registers file."""

    return hashlib.sha256(_REGISTERS_PATH.read_bytes()).hexdigest()


def _load_registers() -> list[Register]:
    """Return cached register definitions, reloading if the file changed."""

    file_hash = _compute_file_hash()
    return _load_registers_from_file(_REGISTERS_PATH, file_hash=file_hash)


def clear_cache() -> None:
    """Clear the register definition cache.

    Exposed for tests and tooling that need to reload register
    definitions.
    """

    _load_registers_from_file.cache_clear()


# Load register definitions once at import time
_load_registers()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_all_registers() -> list[Register]:
    """Return a list of all known registers."""
    return list(_load_registers())


def get_registers_by_function(fn: str) -> list[Register]:
    """Return registers for the given function code or name."""
    code = _normalise_function(fn)
    return [r for r in _load_registers() if r.function == code]


def get_registers_hash() -> str:
    """Return the hash of the currently loaded register file."""
    try:
        return _compute_file_hash()
    except Exception:  # pragma: no cover - defensive
        return ""


@dataclass(slots=True)
class ReadPlan:
    """Plan describing a consecutive block of registers to read."""

    function: str
    address: int
    length: int


def group_reads(max_block_size: int = 64) -> list[ReadPlan]:
    """Group registers into contiguous blocks for efficient reading."""

    plans: list[ReadPlan] = []
    regs_by_fn: dict[str, list[int]] = {}

    for reg in _load_registers():
        addresses = list(range(reg.address, reg.address + reg.length))
        regs_by_fn.setdefault(reg.function, []).extend(addresses)

    for fn, addresses in regs_by_fn.items():
        addresses.sort()
        start = prev = addresses[0]
        length = 1
        for addr in addresses[1:]:
            if addr == prev + 1 and length < max_block_size:
                length += 1
            else:
                plans.append(ReadPlan(fn, start, length))
                start = addr
                length = 1
            prev = addr
        plans.append(ReadPlan(fn, start, length))

    return plans


__all__ = [
    "Register",
    "RegisterDefinition",
    "ReadPlan",
    "get_all_registers",
    "get_registers_by_function",
    "get_registers_hash",
    "group_reads",
]
