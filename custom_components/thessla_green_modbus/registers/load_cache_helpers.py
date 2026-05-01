"""Helpers for cached register file loading."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from .cache import get_cached_file_info, get_cached_registers, set_cached_registers
from .register_def import RegisterDef

T = TypeVar("T")


def resolve_cached_registers(
    path: Path,
    file_hash: str,
    load_when_missing: Callable[[], list[RegisterDef]],
) -> list[RegisterDef]:
    """Return cached register definitions or load and cache them."""
    mtime = _get_cached_mtime(path)
    regs = get_cached_registers(file_hash, mtime)
    if regs is None:
        regs = load_when_missing()
        set_cached_registers(file_hash, mtime, regs)
    return regs


async def async_resolve_cached_registers(
    path: Path,
    file_hash: str,
    load_when_missing: Callable[[], Awaitable[list[RegisterDef]]],
) -> list[RegisterDef]:
    """Asynchronous variant of :func:`resolve_cached_registers`."""
    mtime = _get_cached_mtime(path)
    regs = get_cached_registers(file_hash, mtime)
    if regs is None:
        regs = await load_when_missing()
        set_cached_registers(file_hash, mtime, regs)
    return regs


def _get_cached_mtime(path: Path) -> float:
    cached = get_cached_file_info(path)
    if cached is None:
        raise RuntimeError(f"Missing cache metadata for register file: {path}")
    return cached[0]
