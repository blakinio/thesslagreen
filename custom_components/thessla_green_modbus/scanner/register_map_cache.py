"""Register-map cache helpers for scanner core."""

from __future__ import annotations

from typing import Any

from ..scanner import register_maps as _register_maps


def sync_register_hash_from_maps() -> str:
    """Return current register hash from the canonical register_maps module."""
    return _register_maps.REGISTER_HASH or ""


def build_register_maps_from(regs: list[Any], register_hash: str) -> None:
    """Populate register lookup maps from provided register definitions."""
    _register_maps._build_register_maps_from(regs, register_hash)


def build_register_maps() -> None:
    """Populate register lookup maps from current register definitions."""
    _register_maps._build_register_maps()


async def async_build_register_maps(hass: Any | None) -> None:
    """Populate register lookup maps from current definitions asynchronously."""
    await _register_maps._async_build_register_maps(hass)


def ensure_register_maps() -> None:
    """Ensure register lookup maps are populated."""
    _register_maps._ensure_register_maps()


async def async_ensure_register_maps(hass: Any | None) -> None:
    """Ensure register lookup maps are populated without blocking the event loop."""
    await _register_maps._async_ensure_register_maps(hass)
