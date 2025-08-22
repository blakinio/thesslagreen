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

_LOGGER = logging.getLogger(__name__)


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
    minimum: float | None = None
    maximum: float | None = None
    bcd: bool = False

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

        description: Optional[str] = data.get("description")
        enum: Optional[Dict[str, int]] = data.get("enum")
        multiplier: Optional[float] = data.get("multiplier")
        resolution: Optional[float] = data.get("resolution")
        minimum: Optional[float] = data.get("min")
        maximum: Optional[float] = data.get("max")

        name_lower = name.lower()
        bcd = bool(name_lower.startswith("schedule_") and name_lower.endswith(("_start", "_end")))

        return cls(
            function=function,
            address=address,
            name=name,
            access=access,
            description=description,
            enum=enum,
            multiplier=multiplier,
            resolution=resolution,
            minimum=minimum,
            maximum=maximum,
            bcd=bcd,
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
