"""Capability inference rules for device scanner.

Maps capability attributes to keywords that indicate their presence when
found in register names.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

CAPABILITY_PATTERNS: Mapping[str, Sequence[str]] = {
    "heating_system": ("heating", "heater"),
    "cooling_system": ("cooling", "cooler"),
    "bypass_system": ("bypass",),
    "gwc_system": ("gwc",),
    # Constant flow capable devices expose registers related to airflow and
    # flow rates. These keywords cover typical naming variations used by the
    # firmware for that feature.
    "constant_flow": ("constant_flow", "cf_", "air_flow", "flow_rate"),
    # Weekly schedule functionality is indicated by registers referencing
    # schedules, airing or related settings.
    "weekly_schedule": ("schedule", "weekly", "airing", "setting"),
}
