"""RTU framer detection helpers."""

from __future__ import annotations

from typing import Any

try:
    from pymodbus.framer import FramerType
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    FramerType = None

try:
    from pymodbus.framer import ModbusRtuFramer
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    try:
        from pymodbus.framer.rtu_framer import ModbusRtuFramer
    except (ImportError, ModuleNotFoundError):  # pragma: no cover
        ModbusRtuFramer = None


def get_rtu_framer() -> Any | None:
    """Return a Modbus RTU framer class/enum when available."""

    if FramerType is not None:
        try:
            return FramerType.RTU
        except (AttributeError, ValueError):  # pragma: no cover - unexpected
            return None
    if ModbusRtuFramer is not None:
        return ModbusRtuFramer
    return None
