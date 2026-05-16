"""Capabilities and derived metrics mixin — re-exported from core.capabilities_mixin.

Kept as a shim so that existing ``from .capabilities import _CoordinatorCapabilitiesMixin``
imports inside the coordinator package and tests that import directly from this
module continue to work.
"""

from ..core.capabilities_mixin import _CoordinatorCapabilitiesMixin

__all__ = ["_CoordinatorCapabilitiesMixin"]
