"""Compatibility shim – canonical implementation is in transport.tcp_rtu."""

from .transport.tcp_rtu import RawRtuOverTcpTransport

__all__ = ["RawRtuOverTcpTransport"]
