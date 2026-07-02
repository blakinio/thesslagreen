"""Target-resolution helpers for service handlers."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import lru_cache
from typing import Any, cast

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

__all__ = [
    "extract_entity_ids",
    "extract_entity_ids_with_extractor",
    "get_coordinator_from_entity_id",
    "iter_target_coordinators",
]


@lru_cache(maxsize=32)
def _extractor_needs_hass(extractor: Callable[..., Any]) -> bool:
    """Detect whether `extractor` needs `hass` as its first argument.

    HA's async_extract_entity_ids dropped the `hass` parameter in HA
    2025.10; older cores still require `(hass, service_call)`. Inspected
    once per extractor and cached, since the extractor is typically the
    same function on every service call.
    """
    try:
        parameters = inspect.signature(extractor).parameters.values()
    except (TypeError, ValueError):
        return False
    required_positional = [
        p
        for p in parameters
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and p.default is inspect.Parameter.empty
    ]
    return len(required_positional) >= 2


def extract_entity_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Return entity IDs from a service call."""
    from homeassistant.helpers.service import async_extract_entity_ids

    return extract_entity_ids_with_extractor(hass, call, extractor=async_extract_entity_ids)


def extract_entity_ids_with_extractor(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    extractor: Callable[..., Any],
) -> set[str]:
    """Return entity IDs from a service call using injectable extraction backend.

    Compatible with both the pre-2025.10 HA signature
    ``async_extract_entity_ids(hass, service_call)`` and the current
    ``async_extract_entity_ids(service_call)`` signature.
    """
    if not call.data.get("entity_id"):
        return set()

    extracted = extractor(hass, call) if _extractor_needs_hass(extractor) else extractor(call)
    if inspect.isawaitable(extracted):
        extracted.close()
        raw_ids = call.data.get("entity_id")
        if raw_ids is None:
            return set()
        return {raw_ids} if isinstance(raw_ids, str) else set(raw_ids)
    return cast(set[str], extracted)


def iter_target_coordinators(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    coordinator_getter: Callable[[HomeAssistant, str], Any | None],
) -> list[tuple[str, Any]]:
    """Resolve entity IDs to coordinator instances, skipping missing ones."""
    targets: list[tuple[str, Any]] = []
    for entity_id in extract_entity_ids(hass, call):
        coordinator = coordinator_getter(hass, entity_id)
        if coordinator is None:
            continue
        targets.append((entity_id, coordinator))
    return targets


def get_coordinator_from_entity_id(hass: HomeAssistant, entity_id: str) -> Any | None:
    """Get coordinator from entity ID using entity registry."""
    entity_registry = getattr(hass, "entity_registry", None)
    if not entity_registry:
        try:
            entity_registry = er.async_get(hass) if hasattr(er, "async_get") else None
        except (KeyError, TypeError, AttributeError):
            entity_registry = None
    entry = entity_registry.async_get(entity_id) if entity_registry else None
    if not entry:
        return None
    config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
    if config_entry is None:
        return None
    runtime_data = getattr(config_entry, "runtime_data", None)
    return runtime_data
