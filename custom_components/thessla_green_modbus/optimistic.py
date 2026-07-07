"""Optimistic UI state helper for controllable/setpoint entities.

This helper exists so that control entities (number/switch/select/climate and
the fan) can reflect a *requested* value in the GUI immediately after a
confirmed-successful Modbus write, instead of lagging one full coordinator poll
behind the physical device.

Hard boundaries (enforced by the callers, documented here for context):

* It is **only** used for control/setpoint entities.  Measured/status values
  (temperatures, airflow m³/h, efficiency, power, alarms, diagnostics, …) are
  never made optimistic.
* A pending value is stored **only after a write confirmed success**.  Failed
  writes never populate it.
* The pending value never mutates ``coordinator.data``; it lives entirely inside
  the entity's own :class:`OptimisticState` instance.
* It self-expires after a short TTL (default 10 s) and is cleared as soon as the
  coordinator confirms the real device value, whichever comes first.
"""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from typing import Any

# Default lifetime of an optimistic value.  After this many seconds the pending
# value is dropped and the entity falls back to confirmed device state even if
# the coordinator has not yet caught up.
DEFAULT_OPTIMISTIC_TTL = 10.0


class OptimisticState:
    """Small per-entity store of short-lived optimistic values.

    Keys are entity-defined strings (usually a register name, or a logical
    field name such as ``"hvac_mode"``).  Each entry keeps its value plus the
    monotonic timestamp at which it was recorded so it can self-expire.
    """

    def __init__(self, ttl: float = DEFAULT_OPTIMISTIC_TTL) -> None:
        """Initialise an empty store with the given TTL in seconds."""
        self._ttl = ttl
        self._pending: dict[str, tuple[Any, float]] = {}

    def set_pending(self, key: str, value: Any) -> None:
        """Record an optimistic ``value`` for ``key``.

        Callers must only invoke this **after** a write has confirmed success.
        """
        self._pending[key] = (value, monotonic())

    def get_pending(self, key: str) -> Any | None:
        """Return the pending value for ``key`` while it is still fresh.

        Returns ``None`` when there is no pending value or it has expired.
        Reading an expired value also clears it so later reads fall back to the
        confirmed device state.  Optimistic control values are never ``None``,
        so ``None`` unambiguously means "no fresh pending value".
        """
        entry = self._pending.get(key)
        if entry is None:
            return None
        value, timestamp = entry
        if monotonic() - timestamp > self._ttl:
            del self._pending[key]
            return None
        return value

    def clear_pending(self, key: str) -> None:
        """Drop any pending value for ``key`` (no-op when absent)."""
        self._pending.pop(key, None)

    def clear_if_confirmed(
        self,
        key: str,
        confirmed_value: Any,
        comparator: Callable[[Any, Any], bool] | None = None,
        *,
        tolerance: float | None = None,
    ) -> bool:
        """Clear the pending value for ``key`` once ``confirmed_value`` matches.

        ``comparator`` takes ``(pending_value, confirmed_value)`` and returns
        ``True`` when the confirmed device value should supersede the optimistic
        one.  When no comparator is given, ``tolerance`` enables an approximate
        float comparison (useful for setpoints); otherwise strict equality is
        used.

        Returns ``True`` when a pending value was cleared.
        """
        entry = self._pending.get(key)
        if entry is None:
            return False
        pending_value, _timestamp = entry

        if comparator is not None:
            matched = comparator(pending_value, confirmed_value)
        elif tolerance is not None:
            try:
                matched = abs(float(pending_value) - float(confirmed_value)) <= tolerance
            except (TypeError, ValueError):
                matched = pending_value == confirmed_value
        else:
            matched = pending_value == confirmed_value

        if matched:
            del self._pending[key]
        return matched
