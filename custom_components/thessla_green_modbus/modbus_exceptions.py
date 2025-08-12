"""Compatibility helpers for Modbus exceptions.

Provides ``ConnectionException`` and ``ModbusException`` classes even when
pymodbus is not installed. This allows tests to run without the dependency.
"""
from __future__ import annotations

try:  # pragma: no cover - handle missing or incompatible pymodbus
    from pymodbus.exceptions import ConnectionException, ModbusException
except Exception:  # pragma: no cover
    class ConnectionException(Exception):
        """Fallback exception when pymodbus is unavailable."""

        pass

    class ModbusException(Exception):
        """Fallback Modbus exception when pymodbus is unavailable."""

        pass

__all__ = ["ConnectionException", "ModbusException"]
