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

import asyncio
import hashlib
import importlib.resources as resources
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache, partial
from pathlib import Path
from typing import Any, cast

from .register_def import RegisterDef
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


async def _async_executor(
    hass: Any | None,
    func: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Run ``func`` in the executor or background thread."""

    if kwargs:
        func = partial(func, **kwargs)
    if hass is not None:
        return await hass.async_add_executor_job(func, *args)
    return await asyncio.to_thread(func, *args)


async def async_compute_file_hash(hass: Any | None, path: Path, mtime: float) -> str:
    """Return SHA256 digest for ``path`` and update the cache asynchronously."""

    data = await _async_executor(hass, path.read_bytes)
    digest = hashlib.sha256(data).hexdigest()
    _cached_file_info[str(path)] = (mtime, digest)
    return digest


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

_SPECIAL_MODES_PATH = Path(__file__).resolve().parents[1] / "options" / "special_modes.json"
_SPECIAL_MODES_ENUM: dict[int, str] = {}
try:  # pragma: no cover
    _SPECIAL_MODES_ENUM = {
        idx: key.split("_")[-1]
        for idx, key in enumerate(json.loads(_SPECIAL_MODES_PATH.read_text()))
    }
except (OSError, json.JSONDecodeError, ValueError) as err:  # pragma: no cover
    _LOGGER.debug("Failed to load special modes: %s", err)
    _SPECIAL_MODES_ENUM = {}
except (AttributeError, TypeError) as err:  # pragma: no cover
    _LOGGER.exception("Unexpected error loading special modes: %s", err)
    _SPECIAL_MODES_ENUM = {}


# ---------------------------------------------------------------------------
# Register loading helpers
# ---------------------------------------------------------------------------


def _parse_registers(raw: Any) -> list[RegisterDef]:
    """Parse raw register definition data into RegisterDef objects."""

    items = raw.get("registers", raw) if isinstance(raw, dict) else raw

    if hasattr(RegisterList, "model_validate"):
        parsed_items = RegisterList.model_validate(items).registers
    else:  # pragma: no cover
        parsed_items = RegisterList.parse_obj(items).registers

    return [_register_from_parsed(parsed) for parsed in parsed_items]


def _normalise_enum_map(
    name: str, enum_map: dict[int | str, Any] | None
) -> dict[int | str, Any] | None:
    if name == "special_mode":
        return cast(dict[int | str, Any], _SPECIAL_MODES_ENUM)
    if not enum_map:
        return enum_map
    if all(isinstance(k, int | float) or str(k).isdigit() for k in enum_map):
        return cast(dict[int | str, Any], {int(k): v for k, v in enum_map.items()})
    if all(
        isinstance(v, int | float) or str(v).isdigit() for v in enum_map.values()
    ):  # pragma: no cover
        return cast(
            dict[int | str, Any], {int(v): k for k, v in enum_map.items()}
        )  # pragma: no cover
    return enum_map


def _coerce_scaling_fields(parsed: Any) -> tuple[float, float]:
    """Return safe multiplier/resolution values for RegisterDef construction."""

    # ``multiplier`` and ``resolution`` are optional in the JSON.  The
    # dataclass defaults to ``1`` for both fields but passing ``None`` would
    # override that default and propagate ``None`` through the rest of the
    # code. Coercing ``None`` to ``1`` here keeps values consistent and avoids
    # ``Optional`` downstream.
    multiplier = 1 if parsed.multiplier is None else float(parsed.multiplier)
    resolution = 1 if parsed.resolution is None else float(parsed.resolution)
    return multiplier, resolution


def _register_from_parsed(parsed: Any) -> RegisterDef:
    """Build RegisterDef from parsed schema entry."""

    function = _normalise_function(parsed.function)

    # Keep register addresses exactly as provided in the JSON definition.
    # Older revisions attempted to normalize into compact offset spaces,
    # causing reads to target different addresses than the register map.
    address = int(parsed.address_dec)
    name = _normalise_name(parsed.name)
    enum_map = _normalise_enum_map(
        name,
        cast(dict[int | str, Any] | None, parsed.enum),
    )
    multiplier, resolution = _coerce_scaling_fields(parsed)

    return RegisterDef(
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


def _load_registers_from_file(path: Path, *, mtime: float, file_hash: str) -> list[RegisterDef]:
    """Load register definitions from ``path``.

    ``mtime`` and ``file_hash`` are accepted for tests that spy on cache behaviour.  They do not influence the parsing
    directly; caching is handled in ``load_registers`` using these values.
    """

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:  # pragma: no cover
        raise RuntimeError(f"Register definition file missing: {path}") from err
    except (
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as err:  # pragma: no cover
        raise RuntimeError(f"Failed to read register definitions from {path}") from err

    return _parse_registers(raw)


async def async_load_registers_from_file(
    hass: Any | None, path: Path, *, mtime: float, file_hash: str
) -> list[RegisterDef]:
    """Load register definitions from ``path`` asynchronously."""

    try:
        raw_text = await _async_executor(hass, path.read_text, encoding="utf-8")
        raw = json.loads(raw_text)
    except FileNotFoundError as err:  # pragma: no cover
        raise RuntimeError(f"Register definition file missing: {path}") from err
    except (
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as err:  # pragma: no cover
        raise RuntimeError(f"Failed to read register definitions from {path}") from err

    return _parse_registers(raw)


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


async def async_registers_sha256(hass: Any | None, json_path: Path | str) -> str:
    """Return the SHA256 hash of ``json_path`` asynchronously."""

    path = Path(json_path)
    stat_result = await _async_executor(hass, path.stat)
    mtime = stat_result.st_mtime
    path_str = str(path)
    cached = _cached_file_info.get(path_str)
    if cached and cached[0] == mtime:
        return cached[1]

    return await async_compute_file_hash(hass, path, mtime)


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
    cached = _cached_file_info.get(str(path))
    if cached is None:
        raise RuntimeError(f"Missing cache metadata for register file: {path}")
    mtime = cached[0]
    key = (file_hash, mtime)
    regs = _register_cache.get(key)
    if regs is None:
        regs = _load_registers_from_file(path, mtime=mtime, file_hash=file_hash)
        _register_cache[key] = regs
    return regs


async def async_load_registers(
    hass: Any | None, json_path: Path | str | None = None
) -> list[RegisterDef]:
    """Return cached register definitions asynchronously."""

    path = Path(json_path) if json_path is not None else _REGISTERS_PATH
    file_hash = await async_registers_sha256(hass, path)
    cached = _cached_file_info.get(str(path))
    if cached is None:
        raise RuntimeError(f"Missing cache metadata for register file: {path}")
    mtime = cached[0]
    key = (file_hash, mtime)
    regs = _register_cache.get(key)
    if regs is None:
        regs = await async_load_registers_from_file(hass, path, mtime=mtime, file_hash=file_hash)
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


async def async_get_all_registers(
    hass: Any | None, json_path: Path | str | None = None
) -> list[RegisterDef]:
    """Return all known registers asynchronously."""

    regs = await async_load_registers(hass, json_path)
    return sorted(regs, key=lambda r: (r.function, r.address))


def get_registers_by_function(fn: str, json_path: Path | str | None = None) -> list[RegisterDef]:
    """Return registers for the given function code or name."""
    code = _normalise_function(fn)
    return [r for r in load_registers(json_path) if r.function == code]


async def async_get_registers_by_function(
    hass: Any | None, fn: str, json_path: Path | str | None = None
) -> list[RegisterDef]:
    """Return registers for the given function code or name asynchronously."""

    code = _normalise_function(fn)
    return [r for r in await async_load_registers(hass, json_path) if r.function == code]


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

    from ..modbus_helpers import group_reads

    plans: list[ReadPlan] = []
    for fn, addresses in regs_by_fn.items():
        for start, length in group_reads(addresses, max_block_size=max_block_size):
            plans.append(ReadPlan(fn, start, length))

    return plans


def group_registers(
    addresses: Iterable[int],
    max_block_size: int | None = None,
) -> list[tuple[int, int]]:
    """Return grouped register ranges for the provided addresses."""

    from ..modbus_helpers import group_reads

    return group_reads(addresses, max_block_size=max_block_size)


# Public exports for import * use in tests and helpers
__all__ = [
    "_REGISTERS_PATH",
    "ReadPlan",
    "RegisterDef",
    "async_compute_file_hash",
    "async_get_all_registers",
    "async_get_registers_by_function",
    "async_load_registers",
    "async_load_registers_from_file",
    "async_registers_sha256",
    "clear_cache",
    "get_all_registers",
    "get_register_definition",
    "get_registers_by_function",
    "get_registers_path",
    "group_registers",
    "load_registers",
    "plan_group_reads",
]
