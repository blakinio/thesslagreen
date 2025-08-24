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
from dataclasses import dataclass
from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

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
# Cache for the last (path, mtime, hash) triple of the registers file.  The
# hash is only recomputed when either the path or ``mtime`` changes.
_cached_file_info: tuple[str, float, str] | None = None
# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RegisterDef:
    """Definition of a single Modbus register."""

    function: str
    address: int
    name: str
    access: str
    description: str | None = None
    description_en: str | None = None
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
    bits: list[Any] | None = None


# ------------------------------------------------------------------
# Value helpers
# ------------------------------------------------------------------
    def decode(self, raw: int | Sequence[int]) -> Any:
        """Decode ``raw`` according to the register metadata."""
        if self.length > 1 and isinstance(raw, Sequence):
            raw_list = list(raw)
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
            if typ == "float32":
                value = struct.unpack(">f" if endianness == "big" else "<f", data)[0]
            elif typ == "float64":
                value = struct.unpack(">d" if endianness == "big" else "<d", data)[0]
            elif typ == "int32":
                value = int.from_bytes(data, "big", signed=True)
            elif typ == "uint32":
                value = int.from_bytes(data, "big", signed=False)
            elif typ == "int64":
                value = int.from_bytes(data, "big", signed=True)
            elif typ == "uint64":
                value = int.from_bytes(data, "big", signed=False)
            else:
                value = int.from_bytes(data, "big", signed=False)

            if self.multiplier is not None:
                value *= self.multiplier
            if self.resolution is not None:
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

        # Combined airflow/temperature values use a custom decoding
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

        if self.multiplier is not None:
            value *= self.multiplier
        if self.resolution is not None:
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
            elif typ == "int64":
                data = int(raw_val).to_bytes(8, "big", signed=True)
            elif typ == "uint64":
                data = int(raw_val).to_bytes(8, "big", signed=False)
            else:
                data = int(raw_val).to_bytes(self.length * 2, "big", signed=False)

            words = [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)]
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
            return int(time_to_bcd(time(hours, minutes)))

        if self.extra and self.extra.get("aatt"):
            airflow, temp = (
                value if isinstance(value, (list, tuple)) else (value["airflow"], value["temp"])
            )
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


@lru_cache(maxsize=1)
def _load_registers_from_file(
    path: Path, *, mtime: float, file_hash: str
) -> list[RegisterDef]:
    """Load register definitions from ``path``.

    ``mtime`` and ``file_hash`` participate in the cache key so the file is
    reloaded only when its timestamp or contents change.
    """

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:  # pragma: no cover - sanity check
        raise RuntimeError(f"Register definition file missing: {path}") from err
    except Exception as err:  # pragma: no cover - defensive
        raise RuntimeError(f"Failed to read register definitions from {path}") from err

    items = raw.get("registers", raw) if isinstance(raw, dict) else raw

    registers: list[RegisterDef] = []
    parsed_items = RegisterList.model_validate(items).root

    for parsed in parsed_items:
        function = _normalise_function(parsed.function)
        raw_address = int(parsed.address_dec)

        address = raw_address
        if function == "02":
            address -= 1
        elif function == "03" and address >= 111:
            address -= 111

        name = _normalise_name(parsed.name)

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


def _compute_file_hash(path: Path, mtime: float) -> str:
    """Return the SHA256 hash of ``path``.

    Results are cached based on the file path and modification time so repeated
    calls for an unchanged file avoid reading from disk.
    """

    global _cached_file_info
    path_str = str(path)
    if (
        _cached_file_info
        and _cached_file_info[0] == path_str
        and _cached_file_info[1] == mtime
    ):
        return _cached_file_info[2]

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _cached_file_info = (path_str, mtime, digest)
    return digest


def _get_file_info() -> tuple[float, str]:
    """Return ``(mtime, hash)`` for the bundled registers file.

    ``_compute_file_hash`` is only invoked when the modification time changes so
    repeated calls avoid both hashing and disk access.
    """

    stat = _REGISTERS_PATH.stat()
    mtime = stat.st_mtime
    path_str = str(_REGISTERS_PATH)

    if (
        _cached_file_info
        and _cached_file_info[0] == path_str
        and _cached_file_info[1] == mtime
    ):
        return mtime, _cached_file_info[2]

    file_hash = _compute_file_hash(_REGISTERS_PATH, mtime)
    return mtime, file_hash


def load_registers() -> list[RegisterDef]:
    """Return cached register definitions, reloading if the file changed."""

    mtime, file_hash = _get_file_info()
    return _load_registers_from_file(
        _REGISTERS_PATH, mtime=mtime, file_hash=file_hash
    )


def clear_cache() -> None:  # pragma: no cover
    """Clear the register definition cache.

    Exposed for tests and tooling that need to reload register
    definitions.
    """
    global _cached_file_info
    _cached_file_info = None
    _load_registers_from_file.cache_clear()
    _register_map.cache_clear()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_all_registers() -> list[RegisterDef]:
    """Return a list of all known registers ordered by function and address."""
    return sorted(load_registers(), key=lambda r: (r.function, r.address))


def get_registers_by_function(fn: str) -> list[RegisterDef]:
    """Return registers for the given function code or name."""
    code = _normalise_function(fn)
    return [r for r in load_registers() if r.function == code]


def get_registers_hash() -> str:
    """Return the hash of the currently loaded register file."""
    try:
        return _get_file_info()[1]
    except Exception:  # pragma: no cover - defensive
        return ""


@lru_cache(maxsize=1)
def _register_map() -> dict[str, RegisterDef]:
    return {r.name: r for r in load_registers()}


def get_register_definition(name: str) -> RegisterDef:
    """Return definition for register ``name``."""
    return _register_map()[name]


@dataclass(slots=True)
class ReadPlan:
    """Plan describing a consecutive block of registers to read."""

    function: str
    address: int
    length: int


def plan_group_reads(max_block_size: int = 64) -> list[ReadPlan]:
    """Group registers into contiguous blocks for efficient reading."""

    regs_by_fn: dict[str, list[int]] = {}
    for reg in load_registers():
        addr_range = range(reg.address, reg.address + reg.length)
        regs_by_fn.setdefault(reg.function, []).extend(addr_range)

    plans: list[ReadPlan] = []
    for fn, addresses in regs_by_fn.items():
        for start, length in group_reads(addresses, max_block_size=max_block_size):
            plans.append(ReadPlan(fn, start, length))

    return plans
