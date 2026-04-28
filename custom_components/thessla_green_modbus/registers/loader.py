"""Public register loader/orchestration API."""

from __future__ import annotations

import importlib.resources as resources
from functools import lru_cache
from pathlib import Path
from typing import Any

from .cache import (
    _cached_file_info,
    _register_cache,
    async_registers_sha256,
    registers_sha256,
)
from .cache import (
    clear_cache as _clear_register_cache,
)
from .definition import ReadPlan
from .parser import async_load_registers_from_file, load_registers_from_file
from .read_planner import group_registers as _group_registers_impl
from .read_planner import plan_group_reads as _plan_group_reads_impl
from .register_def import RegisterDef
from .schema import _normalise_function

_REGISTERS_PATH = Path(
    str(resources.files(__package__).joinpath("thessla_green_registers_full.json"))
)


def get_registers_path() -> Path:
    """Return resolved path to bundled register definitions JSON file."""
    return _REGISTERS_PATH.resolve()


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
        regs = load_registers_from_file(path)
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
        regs = await async_load_registers_from_file(hass, path)
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
    "async_get_all_registers",
    "async_get_registers_by_function",
    "async_load_registers",
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
