from __future__ import annotations

"""Register definition helpers for ThesslaGreen devices.

This module loads register metadata from ``thessla_green_registers_full.json``
using a Pydantic schema. Results are cached in memory and exposed via
``get_all_registers`` and ``get_registers_by_function``. A small CSV
compatibility layer is provided for legacy files and will emit a warning when
used. The module also exposes ``group_reads`` which groups consecutive
registers into :class:`ReadPlan` blocks.
"""

import csv
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from pydantic import BaseModel, Field

_LOGGER = logging.getLogger(__name__)

# Path to JSON register definition file. Tests may monkeypatch this.
_REGISTERS_FILE = Path(__file__).resolve().parents[3] / "thessla_green_registers_full.json"


# ---------------------------------------------------------------------------
# Pydantic models describing the JSON structure
# ---------------------------------------------------------------------------


class _RegisterModel(BaseModel):
    function: str
    address_dec: int
    name: str
    access: str | None = "ro"
    description: str | None = None
    enum: Dict[str, str] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    length: int | None = 1
    min: float | None = Field(None, alias="min")
    max: float | None = Field(None, alias="max")

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"


class _RegisterFileModel(BaseModel):
    schema_version: str
    generated_at: str
    registers: List[_RegisterModel]

    class Config:
        extra = "ignore"


