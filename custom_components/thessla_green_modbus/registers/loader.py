from __future__ import annotations

"""Utilities for loading and working with register definitions.

The registers for the ThesslaGreen device are defined in a JSON file. This
module provides helpers to load these definitions and expose them as convenient
Python objects. The JSON is read only once and results are cached in memory.

Each :class:`Register` contains metadata describing how to decode/encode values,
including optional enum mappings, multipliers, resolution and special handling
for schedule times encoded in BCD format.
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel

from ..utils import _decode_aatt

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class Register:
    """Representation of a single Modbus register."""

    function: str
    address: int
    name: str
    access: str
    length: int = 1
    enum: Dict[str, int] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    description: str | None = None
    min: float | None = None
    max: float | None = None
    default: float | None = None
    unit: str | None = None
    information: str | None = None
    bcd: bool = False
    extra: Dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Register":
        """Create a :class:`Register` instance from raw dictionary data.

        Raises ``ValueError`` if required fields are missing or invalid.
        """

        try:
            function = str(data["function"])  # input/holding/coil/discrete
            address = int(data.get("address_dec") or int(data.get("address_hex"), 16))
            name = str(data["name"])
            access = str(data.get("access", ""))
        except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - defensive
            _LOGGER.error("Invalid register definition: %s", data)
            raise ValueError(f"Invalid register definition: {data}") from exc

        length = int(data.get("length", 1))
        enum: Optional[Dict[str, int]] = data.get("enum")
        multiplier: Optional[float] = data.get("multiplier")
        resolution: Optional[float] = data.get("resolution")
        description: Optional[str] = data.get("description")
        min_val: Optional[float] = data.get("min")
        max_val: Optional[float] = data.get("max")
        default: Optional[float] = data.get("default")
        unit: Optional[str] = data.get("unit")
        information: Optional[str] = data.get("information")

        name_lower = name.lower()
        bcd = bool(
            data.get("bcd")
            or (name_lower.startswith("schedule_") and name_lower.endswith(("_start", "_end")))
        )
        extra: Optional[Dict[str, Any]] = data.get("extra")
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

        if self.bcd:
            hours_bcd = (raw >> 8) & 0xFF
            mins_bcd = raw & 0xFF
            hours = (hours_bcd >> 4) * 10 + (hours_bcd & 0x0F)
            mins = (mins_bcd >> 4) * 10 + (mins_bcd & 0x0F)
            return f"{hours:02d}:{mins:02d}"

        if self.extra and self.extra.get("aatt"):
            decoded = _decode_aatt(raw)
            if decoded is not None:
                return decoded
            return raw

        value: Any = raw

        if self.enum:
            for key, val in self.enum.items():
                if val == raw:
                    return key

        if self.multiplier is not None:
            value = value * self.multiplier

        if self.resolution is not None and isinstance(value, (int, float)):
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
        if self.enum and isinstance(value, str) and value in self.enum:
            raw = self.enum[value]
        if self.multiplier is not None:
            raw = int(round(float(raw) / self.multiplier))
        if self.resolution is not None:
            step = self.resolution
            raw = int(round(float(raw) / step) * step)
        return int(raw)


# ----------------------------------------------------------------------
# JSON loading utilities
# ----------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_json() -> List[Dict[str, Any]]:
    """Load register definitions from JSON file with global caching."""

    json_path = Path(__file__).with_name("thessla_green_registers_full.json")
    try:
        with json_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.exception("Failed to load register JSON: %s", exc)
        raise

    if not isinstance(data, list):  # pragma: no cover - defensive
        _LOGGER.error("Register JSON must be a list")
        raise ValueError("Register JSON must be a list")
    return data


@lru_cache(maxsize=1)
def get_all_registers() -> List[Register]:
    """Return all registers defined in the JSON file."""

    registers: List[Register] = []
    for item in _load_json():
        try:
            registers.append(Register.from_dict(item))
        except ValueError as exc:
            _LOGGER.error("Register validation error: %s", exc)
            raise
    return registers


def get_registers_by_function(function: str) -> Dict[str, Register]:
    """Return registers filtered by Modbus function type."""

    function_lower = function.lower()
    regs = {reg.name: reg for reg in get_all_registers() if reg.function.lower() == function_lower}
    return regs


def group_reads(
    registers: Iterable[Register], max_gap: int = 10, max_batch: int = 16
) -> List[Tuple[int, int]]:
    """Group register addresses for batch reading."""

    addresses = sorted(reg.address for reg in registers)
    if not addresses:
        return []

    groups: List[Tuple[int, int]] = []
    start = addresses[0]
    end = start

    for addr in addresses[1:]:
        if (addr - end > max_gap) or (end - start + 1 >= max_batch):
            groups.append((start, end - start + 1))
            start = addr
            end = addr
        else:
            end = addr

    groups.append((start, end - start + 1))
    return groups
    """Represents a single register definition."""

    function: str
    address: int
    name: str | None = None
    length: int = 1
    enum: Dict[str, str] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    description: str | None = None
    access: str | None = None
    min: float | None = None
    max: float | None = None
    default: float | None = None
    unit: str | None = None
    information: str | None = None


@dataclass(slots=True)
class ReadPlan:
    """Plan for reading a block of registers."""

    function: str
    address: int
    length: int


class _RegisterModel(BaseModel):
    function: str
    address_dec: int
    name: str | None = None
    description: str | None = None
    access: str | None = None
    enum: Dict[str, str] | None = None
    length: int | None = None
    multiplier: float | None = None
    resolution: float | None = None
    min: float | None = None
    max: float | None = None
    default: float | None = None
    unit: str | None = None
    information: str | None = None

    class Config:
        extra = "ignore"


class _RegisterFileModel(BaseModel):
    schema_version: str
    generated_at: str
    source_pdf: str
    publisher: str
    device_family: str
    registers: List[_RegisterModel]

    class Config:
        extra = "ignore"


_REGISTERS: list[Register] = []


def _load_registers() -> list[Register]:
    """Load and validate register definitions from JSON file."""
    global _REGISTERS
    if _REGISTERS:
        return _REGISTERS

    json_path = Path(__file__).resolve().parents[3] / "thessla_green_registers_full.json"
    model: _RegisterFileModel
    text = json_path.read_text(encoding="utf-8")
    try:
        # Pydantic v2
        model = _RegisterFileModel.model_validate_json(text)
    except AttributeError:  # pragma: no cover - pydantic v1 fallback
        model = _RegisterFileModel.parse_raw(text)

    _REGISTERS = [
        Register(
            function=r.function,
            address=r.address_dec,
            name=r.name,
            length=r.length or 1,
            enum=r.enum,
            multiplier=r.multiplier,
            resolution=r.resolution,
            description=r.description,
            access=r.access,
            min=r.min,
            max=r.max,
            default=r.default,
            unit=r.unit,
            information=r.information,
        )
        for r in model.registers
    ]
    return _REGISTERS


# Load registers at module import
_load_registers()


def get_all_registers() -> list[Register]:
    """Return all registers."""

    return list(_REGISTERS)


def get_registers_by_function(fn: str) -> list[Register]:
    """Return registers matching a specific function code."""

    return [r for r in _REGISTERS if r.function == fn]


def group_reads(max_block_size: int = 64) -> list[ReadPlan]:
    """Group registers into consecutive read plans respecting block size."""

    plans: list[ReadPlan] = []
    regs_by_fn: Dict[str, list[Register]] = {}
    for reg in _REGISTERS:
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
