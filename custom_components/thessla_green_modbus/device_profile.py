"""Explicit device-family contract for variant-dependent filter writes."""

from __future__ import annotations

from typing import Any

CONF_DEVICE_FAMILY = "device_family"
DEVICE_FAMILIES = ("unspecified", "airpack_home", "airpack4")


def configured_device_family(coordinator: Any) -> str:
    """Return only the owner's explicitly selected family, not a guessed model."""
    entry = getattr(coordinator, "entry", None)
    options = getattr(entry, "options", {}) or {}
    family = options.get(CONF_DEVICE_FAMILY, "unspecified")
    return family if family in DEVICE_FAMILIES else "unspecified"


def validate_filter_command(family: str, value: Any) -> None:
    """Reject ambiguous/wrong-family writes to shared FC03 address 8191."""
    if isinstance(value, bool) or not isinstance(value, int | float) or int(value) != value:
        raise ValueError("Filter command must be an integer")
    if family == "airpack_home" and value in (1, 2, 3, 4):
        return
    if family == "airpack4" and value in (17, 33):
        return
    raise ValueError(
        "Filter write rejected: select the correct device family first; "
        "Home uses filter-system values 1..4, AirPack4 replacement uses 17/33"
    )
