"""Compatibility shim – canonical implementation is in transport.retry."""

from .transport.retry import classify_transport_error

__all__ = ["classify_transport_error"]
