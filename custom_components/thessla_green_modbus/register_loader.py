"""Compatibility wrapper around the JSON register loader.

Historically the project exposed a :class:`RegisterLoader` class that read
register definitions from CSV files.  The integration now uses a JSON file as
the single source of truth.  This module keeps a minimal subset of the old API
so external tools and some tests can continue to work while emitting a warning
about the deprecation.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Tuple, TYPE_CHECKING

from .registers import get_all_registers, get_registers_by_function

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .registers import Register

_LOGGER = logging.getLogger(__name__)


@dataclass
class RegisterLoader:  # pragma: no cover - thin compatibility layer
    """Backward compatible loader returning simple register maps."""

    registers: Dict[str, Register]
    input_registers: Dict[str, int]
    holding_registers: Dict[str, int]
    coil_registers: Dict[str, int]
    discrete_registers: Dict[str, int]
    enums: Dict[str, Dict[str, int]]
    multipliers: Dict[str, float]
    resolutions: Dict[str, float]
    group_reads: Dict[str, List[Tuple[int, int]]]

    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            _LOGGER.warning("RegisterLoader path argument is ignored; JSON definitions are built-in")

        regs = get_all_registers()
        self.registers = {r.name: r for r in regs}
        self.input_registers = {r.name: r.address for r in regs if r.function == "04"}
        self.holding_registers = {r.name: r.address for r in regs if r.function == "03"}
        self.coil_registers = {r.name: r.address for r in regs if r.function == "01"}
        self.discrete_registers = {r.name: r.address for r in regs if r.function == "02"}
        self.enums = {r.name: r.enum for r in regs if r.enum}
        self.multipliers = {r.name: r.multiplier for r in regs if r.multiplier}
        self.resolutions = {r.name: r.resolution for r in regs if r.resolution}

        groups: Dict[str, List[Tuple[int, int]]] = {"input": [], "holding": [], "coil": [], "discrete": []}
        for fn, key in [("04", "input"), ("03", "holding"), ("01", "coil"), ("02", "discrete")]:
            addresses: List[int] = []
            for reg in get_registers_by_function(fn):
                addresses.extend(range(reg.address, reg.address + max(1, reg.length)))
            if not addresses:
                continue
            addresses.sort()
            start = prev = addresses[0]
            length = 1
            for addr in addresses[1:]:
                if addr == prev + 1:
                    length += 1
                else:
                    groups[key].append((start, length))
                    start = addr
                    length = 1
                prev = addr
            groups[key].append((start, length))
        self.group_reads = groups


__all__ = ["RegisterLoader"]

