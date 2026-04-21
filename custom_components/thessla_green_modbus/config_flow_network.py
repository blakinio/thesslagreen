"""Network-related helpers for config flow validation."""

from __future__ import annotations


def looks_like_hostname(value: str) -> bool:
    """Basic hostname validation for environments without network helpers."""
    if not value:
        return False
    if any(char.isspace() for char in value):
        return False
    if value.replace(".", "").isdigit():
        return False
    if value.startswith("-") or value.endswith("-"):
        return False
    return "." in value

