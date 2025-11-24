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
import importlib.resources as resources
import json
import logging
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

# Shared grouping helper
from ..modbus_helpers import group_reads
from ..schedule_helpers import bcd_to_time, time_to_bcd
from .schema import RegisterList, _normalise_function, _normalise_name

_LOGGER = logging.getLogger(__name__)

# Path to the bundled register definition file.  Tests patch this constant to
# supply temporary files, therefore it must be a module level variable instead
# of being computed inside helper functions.
_REGISTERS_PATH = Path(
    str(resources.files(__package__).joinpath("thessla_green_registers_full.json"))
)


def get_registers_path() -> Path:
    """Return resolved path to the bundled register definitions JSON file."""
    return _REGISTERS_PATH.resolve()


# Cache for file metadata keyed by path. Each entry stores ``(mtime, sha256)``
# for the most recently seen state of that file.  A second cache keyed by
# ``(sha256, mtime)`` stores the parsed register definitions so repeated loads of
# unchanged files avoid both hashing and JSON parsing.
_cached_file_info: dict[str, tuple[float, str]] = {}
_register_cache: dict[tuple[str, float], list[RegisterDef]] = {}


def _compute_file_hash(path: Path, mtime: float) -> str:
    """Return SHA256 digest for ``path`` and update the cache."""

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _cached_file_info[str(path)] = (mtime, digest)
    return digest


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RegisterDef:
    """Definition of a single Modbus register."""

    function: int
    address: int
    name: str
    access: str
    description: str | None = None
    description_en: str | None = None
    unit: str | None = None
    multiplier: float = 1
    resolution: float = 1
    min: float | None = None
    max: float | None = None
    default: float | None = None
    enum: dict[int | str, Any] | None = None
    notes: str | None = None
    information: str | None = None
    extra: dict[str, Any] | None = None
    length: int = 1
    bcd: bool = False
    bits: list[Any] | None = None

    # ------------------------------------------------------------------
    # Value helpers
    # ------------------------------------------------------------------
    def decode(self, raw: int | Sequence[int]) -> Any:
        """Decode ``raw`` according to the register metadata."""
        value: Any
        if self.length > 1:
            if isinstance(raw, Sequence):
                raw_list = list(raw)
            else:
                raw_list = [
                    (raw >> (16 * (self.length - 1 - i))) & 0xFFFF for i in range(self.length)
                ]

            if all(v == 0x8000 for v in raw_list):
                return None

            # Multi-register strings are treated specially
            if self.extra and self.extra.get("type") == "string":
                encoding = self.extra.get("encoding", "ascii")
                data = b"".join(w.to_bytes(2, "big") for w in raw_list)
                return data.rstrip(b"\x00").decode(encoding)

            endianness = self.extra.get("endianness", "big") if self.extra else "big"
            words = raw_list if endianness == "big" else list(reversed(raw_list))
            data = b"".join(w.to_bytes(2, "big") for w in words)

            typ = self.extra.get("type") if self.extra else None
            if typ in {"f32", "f64"}:
                fmt = ">" if endianness == "big" else "<"
                fmt += "f" if typ == "f32" else "d"
                value = struct.unpack(fmt, data)[0]
            elif typ in {"i32", "u32", "i64", "u64"}:
                value = int.from_bytes(data, "big", signed=typ.startswith("i"))
            else:
                value = int.from_bytes(data, "big", signed=False)

            if self.multiplier not in (None, 1):
                value *= self.multiplier
            if self.resolution not in (None, 1):
                steps = round(value / self.resolution)
                value = steps * self.resolution
            return value

        # Defensive: handle unexpected sequence for single-register values
        if isinstance(raw, Sequence):
            raw = raw[0]

        if raw == 0x8000:
            return None

        # Bitmask registers map set bits to enum labels
        if self.extra and self.extra.get("bitmask") and self.enum:
            flags: list[Any] = []
            for key, label in sorted(
                ((int(k), v) for k, v in self.enum.items()), key=lambda x: x[0]
            ):
                if raw & key:
                    flags.append(label)
            return flags

        # Regular enum registers return the mapped label
        if self.enum is not None:
            if raw in self.enum:
                return self.enum[raw]
            if str(raw) in self.enum:
                return self.enum[str(raw)]

        typ = self.extra.get("type") if self.extra else None
        if typ == "i16":
            raw = raw if raw < 0x8000 else raw - 0x10000

        value = raw

        # Combined airflow/temperature values use a custom decoding
        if self.extra and self.extra.get("aatt"):
            airflow = (raw >> 8) & 0xFF
            temp = (raw & 0xFF) / 2
            return airflow, temp

        # Schedule registers using BCD time encoding
        if self.bcd:
            try:
                t = bcd_to_time(raw)
            except Exception:  # pragma: no cover - defensive
                pass
            else:
                return f"{t.hour:02d}:{t.minute:02d}"

        if self.multiplier not in (None, 1):
            value *= self.multiplier
        if self.resolution not in (None, 1):
            steps = round(value / self.resolution)
            value = steps * self.resolution
        return value

    def encode(self, value: Any) -> int | list[int]:
        """Encode ``value`` into the raw register representation."""

        if self.length > 1:
            if self.extra and self.extra.get("type") == "string":
                encoding = self.extra.get("encoding", "ascii")
                data = str(value).encode(encoding)
                data = data.ljust(self.length * 2, b"\x00")
                return [
                    int.from_bytes(data[i : i + 2], "big") for i in range(0, self.length * 2, 2)
                ]

            endianness = "big"
            if self.extra:
                endianness = self.extra.get("endianness", "big")

            raw_val: Any = value
            if self.enum:
                if isinstance(value, str):
                    for k, v in self.enum.items():
                        if v == value:
                            raw_val = int(k)
                            break
                    else:
                        raise ValueError(f"Invalid enum value {value!r} for {self.name}")
                elif value not in self.enum and str(value) not in self.enum:
                    raise ValueError(f"Invalid enum value {value!r} for {self.name}")

            try:
                num_val = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                num_val = None
            if num_val is not None:
                if self.min is not None and num_val < Decimal(str(self.min)):
                    raise ValueError(f"{value} is below minimum {self.min} for {self.name}")
                if self.max is not None and num_val > Decimal(str(self.max)):
                    raise ValueError(f"{value} is above maximum {self.max} for {self.name}")
                scaled = Decimal(str(raw_val))
                if self.resolution not in (None, 1):
                    step = Decimal(str(self.resolution))
                    scaled = (scaled / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
                if self.multiplier not in (None, 1):
                    mult = Decimal(str(self.multiplier))
                    scaled = (scaled / mult).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                raw_val = scaled

            typ = self.extra.get("type") if self.extra else None
            if typ == "f32":
                data = struct.pack(">f" if endianness == "big" else "<f", float(raw_val))
            elif typ == "f64":
                data = struct.pack(">d" if endianness == "big" else "<d", float(raw_val))
            elif typ in {"i32", "u32", "i64", "u64"}:
                size = 4 if typ in {"i32", "u32"} else 8
                data = int(raw_val).to_bytes(size, "big", signed=typ.startswith("i"))
            else:
                data = int(raw_val).to_bytes(self.length * 2, "big", signed=False)

            words = [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)]
            if endianness == "little":
                words = list(reversed(words))
            return words

        if self.extra and self.extra.get("bitmask") and self.enum:
            raw_int = 0
            if isinstance(value, list | tuple | set):
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
            elif isinstance(value, tuple | list):
                hours, minutes = int(value[0]), int(value[1])
            else:  # pragma: no cover - defensive
                raise ValueError(f"Unsupported BCD value: {value}")
            return int(time_to_bcd(time(hours, minutes)))

        if self.extra and self.extra.get("aatt"):
            airflow, temp = (
                value if isinstance(value, list | tuple) else (value["airflow"], value["temp"])
            )
            return (int(airflow) << 8) | (int(round(float(temp) * 2)) & 0xFF)

        raw: Any = value
        if self.enum and not (self.extra and self.extra.get("bitmask")):
            if isinstance(value, str):
                for k, v in self.enum.items():
                    if v == value:
                        raw = int(k)
                        break
                else:
                    raise ValueError(f"Invalid enum value {value!r} for {self.name}")
            elif value in self.enum or str(value) in self.enum:
                raw = int(value)
            else:
                raise ValueError(f"Invalid enum value {value!r} for {self.name}")

        try:
            num_val = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            num_val = None
        if num_val is not None:
            if self.min is not None and num_val < Decimal(str(self.min)):
                raise ValueError(f"{value} is below minimum {self.min} for {self.name}")
            if self.max is not None and num_val > Decimal(str(self.max)):
                raise ValueError(f"{value} is above maximum {self.max} for {self.name}")
            scaled = Decimal(str(raw))
            if self.resolution not in (None, 1):
                step = Decimal(str(self.resolution))
                scaled = (scaled / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
            if self.multiplier not in (None, 1):
                mult = Decimal(str(self.multiplier))
                scaled = (scaled / mult).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            raw = scaled
        typ = self.extra.get("type") if self.extra else None
        if typ == "i16":
            return int(raw) & 0xFFFF
        return int(raw)


# Backwards compatible alias used throughout the project/tests
Register = RegisterDef

# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

_SPECIAL_MODES_PATH = Path(__file__).resolve().parents[1] / "options" / "special_modes.json"
_SPECIAL_MODES_ENUM: dict[str, int] = {}
try:  # pragma: no cover - defensive
    _SPECIAL_MODES_ENUM = {
        key.split("_")[-1]: idx
        for idx, key in enumerate(json.loads(_SPECIAL_MODES_PATH.read_text()))
    }
except (OSError, json.JSONDecodeError, ValueError) as err:  # pragma: no cover - defensive
    _LOGGER.debug("Failed to load special modes: %s", err)
    _SPECIAL_MODES_ENUM = {}
except Exception as err:  # pragma: no cover - unexpected
    _LOGGER.exception("Unexpected error loading special modes: %s", err)
    _SPECIAL_MODES_ENUM = {}


# ---------------------------------------------------------------------------
# Register loading helpers
# ---------------------------------------------------------------------------


def _load_registers_from_file(path: Path, *, mtime: float, file_hash: str) -> list[RegisterDef]:
    """Load register definitions from ``path``.

    ``mtime`` and ``file_hash`` are accepted for backwards compatibility with
    tests that spy on cache behaviour.  They do not influence the parsing
    directly; caching is handled in ``load_registers`` using these values.
    """

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:  # pragma: no cover - sanity check
        raise RuntimeError(f"Register definition file missing: {path}") from err
    except Exception as err:  # pragma: no cover - defensive
        raise RuntimeError(f"Failed to read register definitions from {path}") from err

    items = raw.get("registers", raw) if isinstance(raw, dict) else raw

    registers: list[RegisterDef] = []
    parsed_items = RegisterList.parse_obj(items).__root__

    for parsed in parsed_items:
        function = _normalise_function(parsed.function)
        raw_address = int(parsed.address_dec)

        address = raw_address
        if function == 2:
            address -= 1
        elif function == 3 and address >= 111:
            address -= 111

        name = _normalise_name(parsed.name)

        enum_map: dict[int | str, Any] | None = cast(dict[int | str, Any] | None, parsed.enum)
        if name == "special_mode":
            enum_map = cast(dict[int | str, Any], _SPECIAL_MODES_ENUM)
        elif enum_map:
            if all(isinstance(k, int | float) or str(k).isdigit() for k in enum_map):
                enum_map = cast(dict[int | str, Any], {int(k): v for k, v in enum_map.items()})
            elif all(isinstance(v, int | float) or str(v).isdigit() for v in enum_map.values()):
                enum_map = cast(dict[int | str, Any], {int(v): k for k, v in enum_map.items()})

        # ``multiplier`` and ``resolution`` are optional in the JSON.  The
        # dataclass defaults to ``1`` for both fields but passing ``None`` would
        # override that default and propagate ``None`` through the rest of the
        # code.  Coercing ``None`` to ``1`` here keeps the values consistent and
        # avoids ``Optional`` types downstream.
        multiplier = 1 if parsed.multiplier is None else float(parsed.multiplier)
        resolution = 1 if parsed.resolution is None else float(parsed.resolution)

        registers.append(
            RegisterDef(
                function=function,
                address=address,
                name=name,
                access=str(parsed.access),
                description=parsed.description,
                description_en=parsed.description_en,
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
                bits=parsed.bits,
            )
        )

    return registers


def registers_sha256(json_path: Path | str) -> str:
    """Return the SHA256 hash of ``json_path``.

    The result is cached using the file's modification time so repeated calls
    for an unchanged file avoid re-reading from disk.
    """

    path = Path(json_path)
    mtime = path.stat().st_mtime
    path_str = str(path)
    cached = _cached_file_info.get(path_str)
    if cached and cached[0] == mtime:
        return cached[1]

    return _compute_file_hash(path, mtime)


def load_registers(json_path: Path | str | None = None) -> list[RegisterDef]:
    """Return cached register definitions, reloading if the file changed.

    ``json_path`` may be provided to load register definitions from an
    alternate file. When omitted, the bundled definitions are used.

    The cache key derives from the tuple ``(sha256(content), mtime)`` so
    changes to either timestamp or content trigger a reload regardless of the
    path used.
    """

    path = Path(json_path) if json_path is not None else _REGISTERS_PATH
    file_hash = registers_sha256(path)
    mtime = _cached_file_info[str(path)][0]
    key = (file_hash, mtime)
    regs = _register_cache.get(key)
    if regs is None:
        regs = _load_registers_from_file(path, mtime=mtime, file_hash=file_hash)
        _register_cache[key] = regs
    return regs


def clear_cache() -> None:  # pragma: no cover
    """Clear the register definition cache.

    Exposed for tests and tooling that need to reload register
    definitions.
    """
    _cached_file_info.clear()
    _register_cache.clear()
    _register_map.cache_clear()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_all_registers(json_path: Path | str | None = None) -> list[RegisterDef]:
    """Return all known registers ordered by function and address."""
    return sorted(load_registers(json_path), key=lambda r: (r.function, r.address))


def get_registers_by_function(fn: str, json_path: Path | str | None = None) -> list[RegisterDef]:
    """Return registers for the given function code or name."""
    code = _normalise_function(fn)
    return [r for r in load_registers(json_path) if r.function == code]


@lru_cache(maxsize=1)
def _register_map() -> dict[str, RegisterDef]:
    return {r.name: r for r in load_registers()}


def get_register_definition(name: str) -> RegisterDef:
    """Return definition for register ``name``."""
    return _register_map()[name]


@dataclass(slots=True)
class ReadPlan:
    """Plan describing a consecutive block of registers to read."""

    function: int
    address: int
    length: int


def plan_group_reads(max_block_size: int | None = None) -> list[ReadPlan]:
    """Group registers into contiguous blocks for efficient reading."""

    if max_block_size is None:
        from ..const import MAX_BATCH_REGISTERS

        max_block_size = MAX_BATCH_REGISTERS

    regs_by_fn: dict[int, list[int]] = {}
    for reg in load_registers():
        addr_range = range(reg.address, reg.address + reg.length)
        regs_by_fn.setdefault(reg.function, []).extend(addr_range)

    plans: list[ReadPlan] = []
    for fn, addresses in regs_by_fn.items():
        for start, length in group_reads(addresses, max_block_size=max_block_size):
            plans.append(ReadPlan(fn, start, length))

    return plans
