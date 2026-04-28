"""Hash and register-definition cache helpers."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .register_def import RegisterDef

_cached_file_info: dict[str, tuple[float, str]] = {}
_register_cache: dict[tuple[str, float], list[RegisterDef]] = {}


async def _async_executor(
    hass: Any | None,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    if kwargs:
        from functools import partial

        func = partial(func, **kwargs)
    if hass is not None:
        return await hass.async_add_executor_job(func, *args)
    return await asyncio.to_thread(func, *args)


def _compute_file_hash(path: Path, mtime: float) -> str:
    """Return SHA256 digest for ``path`` and update file-info cache."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _cached_file_info[str(path)] = (mtime, digest)
    return digest


async def async_compute_file_hash(hass: Any | None, path: Path, mtime: float) -> str:
    """Return SHA256 digest for ``path`` and update file-info cache asynchronously."""
    data = await _async_executor(hass, path.read_bytes)
    digest = hashlib.sha256(data).hexdigest()
    _cached_file_info[str(path)] = (mtime, digest)
    return digest


def registers_sha256(json_path: Path | str) -> str:
    """Return cached SHA256 for file path, recomputing when mtime changes."""
    path = Path(json_path)
    mtime = path.stat().st_mtime
    path_str = str(path)
    cached = _cached_file_info.get(path_str)
    if cached and cached[0] == mtime:
        return cached[1]
    return _compute_file_hash(path, mtime)


async def async_registers_sha256(hass: Any | None, json_path: Path | str) -> str:
    """Return cached SHA256 for file path asynchronously."""
    path = Path(json_path)
    stat_result = await _async_executor(hass, path.stat)
    mtime = stat_result.st_mtime
    path_str = str(path)
    cached = _cached_file_info.get(path_str)
    if cached and cached[0] == mtime:
        return cached[1]
    return await async_compute_file_hash(hass, path, mtime)


def get_cached_file_info(path: Path | str) -> tuple[float, str] | None:
    """Return cached ``(mtime, digest)`` metadata for ``path``."""
    return _cached_file_info.get(str(Path(path)))


def get_cached_registers(file_hash: str, mtime: float) -> list[RegisterDef] | None:
    """Return cached registers for ``(file_hash, mtime)`` key, if present."""
    return _register_cache.get((file_hash, mtime))


def set_cached_registers(file_hash: str, mtime: float, registers: list[RegisterDef]) -> None:
    """Store register list for ``(file_hash, mtime)`` key."""
    _register_cache[(file_hash, mtime)] = registers


def clear_cache(*, register_map_cache_clear: Callable[[], None] | None = None) -> None:
    """Clear all register/file hash caches used by the loader."""
    _cached_file_info.clear()
    _register_cache.clear()
    if register_map_cache_clear is not None:
        register_map_cache_clear()
