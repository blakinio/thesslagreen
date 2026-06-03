"""Unit tests for scanner/io_core.py pure and pure-adjacent functions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from custom_components.thessla_green_modbus.scanner.io_core import (
    _expand_cached_failed_range,
    is_request_cancelled_error,
    resolve_transport_and_client,
    track_holding_failure,
    track_input_failure,
    unpack_read_args,
)
from pymodbus.exceptions import ConnectionException

# ---------------------------------------------------------------------------
# is_request_cancelled_error
# ---------------------------------------------------------------------------


def test_is_cancelled_request_cancelled_outside_pymodbus() -> None:
    exc = Exception("request cancelled outside pymodbus")
    assert is_request_cancelled_error(exc) is True


def test_is_cancelled_contains_cancelled() -> None:
    exc = Exception("Connection was cancelled by asyncio")
    assert is_request_cancelled_error(exc) is True


def test_is_cancelled_case_insensitive() -> None:
    exc = Exception("CANCELLED by scheduler")
    assert is_request_cancelled_error(exc) is True


def test_is_cancelled_unrelated_error() -> None:
    exc = ConnectionException("timeout")
    assert is_request_cancelled_error(exc) is False


def test_is_cancelled_empty_message() -> None:
    assert is_request_cancelled_error(Exception("")) is False


# ---------------------------------------------------------------------------
# unpack_read_args
# ---------------------------------------------------------------------------


def test_unpack_read_args_count_none_two_arg_form() -> None:
    scanner = object()
    client, address, count = unpack_read_args(scanner, 42, 5, None)
    assert client is None
    assert address == 42
    assert count == 5


def test_unpack_read_args_client_is_int_falls_back() -> None:
    scanner = object()
    client, address, count = unpack_read_args(scanner, 10, 3, None)
    assert client is None
    assert address == 10
    assert count == 3


def test_unpack_read_args_full_three_arg_form() -> None:
    scanner = object()
    fake_client = object()
    client, address, count = unpack_read_args(scanner, fake_client, 100, 4)
    assert client is fake_client
    assert address == 100
    assert count == 4


# ---------------------------------------------------------------------------
# resolve_transport_and_client
# ---------------------------------------------------------------------------


def test_resolve_returns_client_when_provided() -> None:
    fake_client = object()
    scanner = SimpleNamespace(_transport=None, _client=None)
    transport, client = resolve_transport_and_client(scanner, fake_client)
    assert transport is None
    assert client is fake_client


def test_resolve_falls_back_to_transport_when_no_client() -> None:
    fake_transport = object()
    scanner = SimpleNamespace(_transport=fake_transport, _client=None)
    transport, client = resolve_transport_and_client(scanner, None)
    assert transport is fake_transport
    assert client is None


def test_resolve_falls_back_to_scanner_client() -> None:
    fake_client = object()
    scanner = SimpleNamespace(_transport=None, _client=fake_client)
    transport, client = resolve_transport_and_client(scanner, None)
    assert transport is None
    assert client is fake_client


def test_resolve_raises_when_all_none() -> None:
    scanner = SimpleNamespace(_transport=None, _client=None)
    with pytest.raises(ConnectionException):
        resolve_transport_and_client(scanner, None)


# ---------------------------------------------------------------------------
# _expand_cached_failed_range
# ---------------------------------------------------------------------------


def test_expand_no_failed_in_range_returns_none() -> None:
    result = _expand_cached_failed_range(start=10, end=15, failed_registers=set())
    assert result is None


def test_expand_failed_in_range_returns_range() -> None:
    result = _expand_cached_failed_range(start=10, end=15, failed_registers={12})
    assert result is not None
    start, end = result
    assert start <= 12 <= end


def test_expand_expands_contiguous_block() -> None:
    failed = {10, 11, 12, 13}
    result = _expand_cached_failed_range(start=11, end=12, failed_registers=failed)
    assert result == (10, 13)


def test_expand_expands_upward() -> None:
    failed = {5, 6, 7}
    result = _expand_cached_failed_range(start=5, end=5, failed_registers=failed)
    assert result == (5, 7)


def test_expand_no_overlap_returns_none() -> None:
    result = _expand_cached_failed_range(start=20, end=25, failed_registers={10, 11})
    assert result is None


# ---------------------------------------------------------------------------
# track_input_failure / track_holding_failure
# ---------------------------------------------------------------------------


def _make_scanner(retry: int = 3) -> SimpleNamespace:
    return SimpleNamespace(
        retry=retry,
        _input_failures={},
        _holding_failures={},
        _failed_input=set(),
        _failed_holding=set(),
        failed_addresses={
            "modbus_exceptions": {
                "input_registers": set(),
                "holding_registers": set(),
            }
        },
    )


def test_track_input_failure_ignores_multi_count() -> None:
    scanner = _make_scanner()
    track_input_failure(scanner, count=4, address=10)
    assert scanner._input_failures == {}


def test_track_input_failure_increments_counter() -> None:
    scanner = _make_scanner(retry=3)
    track_input_failure(scanner, count=1, address=10)
    assert scanner._input_failures[10] == 1


def test_track_input_failure_marks_failed_after_retry_exhausted() -> None:
    scanner = _make_scanner(retry=2)
    track_input_failure(scanner, count=1, address=10)
    assert 10 not in scanner._failed_input

    track_input_failure(scanner, count=1, address=10)
    assert 10 in scanner._failed_input
    assert 10 in scanner.failed_addresses["modbus_exceptions"]["input_registers"]


def test_track_holding_failure_increments_counter() -> None:
    scanner = _make_scanner(retry=3)
    track_holding_failure(scanner, count=1, address=20)
    assert scanner._holding_failures[20] == 1


def test_track_holding_failure_marks_failed_after_retry_exhausted() -> None:
    scanner = _make_scanner(retry=2)
    track_holding_failure(scanner, count=1, address=20)
    track_holding_failure(scanner, count=1, address=20)
    assert 20 in scanner._failed_holding
    assert 20 in scanner.failed_addresses["modbus_exceptions"]["holding_registers"]


def test_track_holding_failure_ignores_multi_count() -> None:
    scanner = _make_scanner()
    track_holding_failure(scanner, count=2, address=20)
    assert scanner._holding_failures == {}


def test_track_failure_no_duplicate_in_failed_set() -> None:
    scanner = _make_scanner(retry=2)
    for _ in range(5):
        track_input_failure(scanner, count=1, address=30)
    assert len([x for x in scanner._failed_input if x == 30]) == 1
