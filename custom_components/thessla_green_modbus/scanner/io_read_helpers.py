"""Helper utilities for scanner register/bit read workflows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

from ..modbus_helpers import chunk_register_range

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReadAttemptMeta:
    """Address metadata describing a single register-read attempt."""

    start: int
    end: int
    address: int
    count: int


def build_read_attempt_meta(address: int, count: int) -> ReadAttemptMeta:
    """Build normalized metadata for a register read attempt."""
    return ReadAttemptMeta(start=address, end=address + count - 1, address=address, count=count)


def iter_grouped_read_chunks(start: int, count: int, chunk_builder: Any) -> list[tuple[int, int]]:
    """Create grouped chunk plan for optimized/batched reads."""
    return list(chunk_builder(start, count))


def build_register_chunks(start: int, count: int, batch_size: int) -> list[tuple[int, int]]:
    """Build a batched chunk plan for a contiguous register range."""
    return iter_grouped_read_chunks(
        start,
        count,
        lambda chunk_start, chunk_count: chunk_register_range(chunk_start, chunk_count, batch_size),
    )


def append_read_block(results: list[int], block: list[int] | None) -> bool:
    """Append a decoded block to results and report if read should continue."""
    if block is None:
        return False
    results.extend(block)
    return True


def build_success_result(response: Any) -> list[int]:
    """Build normalized register-read success payload from Modbus response."""
    return cast(list[int], response.registers)


def normalize_bit_read_result(response: Any, count: int) -> list[bool] | None:
    """Normalize bit-read response payload for coils/discrete inputs."""
    if response is None or response.isError():
        return None
    return cast(list[bool], response.bits[:count])


def classify_skip_range(
    *,
    start: int,
    end: int,
    skip_cache: bool,
    unsupported_ranges: set[tuple[int, int]],
    failed_registers: set[int],
    expand_cached_failed_range: Any,
) -> tuple[bool, int, int]:
    """Classify whether a read range should be skipped as unsupported/cached-failed."""
    if skip_cache:
        return False, start, end
    if any(skip_start <= start and end <= skip_end for skip_start, skip_end in unsupported_ranges):
        return True, start, end
    cached_failed_range = expand_cached_failed_range(
        start=start,
        end=end,
        failed_registers=failed_registers,
    )
    if cached_failed_range is None:
        return False, start, end
    return True, cached_failed_range[0], cached_failed_range[1]


def should_log_terminal_failure(register_type: str, aborted_transiently: bool) -> bool:
    """Return True when terminal failure should be logged for the read type."""
    if not aborted_transiently:
        return True
    return register_type == "holding_registers"


def mark_failed_addresses(scanner: Any, register_type: str, start: int, end: int) -> None:
    """Track read failures for a contiguous address range."""
    scanner.failed_addresses["modbus_exceptions"][register_type].update(range(start, end + 1))


def log_read_abort(kind: str, start: int, end: int, attempt: int, retry: int) -> None:
    """Log a transiently aborted read due to timeout/cancellation."""
    _LOGGER.warning(
        "Aborted reading %s registers %d-%d after %d/%d attempts due to timeout/cancellation",
        kind,
        start,
        end,
        attempt,
        retry,
    )


def log_read_failure(kind: str, start: int, end: int, retry: int) -> None:
    """Log terminal read failure after retry budget is exhausted."""
    _LOGGER.error("Failed to read %s registers %d-%d after %d retries", kind, start, end, retry)
