"""Connection state transitions for coordinator runtime bookkeeping."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


def mark_connection_established(*, offline_state_setter: Any) -> None:
    """Mark coordinator runtime as connected."""
    offline_state_setter(False)


def mark_connection_failure(*, statistics: MutableMapping[str, Any], offline_state_setter: Any) -> None:
    """Record connection failure counters and switch coordinator offline."""
    statistics["connection_errors"] += 1
    offline_state_setter(True)


def mark_connection_disconnected(*, offline_state_setter: Any) -> None:
    """Mark coordinator runtime as disconnected."""
    offline_state_setter(True)
