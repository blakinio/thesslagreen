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
