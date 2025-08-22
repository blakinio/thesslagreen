"""Compatibility wrapper around the JSON register loader.

Historically the project exposed a :class:`RegisterLoader` class that read
register definitions from CSV files. The integration now uses a JSON file as
the single source of truth. CSV support is retained solely for backward
compatibility and the loader logs a warning whenever it is invoked.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from .registers import Register, get_all_registers, get_registers_by_function
from .utils import _to_snake_case

_LOGGER = logging.getLogger(__name__)


def _csv_path_from_arg(path: Path | None) -> Path | None:
    """Return CSV file path if *path* points to a CSV definition."""
    if path is None:
        return None
    if path.is_file() and path.suffix.lower() == ".csv":
        return path
    if path.is_dir():
        candidate = path / "modbus_registers.csv"
        if candidate.exists():
            return candidate
    return None


def _load_from_csv(csv_path: Path) -> List[Register]:
    """Parse legacy CSV register definition file."""
    registers: List[Register] = []
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            code = row.get("Function_Code")
            if not code or code.startswith("#"):
                continue
            name_raw = row.get("Register_Name")
            if not isinstance(name_raw, str) or not name_raw.strip():
                continue
            name = _to_snake_case(name_raw)
            try:
                address = int(row.get("Address_DEC", 0))
            except (TypeError, ValueError):
                continue

            multiplier: float | None = None
            if row.get("Multiplier") not in (None, ""):
                try:
                    multiplier = float(row["Multiplier"])
                except ValueError:
                    multiplier = None

            enum: Dict[int, str] | None = None
            enum_text = row.get("Unit") or row.get("Information")
            if enum_text and "-" in enum_text:
                enum = {}
                for part in enum_text.split(";"):
                    part = part.strip()
                    if not part:
                        continue
                    try:
                        num_str, label = part.split("-", 1)
                        enum[int(num_str.strip())] = _to_snake_case(label.strip())
                    except ValueError:
                        continue

            registers.append(
                Register(
                    function=str(code).zfill(2),
                    address=address,
                    name=name,
                    access=str(row.get("Access", "")),
                    description=row.get("Description"),
                    unit=row.get("Unit"),
                    multiplier=multiplier,
                    enum=enum,
                )
            )
    return registers


@dataclass
class RegisterLoader:  # pragma: no cover - thin compatibility layer
    """Backward compatible loader returning simple register maps.

    CSV input is deprecated; instantiating this class logs a warning and uses
    the bundled JSON definitions instead.
    """

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
        csv_path = _csv_path_from_arg(path)
        if csv_path:
            _LOGGER.warning(
                "CSV register files are deprecated; JSON definitions are authoritative"
            )
            regs = _load_from_csv(csv_path)
        else:
            if path is not None:
                _LOGGER.warning(
                    "RegisterLoader path argument is ignored; JSON definitions are built-in"
                )
            regs = get_all_registers()
        self.registers = {r.name: r for r in regs}
        self.input_registers = {r.name: r.address for r in regs if r.function == "04"}
        self.holding_registers = {r.name: r.address for r in regs if r.function == "03"}
        self.coil_registers = {r.name: r.address for r in regs if r.function == "01"}
        self.discrete_registers = {r.name: r.address for r in regs if r.function == "02"}
        self.enums = {r.name: r.enum for r in regs if r.enum}
        self.multipliers = {r.name: r.multiplier for r in regs if r.multiplier}
        self.resolutions = {r.name: r.resolution for r in regs if r.resolution}

        groups: Dict[str, List[Tuple[int, int]]] = {
            "input": [],
            "holding": [],
            "coil": [],
            "discrete": [],
        }
        regs_by_fn: Dict[str, List[int]] = {}
        for reg in regs:
            regs_by_fn.setdefault(reg.function, []).extend(
                range(reg.address, reg.address + max(1, reg.length))
            )
        for fn, key in [("04", "input"), ("03", "holding"), ("01", "coil"), ("02", "discrete")]:
            addresses = regs_by_fn.get(fn, [])
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

