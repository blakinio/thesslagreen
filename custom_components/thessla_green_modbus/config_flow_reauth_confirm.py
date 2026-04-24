"""Helpers for config flow reauth confirmation step."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


async def apply_reauth_update(
    *,
    hass: Any,
    reauth_entry_id: str | None,
    prepare_entry_payload: Callable[[type], tuple[dict[str, Any], dict[str, Any]]],
    capabilities_cls: type,
    logger: Any,
) -> str:
    """Apply reauth updates and return abort reason."""

    if hass is None:
        logger.error("Cannot complete reauth - missing Home Assistant context")
        return "reauth_failed"
    if reauth_entry_id is None:
        logger.error("Cannot complete reauth - missing entry id")
        return "reauth_entry_missing"

    entry = hass.config_entries.async_get_entry(reauth_entry_id)
    if entry is None:
        logger.error(
            "Reauthentication requested for missing entry %s",
            reauth_entry_id,
        )
        return "reauth_entry_missing"

    data, options = prepare_entry_payload(capabilities_cls)
    combined_options = dict(entry.options)
    combined_options.update(options)
    hass.config_entries.async_update_entry(entry, data=data, options=combined_options)

    reload_result = hass.config_entries.async_reload(entry.entry_id)
    if isinstance(reload_result, Awaitable):
        await reload_result

    return "reauth_successful"
