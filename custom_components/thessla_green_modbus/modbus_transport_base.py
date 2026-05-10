"""Compatibility shim – canonical implementation is in transport.base and transport.raw."""

from .transport.base import BaseModbusTransport
from .transport.crc import append_crc as _append_crc
from .transport.crc import crc16 as _crc16
from .transport.raw import (
    _MAX_READ_REGISTERS,
    _MAX_SLAVE_ID,
    _MAX_WRITE_REGISTERS,
    _MIN_SLAVE_ID,
    RawModbusResponse,
    RawModbusWriteResponse,
)
from .transport.retry import classify_transport_error as _classify_transport_error_inner


def classify_transport_error(exc: BaseException) -> tuple[str, str]:
    """Expose normalized retry classification for transport layer tests."""
    decision = _classify_transport_error_inner(exc)
    return decision.kind.value, decision.reason


__all__ = [
    "_MAX_READ_REGISTERS",
    "_MAX_SLAVE_ID",
    "_MAX_WRITE_REGISTERS",
    "_MIN_SLAVE_ID",
    "BaseModbusTransport",
    "RawModbusResponse",
    "RawModbusWriteResponse",
    "_append_crc",
    "_crc16",
    "classify_transport_error",
]
