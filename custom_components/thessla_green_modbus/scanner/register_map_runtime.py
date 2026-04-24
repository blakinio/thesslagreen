"""Register-map runtime helpers for scanner core delegation."""

from __future__ import annotations

from typing import Any

from . import register_map_cache as _register_map_cache
from . import register_map_facade as _register_map_facade


def initial_register_hash() -> str:
    """Return initial register hash value."""
    return _register_map_cache.REGISTER_HASH


def sync_register_hash_from_maps() -> str:
    """Synchronize register hash from scanner register maps module."""
    return _register_map_cache.sync_register_hash_from_maps()


def build_register_maps_from(regs: list[Any], register_hash: str) -> str:
    """Populate lookup maps from provided register definitions and return hash."""
    return _register_map_facade.build_register_maps_from(regs, register_hash)


def build_register_maps() -> str:
    """Populate lookup maps from current register definitions and return hash."""
    return _register_map_facade.build_register_maps()


async def async_build_register_maps(hass: Any | None) -> str:
    """Populate lookup maps asynchronously and return hash."""
    return await _register_map_facade.async_build_register_maps(hass)


def ensure_register_maps(register_hash: str) -> str:
    """Ensure lookup maps are populated and return resulting hash."""
    return _register_map_facade.ensure_register_maps(register_hash)


async def async_ensure_register_maps(register_hash: str, hass: Any | None) -> str:
    """Ensure lookup maps asynchronously and return resulting hash."""
    return await _register_map_facade.async_ensure_register_maps(register_hash, hass)
