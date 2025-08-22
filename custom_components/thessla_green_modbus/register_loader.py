"""Helpers for working with JSON-based register definitions.

The register list lives in ``registers/thessla_green_registers_full.json`` and
this loader is mainly used by tests and development utilities.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

_LOGGER = logging.getLogger(__name__)


@dataclass
class Register:
    """Representation of a single Modbus register."""

    function: str
    address: int
    access: str
    name: str
    description: str
    enum: Dict[str, int] | None = None
    multiplier: float | None = None
    resolution: float | None = None


class RegisterLoader:
    """Load and organize register definitions."""

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            path = Path(__file__).parent / "registers" / "thessla_green_registers_full.json"

        if path.exists() and path.suffix.lower() == ".json":
            with path.open(encoding="utf-8") as f:
                raw = json.load(f)
        elif path.exists() and path.suffix.lower() == ".csv":
            raw = self._load_from_csv([path])
        else:
            # Attempt fallback
            json_path = path if path.suffix else path.with_suffix(".json")
            if json_path.exists():
                with json_path.open(encoding="utf-8") as f:
                    raw = json.load(f)
            else:
                csv_dir = path.parent if path.suffix else path
                csv_files = list(csv_dir.glob("*.csv"))
                if not csv_files:
                    raise FileNotFoundError(f"No register definition file found at {path}")
                raw = self._load_from_csv(csv_files)

        self.registers: Dict[str, Register] = {}
        self.input_registers: Dict[str, int] = {}
        self.holding_registers: Dict[str, int] = {}
        self.coil_registers: Dict[str, int] = {}
        self.discrete_registers: Dict[str, int] = {}
        self.enums: Dict[str, Dict[str, int]] = {}
        self.multipliers: Dict[str, float] = {}
        self.resolutions: Dict[str, float] = {}

        for entry in raw:
            reg = Register(
                function=entry["function"],
                address=entry["address_dec"],
                access=entry.get("access", "ro"),
                name=entry["name"],
                description=entry.get("description", ""),
                enum=entry.get("enum"),
                multiplier=entry.get("multiplier"),
                resolution=entry.get("resolution"),
            )
            self.registers[reg.name] = reg
            if reg.function == "input":
                self.input_registers[reg.name] = reg.address
            elif reg.function == "holding":
                self.holding_registers[reg.name] = reg.address
            elif reg.function == "coil":
                self.coil_registers[reg.name] = reg.address
            elif reg.function == "discrete":
                self.discrete_registers[reg.name] = reg.address
            if reg.enum is not None:
                self.enums[reg.name] = reg.enum
            if reg.multiplier is not None:
                self.multipliers[reg.name] = reg.multiplier
            if reg.resolution is not None:
                self.resolutions[reg.name] = reg.resolution

        self.group_reads: Dict[str, List[Tuple[int, int]]] = self._compute_group_reads()

    def _load_from_csv(self, files: Iterable[Path]) -> List[Dict[str, Any]]:
        """Load register definitions from CSV files."""
        _LOGGER.warning(
            "Register CSV files are deprecated and will be removed in a future release. "
            "Please migrate to JSON."
        )
        data: List[Dict[str, Any]] = []
        for csv_file in files:
            with csv_file.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        row["address_dec"] = int(row["address_dec"])
                    except (KeyError, ValueError):
                        continue
                    for field in ("multiplier", "resolution"):
                        if row.get(field) not in (None, ""):
                            try:
                                row[field] = float(row[field])
                            except ValueError:
                                row[field] = None
                    if "enum" in row and row["enum"]:
                        try:
                            row["enum"] = json.loads(row["enum"])
                        except json.JSONDecodeError:
                            row["enum"] = None
                    data.append(row)
        return data

    def _compute_group_reads(self) -> Dict[str, List[Tuple[int, int]]]:
        """Compute contiguous address groups for efficient reading."""

        groups: Dict[str, List[Tuple[int, int]]] = {}
        mapping = {
            "input": self.input_registers,
            "holding": self.holding_registers,
            "coil": self.coil_registers,
            "discrete": self.discrete_registers,
        }
        for func, regs in mapping.items():
            addresses = sorted(regs.values())
            if not addresses:
                groups[func] = []
                continue
            ranges: List[Tuple[int, int]] = []
            start = prev = addresses[0]
            count = 1
            for addr in addresses[1:]:
                if addr == prev + 1:
                    count += 1
                else:
                    ranges.append((start, count))
                    start = addr
                    count = 1
                prev = addr
            ranges.append((start, count))
            groups[func] = ranges
        return groups
