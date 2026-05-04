"""Helper utilities for scanner register/bit read workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast


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
