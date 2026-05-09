"""Transport package for Modbus communication."""

from .base import BaseModbusTransport
from .crc import append_crc, crc16, crc16_bytes
from .raw import (
    _MAX_READ_REGISTERS,
    _MAX_SLAVE_ID,
    _MAX_WRITE_REGISTERS,
    _MIN_SLAVE_ID,
    RawModbusResponse,
    RawModbusWriteResponse,
)
from .retry import ErrorKind, RetryDecision, classify_transport_error, should_retry
from .rtu import SERIAL_IMPORT_ERROR, RtuModbusTransport, _AsyncModbusSerialClient
from .tcp import TcpModbusTransport, _ClientBackedTransport
from .tcp_rtu import RawRtuOverTcpTransport

__all__ = [
    "SERIAL_IMPORT_ERROR",
    "_MAX_READ_REGISTERS",
    "_MAX_SLAVE_ID",
    "_MAX_WRITE_REGISTERS",
    "_MIN_SLAVE_ID",
    "BaseModbusTransport",
    "ErrorKind",
    "RawModbusResponse",
    "RawModbusWriteResponse",
    "RawRtuOverTcpTransport",
    "RetryDecision",
    "RtuModbusTransport",
    "TcpModbusTransport",
    "_AsyncModbusSerialClient",
    "_ClientBackedTransport",
    "append_crc",
    "classify_transport_error",
    "crc16",
    "crc16_bytes",
    "should_retry",
]
