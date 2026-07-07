"""Unit tests for the optimistic UI state helper."""

from custom_components.thessla_green_modbus import optimistic
from custom_components.thessla_green_modbus.optimistic import (
    DEFAULT_OPTIMISTIC_TTL,
    OptimisticState,
)


def test_set_and_get_pending():
    """A stored value is returned while fresh."""
    store = OptimisticState()
    assert store.get_pending("k") is None
    store.set_pending("k", 42)
    assert store.get_pending("k") == 42


def test_clear_pending():
    """clear_pending drops the value; clearing an absent key is a no-op."""
    store = OptimisticState()
    store.set_pending("k", 1)
    store.clear_pending("k")
    assert store.get_pending("k") is None
    store.clear_pending("missing")  # no error


def test_clear_if_confirmed_exact():
    """Exact equality clears the pending value; a mismatch keeps it."""
    store = OptimisticState()
    store.set_pending("k", 5)
    assert store.clear_if_confirmed("k", 4) is False
    assert store.get_pending("k") == 5
    assert store.clear_if_confirmed("k", 5) is True
    assert store.get_pending("k") is None


def test_clear_if_confirmed_tolerance():
    """A float tolerance allows approximate confirmation."""
    store = OptimisticState()
    store.set_pending("t", 21.5)
    assert store.clear_if_confirmed("t", 21.6, tolerance=0.25) is True
    assert store.get_pending("t") is None


def test_clear_if_confirmed_tolerance_none_confirmed_does_not_crash():
    """A None confirmed value with a tolerance falls back to equality safely."""
    store = OptimisticState()
    store.set_pending("t", 21.5)
    assert store.clear_if_confirmed("t", None, tolerance=0.25) is False
    assert store.get_pending("t") == 21.5


def test_clear_if_confirmed_comparator():
    """A custom comparator drives the confirmation decision."""
    store = OptimisticState()
    store.set_pending("b", 4)
    matched = store.clear_if_confirmed(
        "b", 6, comparator=lambda pending, conf: bool(pending & 4) == bool(conf & 4)
    )
    assert matched is True
    assert store.get_pending("b") is None


def test_clear_if_confirmed_absent_key_returns_false():
    """Confirming a key with no pending value returns False."""
    store = OptimisticState()
    assert store.clear_if_confirmed("missing", 1) is False


def test_ttl_expiry(monkeypatch):
    """A value past its TTL is dropped and clears on read."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(optimistic, "monotonic", lambda: clock["now"])

    store = OptimisticState(ttl=DEFAULT_OPTIMISTIC_TTL)
    store.set_pending("x", 9)
    assert store.get_pending("x") == 9

    clock["now"] += DEFAULT_OPTIMISTIC_TTL + 1
    assert store.get_pending("x") is None
    # Reading after expiry also removed the entry.
    assert store._pending == {}


def test_default_ttl_value():
    """The default TTL matches the documented 10 seconds."""
    assert DEFAULT_OPTIMISTIC_TTL == 10.0
