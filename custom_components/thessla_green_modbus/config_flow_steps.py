"""Pure step helpers for config flow orchestration."""

from __future__ import annotations

from typing import Any

from .const import CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST


def validate_options_submission(
    user_input: dict[str, Any],
    *,
    max_batch_registers: int,
) -> dict[str, str]:
    """Validate options form submission and return field errors."""
    errors: dict[str, str] = {}
    max_regs = user_input.get(CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST)
    if not 1 <= max_regs <= max_batch_registers:
        errors[CONF_MAX_REGISTERS_PER_REQUEST] = "max_registers_range"
    return errors


def merge_options_payload(
    existing_options: dict[str, Any] | None,
    user_input: dict[str, Any],
) -> dict[str, Any]:
    """Merge user input into existing options without dropping keys."""
    merged = dict(existing_options or {})
    merged.update(dict(user_input))
    return merged


def extract_discovered_state(info: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return device_info and scan_result dictionaries from validation output."""
    return dict(info.get("device_info", {})), dict(info.get("scan_result", {}))


def resolve_reauth_defaults(
    entry_data: dict[str, Any] | None,
    entry_options: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build reauth defaults from config entry payloads."""
    return {**(entry_options or {}), **(entry_data or {})}


def resolve_reauth_entry(hass: Any, context: dict[str, Any]) -> Any | None:
    """Resolve current reauth config entry from flow context."""
    if hass is None:
        return None
    entry_id = context.get("entry_id")
    if not entry_id:
        return None
    return hass.config_entries.async_get_entry(entry_id)


def initialize_reauth_state(
    *,
    active_entry_id: str | None,
    entry: Any | None,
    defaults: dict[str, Any],
) -> tuple[bool, str | None, dict[str, Any]]:
    """Return initialization state and normalized reauth state payload."""
    if active_entry_id is None:
        return True, (entry.entry_id if entry else None), dict(defaults)
    return False, active_entry_id, dict(defaults)


def build_reauth_form_defaults(
    *,
    user_input: dict[str, Any] | None,
    existing_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build defaults for rendering the reauth form."""
    return dict(user_input or existing_data or {})
