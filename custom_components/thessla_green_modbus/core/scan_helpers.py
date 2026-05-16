"""Scan helper functions for register name normalisation."""

from __future__ import annotations

import re
from typing import Any


def normalise_cached_register_name(name: str) -> str:
    """Normalise cached register names to current canonical form."""
    match = re.fullmatch(r"([es])(\d+)", name)
    if match:
        return f"{match.group(1)}_{int(match.group(2))}"
    return name


def normalise_available_registers(
    coordinator: Any, available: dict[str, list[str] | set[str]]
) -> dict[str, set[str]]:
    """Return available register names in canonical form."""
    normalised: dict[str, set[str]] = {}
    for reg_type, names in available.items():
        if not isinstance(names, list | set):
            continue
        normalised[reg_type] = {normalise_cached_register_name(str(name)) for name in names}
    return normalised
