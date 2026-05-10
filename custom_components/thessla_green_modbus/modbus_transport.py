"""Transport abstractions for Modbus communication."""

from .modbus_helpers import get_rtu_framer
from .modbus_transport_base import classify_transport_error
from .transport.base import BaseModbusTransport
from .transport.crc import append_crc as _append_crc
from .transport.crc import crc16 as _crc16
from .transport.raw import RawModbusResponse, RawModbusWriteResponse
from .transport.rtu import SERIAL_IMPORT_ERROR, RtuModbusTransport, _AsyncModbusSerialClient
from .transport.tcp import TcpModbusTransport, _ClientBackedTransport
from .transport.tcp_rtu import RawRtuOverTcpTransport

__all__ = [
    "SERIAL_IMPORT_ERROR",
    "BaseModbusTransport",
    "RawModbusResponse",
    "RawModbusWriteResponse",
    "RawRtuOverTcpTransport",
    "RtuModbusTransport",
    "TcpModbusTransport",
    "_AsyncModbusSerialClient",
    "_ClientBackedTransport",
    "_append_crc",
    "_crc16",
    "classify_transport_error",
    "get_rtu_framer",
]
