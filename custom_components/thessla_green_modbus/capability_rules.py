"""Capability inference rules for device scanner.

Maps capability attributes to keywords that indicate their presence when
found in register names.
"""

from __future__ import annotations

from typing import Mapping, Sequence

CAPABILITY_PATTERNS: Mapping[str, Sequence[str]] = {
    "heating_system": ("heating", "heater"),
    "cooling_system": ("cooling", "cooler"),
    "bypass_system": ("bypass",),
    "gwc_system": ("gwc",),
}
