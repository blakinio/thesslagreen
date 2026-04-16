"""Backward-compatible shim for the ``mappings`` package."""

from __future__ import annotations

import sys

from . import mappings as _m
from .mappings import (
    BINARY_SENSOR_ENTITY_MAPPINGS,
    ENTITY_MAPPINGS,
    NUMBER_ENTITY_MAPPINGS,
    SELECT_ENTITY_MAPPINGS,
    SENSOR_ENTITY_MAPPINGS,
    SWITCH_ENTITY_MAPPINGS,
    TEXT_ENTITY_MAPPINGS,
    TIME_ENTITY_MAPPINGS,
    async_setup_entity_mappings,
    map_legacy_entity_id,
)

# Keep ``entity_mappings`` as an alias of ``mappings`` so existing tests and
# monkeypatches that mutate module globals continue to affect runtime behavior.
_m.__file__ = __file__
sys.modules[__name__] = _m

__all__ = [
    "BINARY_SENSOR_ENTITY_MAPPINGS",
    "ENTITY_MAPPINGS",
    "NUMBER_ENTITY_MAPPINGS",
    "SELECT_ENTITY_MAPPINGS",
    "SENSOR_ENTITY_MAPPINGS",
    "SWITCH_ENTITY_MAPPINGS",
    "TEXT_ENTITY_MAPPINGS",
    "TIME_ENTITY_MAPPINGS",
    "async_setup_entity_mappings",
    "map_legacy_entity_id",
]
