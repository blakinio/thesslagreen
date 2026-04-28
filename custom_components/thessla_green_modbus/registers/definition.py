"""Register loading/planning dataclasses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ReadPlan:
    """Plan describing a consecutive block of registers to read."""

    function: int | str
    address: int
    length: int