# ---------------------------------------------------------------------------
# Dataclasses exposed to callers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Register:
    """Representation of a single Modbus register."""

    function: str
    address: int
    name: str
    access: str
    description: str | None = None
    enum: Dict[str, int] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    length: int = 1
    minimum: float | None = None
    maximum: float | None = None
    bcd: bool = False

    # ------------------------------------------------------------------
    # Value helpers
    # ------------------------------------------------------------------
    def decode(self, raw: int) -> Any:
        """Decode a raw register value."""

        if self.bcd:
            hours_bcd = (raw >> 8) & 0xFF
            mins_bcd = raw & 0xFF
            hours = (hours_bcd >> 4) * 10 + (hours_bcd & 0x0F)
            mins = (mins_bcd >> 4) * 10 + (mins_bcd & 0x0F)
            return f"{hours:02d}:{mins:02d}"

        value: Any = raw

        if self.enum:
            for key, val in self.enum.items():
                if val == raw:
                    return key

        if self.multiplier is not None:
            value = value * self.multiplier

        if self.resolution is not None and isinstance(value, (int, float)):
            value = round(value / self.resolution) * self.resolution

        return value

    def encode(self, value: Any) -> int:
        """Encode a value to the raw register format."""

        if self.bcd:
            if isinstance(value, str):
                hours_str, mins_str = value.split(":")
                hours = int(hours_str)
                mins = int(mins_str)
            else:  # tuple or sequence
                hours, mins = value
            hours_bcd = ((hours // 10) << 4) | (hours % 10)
            mins_bcd = ((mins // 10) << 4) | (mins % 10)
            return (hours_bcd << 8) | mins_bcd

        raw: Any = value

        if self.enum and isinstance(value, str):
            if value not in self.enum:
                raise ValueError(f"Invalid enum value {value} for {self.name}")
            raw = self.enum[value]

        if self.multiplier is not None:
            raw = float(raw) / self.multiplier

        if self.resolution is not None:
            step = self.resolution
            raw = round(float(raw) / step) * step

        return int(raw)


@dataclass(slots=True)
class ReadPlan:
    """Plan for reading a block of registers."""

    function: str
    address: int
    length: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_from_csv(path: Path) -> List[Dict[str, Any]]:
    """Load register definitions from a CSV file with deprecation warning."""

    _LOGGER.warning(
        "Register CSV files are deprecated and will be removed in a future release. "
        "Please migrate to JSON."
    )
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
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
            rows.append(row)
    return rows


@lru_cache(maxsize=1)
def _load_register_definitions() -> List[Register]:
    """Load and validate register definitions from JSON or CSV."""

    path = _REGISTERS_FILE
    if path.exists() and path.suffix.lower() == ".json":
        text = path.read_text(encoding="utf-8")
        try:
            model = _RegisterFileModel.model_validate_json(text)
        except AttributeError:  # pragma: no cover - pydantic v1 fallback
            model = _RegisterFileModel.parse_raw(text)
        regs: List[Register] = []
        for item in model.registers:
            name_lower = (item.name or "").lower()
            bcd = bool(
                name_lower.startswith("schedule_")
                and name_lower.endswith(("_start", "_end"))
            )
            enum_map = {v: int(k) for k, v in (item.enum or {}).items()}
            regs.append(
                Register(
                    function=item.function,
                    address=item.address_dec,
                    name=item.name,
                    access=item.access or "ro",
                    description=item.description,
                    enum=enum_map or None,
                    multiplier=item.multiplier,
                    resolution=item.resolution,
                    length=item.length or 1,
                    minimum=item.min,
                    maximum=item.max,
                    bcd=bcd,
                )
            )
        return regs

    # CSV fallback
    if path.suffix.lower() == ".csv" and path.exists():
        raw = _load_from_csv(path)
    else:
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            raw = _load_from_csv(csv_path)
        else:
            raise FileNotFoundError(f"Register definition file not found: {path}")

    regs: List[Register] = []
    for row in raw:
        try:
            item = _RegisterModel(**row)
        except Exception:  # pragma: no cover - defensive
            continue
        name_lower = (item.name or "").lower()
        bcd = bool(
            name_lower.startswith("schedule_")
            and name_lower.endswith(("_start", "_end"))
        )
        enum_map = {v: int(k) for k, v in (item.enum or {}).items()}
        regs.append(
            Register(
                function=item.function,
                address=item.address_dec,
                name=item.name,
                access=item.access or "ro",
                description=item.description,
                enum=enum_map or None,
                multiplier=item.multiplier,
                resolution=item.resolution,
                length=item.length or 1,
                minimum=item.min,
                maximum=item.max,
                bcd=bcd,
            )
        )
    return regs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_all_registers() -> List[Register]:
    """Return all known registers."""

    return list(_load_register_definitions())


def get_registers_by_function(fn: str) -> List[Register]:
    """Return registers matching a Modbus function code or name."""

    mapping = {
        "01": "01",
        "coil": "01",
        "coils": "01",
        "02": "02",
        "discrete": "02",
        "discrete_input": "02",
        "04": "04",
        "input": "04",
        "03": "03",
        "holding": "03",
    }
    fn_code = mapping.get(fn.lower(), fn)
    return [r for r in get_all_registers() if r.function == fn_code]


def group_reads(max_block_size: int = 64) -> List[ReadPlan]:
    """Group registers into contiguous blocks per function."""

    plans: List[ReadPlan] = []
    regs_by_fn: Dict[str, List[Register]] = {}
    for reg in get_all_registers():
        regs_by_fn.setdefault(reg.function, []).append(reg)

    for fn, regs in regs_by_fn.items():
        regs.sort(key=lambda r: r.address)
        if not regs:
            continue
        start = regs[0].address
        length = regs[0].length
        prev_end = start + length
        for reg in regs[1:]:
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


def get_register_definition(name: str) -> Register | None:
    """Return the :class:`Register` definition for ``name`` if available."""

    for reg in get_all_registers():
        if reg.name == name:
            return reg
    return None


def group_addresses(addresses: Iterable[int], max_block_size: int = 64) -> List[Tuple[int, int]]:
    """Group bare addresses into contiguous blocks."""

    sorted_addresses = sorted(set(addresses))
    if not sorted_addresses:
        return []
    groups: List[Tuple[int, int]] = []
    start = prev = sorted_addresses[0]
    for addr in sorted_addresses[1:]:
        if addr == prev + 1 and (addr - start) < max_block_size:
            prev = addr
            continue
        groups.append((start, prev - start + 1))
        start = prev = addr
    groups.append((start, prev - start + 1))
    return groups
