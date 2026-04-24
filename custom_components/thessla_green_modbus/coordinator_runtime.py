"""Runtime normalization helpers for coordinator state."""

from __future__ import annotations

from .const import DEFAULT_BACKOFF, DEFAULT_BACKOFF_JITTER


def normalize_backoff(value: float | int | str | None) -> float:
    """Normalize runtime backoff value to float with safe default."""
    try:
        return float(value) if value is not None else float(DEFAULT_BACKOFF)
    except (TypeError, ValueError):
        return float(DEFAULT_BACKOFF)


def parse_backoff_jitter(
    value: float | int | str | tuple[float, float] | list[float] | None,
) -> float | tuple[float, float] | None:
    """Normalize backoff_jitter input to None, float, or (float, float)."""
    result: float | tuple[float, float] | None
    if isinstance(value, int | float):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value)
        except ValueError:
            result = None
    elif isinstance(value, list | tuple) and len(value) >= 2:
        try:
            result = (float(value[0]), float(value[1]))
        except (TypeError, ValueError):
            result = None
    else:
        result = None if value in (None, "") else DEFAULT_BACKOFF_JITTER

    if result in (0, 0.0):
        result = 0.0
    return result
