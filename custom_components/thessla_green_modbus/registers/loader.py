"""Utilities for loading and validating register definitions.

The register metadata used by development tools and tests is stored in
``thessla_green_registers_full.json``.  This module exposes small helper
classes and functions to read that file and to organise registers into
contiguous read blocks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel


@dataclass(slots=True)
class Register:
    """Representation of a single Modbus register."""

    function: str
    address: int
    name: str | None = None
    description: str | None = None
    access: str | None = None
    enum: Dict[str, int] | None = None
    multiplier: float | None = None
    resolution: float | None = None
    length: int = 1


@dataclass(slots=True)
class ReadPlan:
    """Plan for reading a consecutive block of registers."""

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
    multiplier: float | None = None
    resolution: float | None = None
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


_REGISTERS_PATH = Path(__file__).resolve().parents[3] / "thessla_green_registers_full.json"
_REGISTERS: List[Register] = []


def _load_registers() -> List[Register]:
    """Load register definitions from the JSON file."""

    global _REGISTERS
    if _REGISTERS:
        return _REGISTERS

    text = _REGISTERS_PATH.read_text(encoding="utf-8")
    try:
        model = _RegisterFileModel.model_validate_json(text)
    except AttributeError:  # pragma: no cover - pydantic v1 fallback
        model = _RegisterFileModel.parse_raw(text)

    _REGISTERS = [
        Register(
            function=r.function,
            address=r.address_dec,
            name=r.name,
            description=r.description,
            access=r.access,
            enum={v: int(k) for k, v in (r.enum or {}).items()},
            multiplier=r.multiplier,
            resolution=r.resolution,
            length=r.length or 1,
        )
        for r in model.registers
    ]
    return _REGISTERS


def get_all_registers() -> List[Register]:
    """Return a list of all known registers."""

    return list(_load_registers())


def get_registers_by_function(fn: str) -> List[Register]:
    """Return registers matching a specific Modbus function code."""

    return [r for r in _load_registers() if r.function == fn]


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
        length = 1
        prev = start
        for reg in sorted_regs[1:]:
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
