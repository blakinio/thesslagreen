"""Register loader and grouping utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel


@dataclass(slots=True)
class Register:
    """Represents a single register definition."""

    function: str
    address: int
    length: int = 1


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
        Register(function=r.function, address=r.address_dec, length=r.length or 1)
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
