"""Compatibility wrappers for register metadata access.

The actual register information is now provided by :mod:`custom_components.
thessla_green_modbus.loader`.  This module remains to keep backwards
compatibility with older imports and simply forwards calls to the loader.
"""

from __future__ import annotations

from ..loader import get_register_info, get_register_infos

__all__ = ["get_register_info", "get_register_infos"]

