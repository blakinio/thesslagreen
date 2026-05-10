"""Compatibility shim – canonical implementation is in transport.tcp and transport.rtu."""

from .transport.rtu import (
    SERIAL_IMPORT_ERROR,
    RtuModbusTransport,
    _AsyncModbusSerialClient,
)
from .transport.tcp import TcpModbusTransport, _ClientBackedTransport

__all__ = [
    "SERIAL_IMPORT_ERROR",
    "RtuModbusTransport",
    "TcpModbusTransport",
    "_AsyncModbusSerialClient",
    "_ClientBackedTransport",
]
