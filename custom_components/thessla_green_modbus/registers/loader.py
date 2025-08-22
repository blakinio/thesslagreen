from __future__ import annotations

"""Load and work with Thessla Green register definitions."""

import csv
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel

_LOGGER = logging.getLogger(__name__)

_REGISTERS_FILE = Path(__file__).with_name("thessla_green_registers_full.json")


class _RegisterModel(BaseModel):
    """Pydantic model for a single register entry."""

    function: str
    address_dec: int
    name: str
    description: Optional[str] = None
    access: Optional[str] = None
    enum: Optional[Dict[str, int]] = None
    multiplier: Optional[float] = None
    resolution: Optional[float] = None
    length: Optional[int] = None

    class Config:
        extra = "ignore"


@dataclass(slots=True)
class Register:
    """Representation of a Modbus register."""

    function: str
    address: int
    name: str
    description: str | None = None
    access: str | None = None
    enum: Dict[str, int] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    length: int = 1


@dataclass(slots=True)
class ReadPlan:
    """Plan for reading a block of registers."""

    function: str
    address: int
    length: int


def _load_from_csv(files: Iterable[Path]) -> List[Dict[str, Any]]:
    """Load register definitions from CSV files with a deprecation warning."""

    _LOGGER.warning(
        "Register CSV files are deprecated and will be removed in a future release. "
        "Please migrate to JSON."
    )
    rows: List[Dict[str, Any]] = []
    for csv_file in files:
        with csv_file.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row["address_dec"] = int(row["address_dec"])
                except (KeyError, ValueError):
                    continue
                for field in ("multiplier", "resolution", "length"):
                    if row.get(field) not in (None, ""):
                        try:
                            if field == "length":
                                row[field] = int(row[field])
                            else:
                                row[field] = float(row[field])
                        except ValueError:
                            row[field] = None
                if row.get("enum"):
                    try:
                        row["enum"] = json.loads(row["enum"])
                    except json.JSONDecodeError:
                        row["enum"] = None
                rows.append(row)
    return rows


@lru_cache(maxsize=1)
def _load_raw() -> List[Dict[str, Any]]:
    """Load raw register definitions from JSON or CSV."""

    if _REGISTERS_FILE.exists():
        text = _REGISTERS_FILE.read_text(encoding="utf-8")
        try:
            data, _ = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - invalid JSON
            _LOGGER.error("Invalid register definition file: %s", exc)
            raise
    else:
        csv_files = list(_REGISTERS_FILE.parent.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No register definition file found at {_REGISTERS_FILE}")
        data = _load_from_csv(csv_files)
    if not isinstance(data, list):
        raise ValueError("Register definition file must contain a list")
    validated: List[Dict[str, Any]] = []
    for item in data:
        try:
            model = _RegisterModel.model_validate(item)
        except AttributeError:  # pragma: no cover - pydantic v1 fallback
            model = _RegisterModel.parse_obj(item)
        validated.append(model.dict())
    return validated


@lru_cache(maxsize=1)
def _load_registers() -> List[Register]:
    """Return all registers as :class:`Register` objects."""

    registers: List[Register] = []
    for entry in _load_raw():
        registers.append(
            Register(
                function=entry["function"],
                address=entry["address_dec"],
                name=entry["name"],
                description=entry.get("description"),
                access=entry.get("access"),
                enum=entry.get("enum"),
                multiplier=entry.get("multiplier"),
                resolution=entry.get("resolution"),
                length=entry.get("length") or 1,
            )
        )
    return registers


def get_all_registers() -> List[Register]:
    """Return all registers defined for the device."""

    return list(_load_registers())


def get_registers_by_function(fn: str) -> List[Register]:
    """Return registers for a specific Modbus function code."""

    fn_lower = fn.lower()
    return [r for r in _load_registers() if r.function.lower() == fn_lower]


def get_register_definition(name: str) -> Dict[str, Any]:
    """Return the raw register definition by name."""

    for entry in _load_raw():
        if entry.get("name") == name:
            return dict(entry)
    return {}


def group_reads(max_block_size: int = 64) -> List[ReadPlan]:
    """Group registers into consecutive read plans respecting block size."""

    plans: List[ReadPlan] = []
    regs_by_fn: Dict[str, List[Register]] = {}
    for reg in _load_registers():
        regs_by_fn.setdefault(reg.function, []).append(reg)

    for fn, regs in regs_by_fn.items():
        sorted_regs = sorted(regs, key=lambda r: r.address)
        if not sorted_regs:
            continue
        start = sorted_regs[0].address
        length = sorted_regs[0].length
        prev_end = start + length
        for reg in sorted_regs[1:]:
            reg_end = reg.address + reg.length
            if reg.address == prev_end and length + reg.length <= max_block_size:
                length += reg.length
            else:
                plans.append(ReadPlan(fn, start, length))
                start = reg.address
                length = reg.length
            prev_end = reg_end
        plans.append(ReadPlan(fn, start, length))
    return plans


__all__ = [
    "Register",
    "ReadPlan",
    "get_all_registers",
    "get_registers_by_function",
    "get_register_definition",
    "group_reads",
]
