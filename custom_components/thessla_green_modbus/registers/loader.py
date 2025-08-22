"""Load and organise Thessla Green Modbus register definitions.


The register metadata used by development tools and tests is stored in
``thessla_green_registers_full.json``. This module exposes helper classes and
functions to read that file and to organise registers into contiguous read
blocks.
"""

from __future__ import annotations

The integration stores a canonical list of all supported Modbus registers in
``thessla_green_registers_full.json``.  This module reads that file once, caches
the result and exposes a small helper API used by the integration and tests.

The loader prefers the JSON file but will fall back to legacy CSV files placed
in the same directory.  When falling back a deprecation warning is logged so
users can migrate to the JSON format.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import csv

import logging
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel
from typing import Any, Dict, Iterable, List

from pydantic import BaseModel, Field

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Register representation
# Data models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Register:
    """Definition of a single Modbus register."""

    function: str
    address: int
    name: str
    access: str
    length: int = 1
    enum: Dict[str, Any] | None = None
    access: str
    name: str
    description: str | None = None
    unit: str | None = None
    resolution: float | None = None
    multiplier: float | None = None
    min: float | None = None
    max: float | None = None
    enum: Dict[str, int] | None = None
    notes: str | None = None
    extra: Dict[str, Any] | None = None
    length: int = 1

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Register":
        """Create a :class:`Register` instance from raw dictionary data."""

        try:
            function = str(data["function"])
            address_dec = data.get("address_dec")
            if address_dec is not None:
                address = int(address_dec)
            else:
                address = int(str(data.get("address_hex")), 16)
            name = str(data["name"])
            access = str(data.get("access", ""))
        except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - defensive
            _LOGGER.error("Invalid register definition: %s", data)
            raise ValueError(f"Invalid register definition: {data}") from exc

        length = int(data.get("length") or 1)
        enum_raw: Dict[str, Any] | None = data.get("enum")
        enum = {k: v for k, v in enum_raw.items()} if enum_raw else None
        multiplier = data.get("multiplier")
        resolution = data.get("resolution")
        description = data.get("description")
        min_val = data.get("min")
        max_val = data.get("max")
        default = data.get("default")
        unit = data.get("unit")
        information = data.get("information")

        name_lower = name.lower()
        bcd = bool(
            data.get("bcd")
            or (name_lower.startswith("schedule_") and name_lower.endswith(("_start", "_end")))
        )

        extra: Dict[str, Any] | None = data.get("extra")
        if extra is None and name_lower.startswith("setting_"):
            extra = {"aatt": True}

        return cls(
            function=function,
            address=address,
            name=name,
            access=access,
            length=length,
            enum=enum,
            multiplier=multiplier,
            resolution=resolution,
            description=description,
            min=min_val,
            max=max_val,
            default=default,
            unit=unit,
            information=information,
            bcd=bcd,
            extra=extra,
        )

    # ------------------------------------------------------------------
    # Value helpers
    # ------------------------------------------------------------------
    def decode(self, raw: int) -> Any:
        """Decode a raw register value using register metadata."""
    def decode(self, raw: int) -> Any:
        """Decode a raw value according to register metadata."""

        if raw == 0x8000:
            return None

        value: Any = raw

        if self.multiplier is not None:
            value = value * self.multiplier

        if self.resolution is not None:
            steps = round(value / self.resolution)
            value = steps * self.resolution

        return value

    def encode(self, value: Any) -> int:
        """Encode a value to raw register format."""

        if self.bcd:
            if isinstance(value, str):
                hours_str, mins_str = value.split(":")
                hours = int(hours_str)
                mins = int(mins_str)
            else:
                hours, mins = divmod(int(value), 60)
            hours_bcd = ((hours // 10) << 4) | (hours % 10)
            mins_bcd = ((mins // 10) << 4) | (mins % 10)
            return (hours_bcd << 8) | mins_bcd

        if self.extra and self.extra.get("aatt"):
            if isinstance(value, (tuple, list)):
                airflow, temp = value
            elif isinstance(value, dict):
                airflow = value["airflow"]
                temp = value["temp"]
            else:
                airflow, temp = value  # type: ignore[misc]
            airflow_int = int(round(float(airflow)))
            temp_raw = int(round(float(temp) * 2))
            return (airflow_int << 8) | (temp_raw & 0xFF)

        raw = value
        if self.enum and isinstance(value, str):
            for raw_str, label in self.enum.items():
                if label == value:
                    raw = int(raw_str)
                    break
        if self.multiplier is not None:
            raw = int(round(float(raw) / self.multiplier))
        if self.resolution is not None:
            step = self.resolution
            raw = int(round(float(raw) / step) * step)
        return int(raw)


# ---------------------------------------------------------------------------
# Pydantic models describing the register file structure
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ReadPlan:
    """Plan describing a contiguous block of registers to read."""

    function: str
    address: int
    length: int


class _RegisterModel(BaseModel):
    """Internal model used for validating JSON entries."""

    function: str = Field(pattern=r"^(01|02|03|04|input|holding|coil|discrete)$")
    address_dec: int
    name: str

    description: str | None = None
    access: str | None = None
    enum: Dict[str, Any] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    length: int | None = None
    min: float | None = None
    max: float | None = None
    default: float | None = None
    unit: str | None = None
    information: str | None = None
    bcd: bool | None = None
    access: str = "ro"
    description: str | None = None
    unit: str | None = None
    resolution: float | None = None
    multiplier: float | None = None
    min: float | None = None
    max: float | None = None
    enum: Dict[str, int] | None = None
    notes: str | None = None
    extra: Dict[str, Any] | None = None

    class Config:
        extra = "ignore"


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


_REGISTERS_PATH = Path(__file__).with_name("thessla_green_registers_full.json")


def _load_from_csv(files: Iterable[Path]) -> List[Dict[str, Any]]:
    """Load register definitions from CSV files (legacy support)."""

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
                for field in ("multiplier", "resolution", "min", "max"):
                    if row.get(field) not in (None, ""):
                        try:
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

    if _REGISTERS_PATH.exists():
        text = _REGISTERS_PATH.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            items = data.get("registers", [])
        else:
            items = data
        return [
            _RegisterModel.model_validate(item).model_dump()
            for item in items
        ]

    csv_files = list(_REGISTERS_PATH.parent.glob("*.csv"))
    if csv_files:
        return _load_from_csv(csv_files)


# ---------------------------------------------------------------------------
# Register loading helpers
# ---------------------------------------------------------------------------


_REGISTERS_PATH = Path(__file__).resolve().parents[3] / "registers" / "thessla_green_registers_full.json"


@lru_cache(maxsize=1)
def _load_register_file() -> _RegisterFileModel:
    """Load and validate the full register definition file."""

    text = _REGISTERS_PATH.read_text(encoding="utf-8")
    try:
        return _RegisterFileModel.model_validate_json(text)
    except AttributeError:  # pragma: no cover - pydantic v1 fallback
        return _RegisterFileModel.parse_raw(text)


@lru_cache(maxsize=1)
def get_all_registers() -> List[Register]:
    """Return a list of all known registers."""

    return [Register.from_dict(r.model_dump()) for r in _load_register_file().registers]
    raise FileNotFoundError(f"No register definition file found near {_REGISTERS_PATH}")


@lru_cache(maxsize=1)
def _load_registers() -> List[Register]:
    """Convert raw data to :class:`Register` instances."""

    registers: List[Register] = []
    for item in _load_raw():
        function = str(item["function"]).lower()
        fn_code = {
            "1": "01",
            "01": "01",
            "coil": "01",
            "coils": "01",
            "2": "02",
            "02": "02",
            "discrete": "02",
            "3": "03",
            "03": "03",
            "holding": "03",
            "4": "04",
            "04": "04",
            "input": "04",
        }.get(function, function)

        if item.get("address_dec") is not None:
            address = int(item["address_dec"])
        else:
            address = int(str(item.get("address_hex")), 16)
        registers.append(
            Register(
                function=fn_code,
                address=address,
                access=item.get("access", "ro"),
                name=item["name"],
                description=item.get("description"),
                unit=item.get("unit"),
                resolution=item.get("resolution"),
                multiplier=item.get("multiplier"),
                min=item.get("min"),
                max=item.get("max"),
                enum=item.get("enum"),
                notes=item.get("notes"),
                extra=item.get("extra"),
                length=int(item.get("length", 1)),
            )
        )
    return registers


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------



def get_all_registers() -> List[Register]:
    """Return all known registers."""

    return list(_load_registers())


@lru_cache(maxsize=None)
def get_registers_by_function(fn: str) -> List[Register]:
    """Return registers for a specific Modbus function code."""

    key = fn.lower().replace("_", "").replace(" ", "")

    fn_code = _FUNCTION_MAP.get(key, key)
    return [r for r in get_all_registers() if r.function == fn_code]


    fn_code = {
        "1": "01",
        "01": "01",
        "coil": "01",
        "coils": "01",
        "2": "02",
        "02": "02",
        "discrete": "02",
        "discreteinput": "02",
        "discreteinputs": "02",
        "3": "03",
        "03": "03",
        "holding": "03",
        "holdingregister": "03",
        "holdingregisters": "03",
        "4": "04",
        "04": "04",
        "input": "04",
        "inputregister": "04",
        "inputregisters": "04",
    }.get(key, key)

    return [r for r in _load_registers() if r.function == fn_code]


@dataclass(slots=True)
class ReadPlan:
    """Plan for reading a consecutive block of registers."""

    function: str
    address: int
    length: int


@lru_cache(maxsize=None)
def group_reads(max_block_size: int = 64) -> List[ReadPlan]:
    """Group registers into consecutive blocks for efficient reading."""

    plans: List[ReadPlan] = []
    regs_by_fn: Dict[str, List[Register]] = {}
    for reg in get_all_registers():
        regs_by_fn.setdefault(reg.function, []).append(reg)

    for fn, regs in regs_by_fn.items():
        regs.sort(key=lambda r: r.address)
        if not regs:
            continue
        start = regs[0].address
        length = 1
        prev = start
        for reg in regs[1:]:
            if reg.address == prev + 1 and length < max_block_size:
                length += 1
            else:
                plans.append(ReadPlan(fn, start, length))
                start = reg.address
                length = 1
            prev = reg.address
        plans.append(ReadPlan(fn, start, length))
    return plans



__all__ = [
    "Register",
    "ReadPlan",
    "get_all_registers",
    "get_registers_by_function",
    "group_reads",
    "_RegisterFileModel",
]

__all__ = ["Register", "ReadPlan", "get_all_registers", "get_registers_by_function", "group_reads"]

