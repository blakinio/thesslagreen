"""Backward-compatible shim for entity mappings package."""

from __future__ import annotations

import sys

from . import mappings as _m

_m.__file__ = __file__
sys.modules[__name__] = _m
