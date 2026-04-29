"""Shared helpers for service handlers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import async_extract_entity_ids


def extract_entity_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Return entity IDs from a service call."""
    if not call.data.get("entity_id"):
        return set()
    return cast(set[str], async_extract_entity_ids(hass, call))


def iter_target_coordinators(
    hass: HomeAssistant,
    call: ServiceCall,
    get_coordinator_from_entity_id: Callable[[HomeAssistant, str], Any],
) -> list[tuple[str, Any]]:
    """Resolve entity IDs to coordinator instances, skipping missing ones."""
    targets: list[tuple[str, Any]] = []
    for entity_id in extract_entity_ids(hass, call):
        coordinator = get_coordinator_from_entity_id(hass, entity_id)
        if coordinator is None:
            continue
        targets.append((entity_id, coordinator))
    return targets


def clamp_airflow_rate(coordinator: Any, airflow_rate: int) -> int:
    """Clamp airflow_rate to the coordinator's reported min/max percentages."""
    data = getattr(coordinator, "data", {}) or {}
    min_pct = data.get("min_percentage")
    max_pct = data.get("max_percentage")
    try:
        min_val = int(min_pct) if min_pct is not None else 0
    except (TypeError, ValueError):
        min_val = 0
    try:
        max_val = int(max_pct) if max_pct is not None else 150
    except (TypeError, ValueError):
        max_val = 150
    min_val = max(0, min_val)
    max_val = min(150, max_val)
    if max_val < min_val:
        max_val = min_val
    return max(min_val, min(max_val, int(airflow_rate)))
