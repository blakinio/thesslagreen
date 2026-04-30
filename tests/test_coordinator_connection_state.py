"""Tests for coordinator connection state bookkeeping helpers."""

from __future__ import annotations

from custom_components.thessla_green_modbus.coordinator.connection_state import (
    mark_connection_disconnected,
    mark_connection_established,
    mark_connection_failure,
)


def test_mark_connection_established_sets_online() -> None:
    holder = {"offline": True}

    mark_connection_established(offline_state_setter=lambda value: holder.__setitem__("offline", value))

    assert holder["offline"] is False


def test_mark_connection_failure_increments_counter_and_sets_offline() -> None:
    holder = {"offline": False}
    statistics = {"connection_errors": 2}

    mark_connection_failure(
        statistics=statistics,
        offline_state_setter=lambda value: holder.__setitem__("offline", value),
    )

    assert statistics["connection_errors"] == 3
    assert holder["offline"] is True


def test_mark_connection_disconnected_sets_offline() -> None:
    holder = {"offline": False}

    mark_connection_disconnected(
        offline_state_setter=lambda value: holder.__setitem__("offline", value)
    )

    assert holder["offline"] is True
