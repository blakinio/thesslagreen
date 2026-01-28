"""Retry policy helpers for Modbus calls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RetryPolicy:
    """Simple retry policy metadata for Modbus operations."""

    max_attempts: int = 1

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            self.max_attempts = 1
