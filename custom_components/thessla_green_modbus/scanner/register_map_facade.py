"""Facade helpers for scanner register-map cache access."""

from __future__ import annotations

from typing import Any

from . import register_map_cache as _register_map_cache


def build_register_maps_from(regs: list[Any], register_hash: str) -> str:
    """Populate register maps from provided register definitions and return hash."""
    _register_map_cache.build_register_maps_from(regs, register_hash)
    return _register_map_cache.sync_register_hash_from_maps()


def build_register_maps() -> str:
    """Populate register maps from current register definitions and return hash."""
    _register_map_cache.build_register_maps()
    return _register_map_cache.sync_register_hash_from_maps()


async def async_build_register_maps(hass: Any | None) -> str:
    """Populate register maps asynchronously and return hash."""
    await _register_map_cache.async_build_register_maps(hass)
    return _register_map_cache.sync_register_hash_from_maps()


def ensure_register_maps(current_hash: str) -> str:
    """Ensure sync register maps are loaded and return latest hash."""
    _register_map_cache.REGISTER_HASH = current_hash
    _register_map_cache.ensure_register_maps()
    return _register_map_cache.sync_register_hash_from_maps()


async def async_ensure_register_maps(current_hash: str, hass: Any | None) -> str:
    """Ensure async register maps are loaded and return latest hash."""
    _register_map_cache.REGISTER_HASH = current_hash
    await _register_map_cache.async_ensure_register_maps(hass)
    return _register_map_cache.sync_register_hash_from_maps()
