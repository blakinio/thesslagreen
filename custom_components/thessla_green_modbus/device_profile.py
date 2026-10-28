"""Explicit device-family contract for variant-dependent filter writes."""

from __future__ import annotations

from typing import Any

CONF_DEVICE_FAMILY = "device_family"
DEVICE_FAMILIES = ("unspecified", "airpack_home", "airpack4")


def configuration_command_block_reason(family: str, firmware: Any, value: Any) -> str | None:
    """Gate AFC filter control, not airflow calibration (Home protocol p.5).

    Reading address 13 does not establish that every command is implemented.
    Keep stop (0) and the older duct-filter test (47) independent of this gate.
    """
    if value != 65:
        return None
    if family not in ("airpack_home", "airpack4"):
        return "Select the documented Home or AirPack4 profile before an AFC test"
    parts = firmware.strip().lstrip("vV").split(".") if isinstance(firmware, str) else []
    if len(parts) < 2 or not all(part.isdigit() for part in parts[:2]):
        return "AFC filter control requires a known firmware version of 4.75 or later"
    if tuple(map(int, parts[:2])) < (4, 75):
        return "AFC filter control requires firmware 4.75 or later; it is not airflow calibration"
    return None


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
