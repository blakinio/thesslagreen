"""Public register loader/orchestration API."""

from __future__ import annotations

import importlib.resources as resources
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import parser as _parser_module
from .cache import (
    _cached_file_info,
    _register_cache,
    async_compute_file_hash,
    async_registers_sha256,
    registers_sha256,
)
from .cache import (
    clear_cache as _clear_register_cache,
)
from .definition import ReadPlan
from .parser import (
    async_load_registers_from_file as _async_load_registers_from_file_impl,
)
from .parser import (
    coerce_scaling_fields as _coerce_scaling_fields_impl,
)
from .parser import (
    load_registers_from_file as _load_registers_from_file_impl,
)
from .parser import (
    normalise_enum_map as _normalise_enum_map_impl,
)
from .parser import (
    parse_registers as _parse_registers_impl,
)
from .parser import (
    register_from_parsed as _register_from_parsed_impl,
)
from .read_planner import group_registers as _group_registers_impl
from .read_planner import plan_group_reads as _plan_group_reads_impl
from .register_def import RegisterDef
from .schema import _normalise_function

_LOGGER = logging.getLogger(__name__)
_REGISTERS_PATH = Path(
    str(resources.files(__package__).joinpath("thessla_green_registers_full.json"))
)
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
_parser_module._SPECIAL_MODES_PATH = _SPECIAL_MODES_PATH
_parser_module._SPECIAL_MODES_ENUM = _SPECIAL_MODES_ENUM


def get_registers_path() -> Path:
    """Return resolved path to bundled register definitions JSON file."""
    return _REGISTERS_PATH.resolve()


def _parse_registers(raw: Any) -> list[RegisterDef]:
    """Compatibility private helper retained for tests."""
    return _parse_registers_impl(raw)


def _normalise_enum_map(
    name: str, enum_map: dict[int | str, Any] | None
) -> dict[int | str, Any] | None:
    """Compatibility private helper retained for tests."""
    return _normalise_enum_map_impl(name, enum_map)


def _coerce_scaling_fields(parsed: Any) -> tuple[float, float]:
    """Compatibility private helper retained for tests."""
    return _coerce_scaling_fields_impl(parsed)


def _register_from_parsed(parsed: Any) -> RegisterDef:
    """Compatibility private helper retained for tests."""
    return _register_from_parsed_impl(parsed)


def _load_registers_from_file(path: Path, *, mtime: float, file_hash: str) -> list[RegisterDef]:
    """Load register definitions from path (mtime/hash accepted for test probes)."""
    _ = (mtime, file_hash)
    return _load_registers_from_file_impl(path)


async def async_load_registers_from_file(
    hass: Any | None, path: Path, *, mtime: float, file_hash: str
) -> list[RegisterDef]:
    """Load register definitions from path asynchronously."""
    _ = (mtime, file_hash)
    return await _async_load_registers_from_file_impl(hass, path)


def load_registers(json_path: Path | str | None = None) -> list[RegisterDef]:
    """Return cached register definitions, reloading if file changed."""
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
    """Clear register loader/file-hash cache."""
    _clear_register_cache(register_map_cache_clear=_register_map.cache_clear)


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
    """Return registers for given function code/name asynchronously."""
    code = _normalise_function(fn)
    return [r for r in await async_load_registers(hass, json_path) if r.function == code]


@lru_cache(maxsize=1)
def _register_map() -> dict[str, RegisterDef]:
    return {r.name: r for r in load_registers()}


def get_register_definition(name: str) -> RegisterDef:
    """Return definition for register name."""
    return _register_map()[name]


def plan_group_reads(max_block_size: int | None = None) -> list[ReadPlan]:
    """Group registers into contiguous blocks for efficient reading."""
    return _plan_group_reads_impl(load_registers, max_block_size=max_block_size)


def group_registers(
    addresses: list[int],
    max_block_size: int | None = None,
) -> list[tuple[int, int]]:
    """Return grouped register ranges for provided addresses."""
    return _group_registers_impl(addresses, max_block_size=max_block_size)


__all__ = [
    "_REGISTERS_PATH",
    "_SPECIAL_MODES_ENUM",
    "_SPECIAL_MODES_PATH",
    "ReadPlan",
    "RegisterDef",
    "_cached_file_info",
    "_coerce_scaling_fields",
    "_normalise_enum_map",
    "_parse_registers",
    "_register_cache",
    "_register_from_parsed",
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
    "registers_sha256",
]
