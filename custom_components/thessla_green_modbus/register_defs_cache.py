"""Cached access helpers for register definitions."""

from __future__ import annotations

from functools import lru_cache

from .registers.loader import RegisterDef, get_all_registers


@lru_cache(maxsize=1)
def get_register_definitions() -> dict[str, RegisterDef]:
    """Return register definitions keyed by register name."""
    return {register.name: register for register in get_all_registers()}


def clear_register_definitions_cache() -> None:
    """Clear cached register definitions.

    Useful for tests that monkeypatch ``get_all_registers``.
    """
    get_register_definitions.cache_clear()
