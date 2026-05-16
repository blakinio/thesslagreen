"""Read-path coordinator mixin — re-exported from core.io_mixin.

Kept as a shim so that existing ``from .io import _ModbusIOMixin`` imports
inside the coordinator package and any external callers continue to work.
"""

from ..core.io_mixin import _ModbusIOMixin

__all__ = ["_ModbusIOMixin"]
