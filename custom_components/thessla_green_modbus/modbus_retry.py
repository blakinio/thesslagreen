"""Retry policy helpers for Modbus operations."""

from __future__ import annotations

import random


def _calculate_backoff_delay(
    *,
    base: float,
    attempt: int,
    jitter: float | tuple[float, float] | None,
) -> float:
    """Return the delay for the given ``attempt`` including optional jitter."""

    if base <= 0 or attempt <= 1:
        delay = 0.0
    else:
        delay = float(base) * (2 ** (attempt - 2))

    if jitter:
        if isinstance(jitter, int | float):
            jitter_min = 0.0
            jitter_max = float(jitter)
        else:
            jitter_min, jitter_max = (float(jitter[0]), float(jitter[1]))
        if jitter_max < jitter_min:
            jitter_min, jitter_max = jitter_max, jitter_min
        delay += random.uniform(jitter_min, jitter_max)

    return max(delay, 0.0)
