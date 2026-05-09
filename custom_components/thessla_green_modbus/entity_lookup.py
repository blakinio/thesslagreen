"""Entity-lookup cache for unique-ID migration."""

from __future__ import annotations

_ENTITY_LOOKUP: dict[str, tuple[str, str | None, int | None]] | None = None


def _build_entity_lookup() -> dict[str, tuple[str, str | None, int | None]]:
    """Build and cache a mapping of entity keys to register info."""
    global _ENTITY_LOOKUP
    if _ENTITY_LOOKUP is None:
        from .mappings import ENTITY_MAPPINGS as _MAP

        lookup: dict[str, tuple[str, str | None, int | None]] = {}
        for platform in ("sensor", "binary_sensor", "switch", "select", "number"):
            for key, cfg in _MAP.get(platform, {}).items():
                register = cfg.get("register", key)
                lookup[key] = (register, cfg.get("register_type"), cfg.get("bit"))
        _ENTITY_LOOKUP = lookup
    return _ENTITY_LOOKUP


__all__ = ["_ENTITY_LOOKUP", "_build_entity_lookup"]
