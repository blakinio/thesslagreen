"""Backward-compatible shim for entity mappings package."""

from __future__ import annotations

import sys

from . import mappings as _m

# Keep ``entity_mappings`` as an alias of ``mappings`` so existing tests and
# monkeypatches that mutate module globals continue to affect runtime behavior.
_m.__file__ = __file__
sys.modules[__name__] = _m
