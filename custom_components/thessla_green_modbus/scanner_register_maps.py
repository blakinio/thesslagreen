"""Register-definition caches and map builders for scanner usage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional during isolated tests
    from .registers.loader import (
        async_get_all_registers,
        async_registers_sha256,
        get_all_registers,
        get_registers_path,
        registers_sha256,
    )
except (ImportError, AttributeError):  # pragma: no cover - fallback when stubs incomplete

    async def async_get_all_registers(*_args, **_kwargs):
        return []

    async def async_registers_sha256(*_args, **_kwargs) -> str:
        return ""

    def get_all_registers(*_args, **_kwargs):
        return []

    def get_registers_path(*_args, **_kwargs) -> Path:
        return Path(".")

    def registers_sha256(*_args, **_kwargs) -> str:
        return ""


REGISTER_DEFINITIONS: dict[str, Any] = {}

INPUT_REGISTERS: dict[str, int] = {}

HOLDING_REGISTERS: dict[str, int] = {}

COIL_REGISTERS: dict[str, int] = {}

DISCRETE_INPUT_REGISTERS: dict[str, int] = {}

MULTI_REGISTER_SIZES: dict[str, int] = {}

REGISTER_HASH: str | None = None


def _build_register_maps_from(regs: list[Any], register_hash: str) -> None:
    """Populate register lookup maps from provided register definitions."""
    global REGISTER_HASH
    REGISTER_HASH = register_hash

    REGISTER_DEFINITIONS.clear()
    REGISTER_DEFINITIONS.update({r.name: r for r in regs})

    INPUT_REGISTERS.clear()
    INPUT_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == 4}
    )

    HOLDING_REGISTERS.clear()
    HOLDING_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == 3}
    )

    COIL_REGISTERS.clear()
    COIL_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == 1}
    )

    DISCRETE_INPUT_REGISTERS.clear()
    DISCRETE_INPUT_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == 2}
    )

    MULTI_REGISTER_SIZES.clear()
    MULTI_REGISTER_SIZES.update(
        {
            name: reg.length
            for name, reg in REGISTER_DEFINITIONS.items()
            if reg.function == 3 and reg.length > 1
        }
    )


def _build_register_maps() -> None:
    """Populate register lookup maps from current register definitions."""
    regs = get_all_registers()
    register_hash = registers_sha256(get_registers_path())
    _build_register_maps_from(regs, register_hash)


async def _async_build_register_maps(hass: Any | None) -> None:
    """Populate register lookup maps from current definitions asynchronously."""
    register_hash = await async_registers_sha256(hass, get_registers_path())
    regs = await async_get_all_registers(hass)
    _build_register_maps_from(regs, register_hash)


def _ensure_register_maps() -> None:
    """Ensure register lookup maps are populated."""
    current_hash = registers_sha256(get_registers_path())
    if not REGISTER_DEFINITIONS or current_hash != REGISTER_HASH:
        _build_register_maps()


async def _async_ensure_register_maps(hass: Any | None) -> None:
    """Ensure register lookup maps are populated without blocking the event loop."""
    register_hash = await async_registers_sha256(hass, get_registers_path())
    if not REGISTER_DEFINITIONS or register_hash != REGISTER_HASH:
        await _async_build_register_maps(hass)


async def async_ensure_register_maps(hass: Any | None = None) -> None:
    """Ensure register lookup maps are populated without blocking the event loop."""
    await _async_ensure_register_maps(hass)


__all__ = [
    "COIL_REGISTERS",
    "DISCRETE_INPUT_REGISTERS",
    "HOLDING_REGISTERS",
    "INPUT_REGISTERS",
    "MULTI_REGISTER_SIZES",
    "REGISTER_DEFINITIONS",
    "REGISTER_HASH",
    "_async_build_register_maps",
    "_async_ensure_register_maps",
    "_build_register_maps",
    "_build_register_maps_from",
    "_ensure_register_maps",
    "async_ensure_register_maps",
]
