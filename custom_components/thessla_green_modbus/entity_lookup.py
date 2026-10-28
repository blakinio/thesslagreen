"""Entity-lookup cache for unique-ID migration."""

from __future__ import annotations

import functools


@functools.cache
def _build_entity_lookup() -> dict[str, tuple[str, str | None, int | None]]:
    """Build and cache a mapping of entity keys to register info."""
    from .mappings import ENTITY_MAPPINGS as _MAP

    lookup: dict[str, tuple[str, str | None, int | None]] = {}
    for platform in (
        "sensor",
        "binary_sensor",
        "switch",
        "select",
        "number",
        "time",
        "text",
        "button",
    ):
        for key, cfg in _MAP.get(platform, {}).items():
            register = cfg.get("register", key)
            lookup[key] = (register, cfg.get("register_type"), cfg.get("bit"))
    for key in (
        "ventilation",
        "climate_control",
        "error_codes",
        "active_errors",
        "sync_device_clock",
    ):
        lookup.setdefault(key, (key, None, None))
    return lookup


__all__ = ["_build_entity_lookup"]
