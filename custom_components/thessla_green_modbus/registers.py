"""Public register mappings for the Thessla Green integration.

This module previously contained large dictionaries generated from the CSV
specification.  The data is now provided by :mod:`loader` which is responsible
for parsing and caching the register information.  The module remains as a
compatibility façade exposing the same constants as before so existing imports
continue to function.
"""

from __future__ import annotations

from .loader import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    MULTI_REGISTER_SIZES,
)

__all__ = [
    "COIL_REGISTERS",
    "DISCRETE_INPUT_REGISTERS",
    "INPUT_REGISTERS",
    "HOLDING_REGISTERS",
    "MULTI_REGISTER_SIZES",
]

