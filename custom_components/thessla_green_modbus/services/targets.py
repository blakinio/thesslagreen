"""Target-resolution helpers for service handlers."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

__all__ = [
    "extract_entity_ids",
    "extract_entity_ids_with_extractor",
    "get_coordinator_from_entity_id",
    "iter_target_coordinators",
]


async def extract_entity_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Resolve all Home Assistant service targets to entity IDs.

    Home Assistant 2026.1+ exposes ``async_extract_entity_ids(service_call)``.
    The helper expands direct entities as well as indirect targets such as
    devices, areas, floors, labels, and groups. ``hass`` is intentionally kept
    in this internal signature so callers do not need a second compatibility
    adapter; the Home Assistant helper reads the instance from ``call.hass``.
    """
    from homeassistant.helpers.service import async_extract_entity_ids

    return await extract_entity_ids_with_extractor(hass, call, extractor=async_extract_entity_ids)


async def extract_entity_ids_with_extractor(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    extractor: Callable[..., Any],
) -> set[str]:
    """Resolve target entity IDs using an injectable extraction backend.

    Production uses Home Assistant's asynchronous extractor. A synchronous
    return value is accepted only to keep small unit-test doubles lightweight;
    production awaitables are always awaited and are never closed/discarded.
    """
    del hass
    extracted = extractor(call)
    if inspect.isawaitable(extracted):
        extracted = await extracted
    return set(extracted)


async def iter_target_coordinators(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    coordinator_getter: Callable[[HomeAssistant, str], Any | None],
    entity_id_extractor: Callable[
        [HomeAssistant, ServiceCall], Awaitable[set[str]]
    ]
    | None = None,
) -> list[tuple[str, Any]]:
    """Resolve service targets to loaded ThesslaGreen coordinators.

    Targets may contain entities from other integrations (for example when an
    area is selected), so non-ThesslaGreen entities are ignored. A call that
    resolves to no loaded ThesslaGreen entity is invalid and is surfaced to the
    caller instead of silently succeeding.
    """
    resolver = entity_id_extractor or extract_entity_ids
    targets: list[tuple[str, Any]] = []
    for entity_id in await resolver(hass, call):
        coordinator = coordinator_getter(hass, entity_id)
        if coordinator is None:
            continue
        targets.append((entity_id, coordinator))

    if not targets:
        raise ServiceValidationError("No loaded ThesslaGreen entity matched the selected target.")
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
