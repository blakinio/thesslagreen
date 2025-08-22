"""Loader for Modbus register definitions.

This module reads the bundled ``thessla_green_registers_full.json`` file and
exposes a small helper API used by the integration and the tests.  The JSON file
contains the canonical list of registers together with metadata describing how a
raw register value should be interpreted.

Only a fairly small subset of the original project is required for the unit
tests in this kata, therefore the implementation below purposely focuses on the
features that are exercised in the tests: parsing of the JSON file, decoding of
values using ``enum``/``multiplier``/``resolution`` information, optional BCD
time handling for schedule registers and grouping of addresses for efficient
reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..schedule_helpers import bcd_to_time, time_to_bcd

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Register:
    """Definition of a single Modbus register."""

    function: str
    address: int
    name: str
    access: str
    description: str | None = None
    unit: str | None = None
    multiplier: float | None = None
    resolution: float | None = None
    min: float | None = None
    max: float | None = None
    default: float | None = None
    enum: Dict[int | str, Any] | None = None
    notes: str | None = None
    information: str | None = None
    extra: Dict[str, Any] | None = None
    length: int = 1
    bcd: bool = False

    # ------------------------------------------------------------------
    # Value helpers
    # ------------------------------------------------------------------
    def decode(self, raw: int) -> Any:
        """Decode ``raw`` according to the register metadata."""

        if raw == 0x8000:  # common sentinel used by the device
            return None

        # Enumerations map raw numeric values to labels
        if self.enum is not None:
            if raw in self.enum:
                return self.enum[raw]
            if str(raw) in self.enum:
                return self.enum[str(raw)]

        value: Any = raw
        if self.multiplier is not None:
            value = value * self.multiplier
        if self.resolution is not None:
            steps = round(value / self.resolution)
            value = steps * self.resolution

        if self.extra and self.extra.get("aatt"):
            airflow = (raw >> 8) & 0xFF
            temp = (raw & 0xFF) / 2
            return airflow, temp

        if self.bcd:
            try:
                t = bcd_to_time(raw)
            except Exception:  # pragma: no cover - defensive
                return value
            return f"{t.hour:02d}:{t.minute:02d}"

        return value

    def encode(self, value: Any) -> int:
        """Encode ``value`` into the raw register representation."""

        if self.bcd:
            if isinstance(value, str):
                hours, minutes = (int(x) for x in value.split(":"))
            elif isinstance(value, int):
                hours, minutes = divmod(value, 60)
            elif isinstance(value, (tuple, list)):
                hours, minutes = int(value[0]), int(value[1])
            else:  # pragma: no cover - defensive
                raise ValueError(f"Unsupported BCD value: {value}")
            return time_to_bcd(time(hours, minutes))

        if self.extra and self.extra.get("aatt"):
            airflow, temp = value if isinstance(value, (list, tuple)) else (value["airflow"], value["temp"])  # type: ignore[index]
            return (int(airflow) << 8) | (int(round(float(temp) * 2)) & 0xFF)

        raw: Any = value
        if self.enum and isinstance(value, str):
            # Reverse lookup
            for k, v in self.enum.items():
                if v == value:
                    raw = int(k)
                    break
        if self.multiplier is not None:
            raw = int(round(float(raw) / self.multiplier))
        if self.resolution is not None:
            step = self.resolution
            raw = int(round(float(raw) / step) * step)
        return int(raw)


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

_REGISTERS_PATH = Path(__file__).with_name("thessla_green_registers_full.json")


def _normalise_function(fn: str) -> str:
    mapping = {
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
    }
    return mapping.get(fn.lower(), fn)


@lru_cache(maxsize=1)
def _load_registers() -> List[Register]:
    """Load register definitions from the JSON file."""

    if not _REGISTERS_PATH.exists():  # pragma: no cover - sanity check
        _LOGGER.error("Register definition file missing: %s", _REGISTERS_PATH)
        return []

    text = _REGISTERS_PATH.read_text(encoding="utf-8")
    raw = json.loads(text)
    items = raw.get("registers", raw) if isinstance(raw, dict) else raw

    registers: List[Register] = []
    for item in items:
        function = _normalise_function(str(item.get("function", "")))
        if item.get("address_dec") is not None:
            address = int(item["address_dec"])
        else:
            address = int(str(item.get("address_hex")), 16)

        try:
            registers.append(
                Register(
                    function=function,
                    address=address,
                    name=str(item["name"]),
                    access=str(item.get("access", "ro")),
                    description=item.get("description"),
                    unit=item.get("unit"),
                    multiplier=item.get("multiplier"),
                    resolution=item.get("resolution"),
                    min=item.get("min"),
                    max=item.get("max"),
                    default=item.get("default"),
                    enum=item.get("enum"),
                    notes=item.get("notes"),
                    information=item.get("information"),
                    extra=item.get("extra"),
                    length=int(item.get("length", 1)),
                    bcd=bool(item.get("bcd", False)),
                )
            )
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.warning("Invalid register definition skipped: %s", err)
    return registers


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_all_registers() -> List[Register]:
    """Return a list of all known registers."""

    return list(_load_registers())


def get_registers_by_function(fn: str) -> List[Register]:
    """Return registers for the given function code or name."""

    code = _normalise_function(fn)
    return [r for r in _load_registers() if r.function == code]


@dataclass(slots=True)
class ReadPlan:
    """Plan describing a consecutive block of registers to read."""

    function: str
    address: int
    length: int


def group_reads(max_block_size: int = 64) -> List[ReadPlan]:
    """Group registers into contiguous blocks for efficient reading."""

    plans: List[ReadPlan] = []
    regs_by_fn: Dict[str, List[int]] = {}

    for reg in _load_registers():
        addresses = list(range(reg.address, reg.address + reg.length))
        regs_by_fn.setdefault(reg.function, []).extend(addresses)

    for fn, addresses in regs_by_fn.items():
        addresses.sort()
        start = prev = addresses[0]
        length = 1
        for addr in addresses[1:]:
            if addr == prev + 1 and length < max_block_size:
                length += 1
            else:
                plans.append(ReadPlan(fn, start, length))
                start = addr
                length = 1
            prev = addr
        plans.append(ReadPlan(fn, start, length))

    return plans


__all__ = [
    "Register",
    "ReadPlan",
    "get_all_registers",
    "get_registers_by_function",
    "group_reads",
]

