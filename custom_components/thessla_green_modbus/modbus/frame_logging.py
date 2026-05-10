"""Frame logging helpers for Modbus communication."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def _mask_frame(frame: bytes) -> str:
    """Return a hex representation of ``frame`` with the slave ID masked."""

    if not frame:
        return ""

    hex_str = frame.hex()
    if len(hex_str) >= 2:
        return f"**{hex_str[2:]}"
    return hex_str


def _build_request_frame(
    func_name: str, slave_id: int, positional: list[Any], kwargs: dict[str, Any]
) -> bytes:
    """Best-effort Modbus request frame builder for logging."""

    try:
        if func_name == "read_input_registers":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 4, addr >> 8, addr & 255, count >> 8, count & 255])
        if func_name == "read_holding_registers":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 3, addr >> 8, addr & 255, count >> 8, count & 255])
        if func_name == "read_coils":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 1, addr >> 8, addr & 255, count >> 8, count & 255])
        if func_name == "read_discrete_inputs":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 2, addr >> 8, addr & 255, count >> 8, count & 255])
        if func_name == "write_register":
            addr = int(kwargs.get("address", positional[0]))
            value = int(kwargs.get("value", positional[1] if len(positional) > 1 else 0))
            return bytes([slave_id, 6, addr >> 8, addr & 255, value >> 8, value & 255])
        if func_name == "write_registers":
            addr = int(kwargs.get("address", positional[0]))
            values = [
                int(v) for v in kwargs.get("values", positional[1] if len(positional) > 1 else [])
            ]
            qty = len(values)
            frame = bytearray(
                [
                    slave_id,
                    16,
                    addr >> 8,
                    addr & 255,
                    qty >> 8,
                    qty & 255,
                    qty * 2,
                ]
            )
            for v in values:
                frame.extend([v >> 8, v & 255])
            return bytes(frame)
        if func_name == "write_coil":
            addr = int(kwargs.get("address", positional[0]))
            value = (
                65280 if kwargs.get("value", positional[1] if len(positional) > 1 else False) else 0
            )
            return bytes([slave_id, 5, addr >> 8, addr & 255, value >> 8, value & 255])
    except (ValueError, TypeError, IndexError) as err:
        _LOGGER.debug("Failed to build request frame: %s", err)
        return b""
    return b""


def _log_modbus_request(
    *,
    func_name: str,
    slave_id: int,
    positional: list[Any],
    kwargs: dict[str, Any],
) -> None:
    """Emit request diagnostics at debug level."""
    request_frame = _build_request_frame(func_name, slave_id, positional, kwargs)
    if request_frame:
        _LOGGER.debug("Modbus request: %s", _mask_frame(request_frame))
        return
    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            "Sending %s to slave %s: args=%s kwargs=%s", func_name, slave_id, positional, kwargs
        )


def _log_modbus_response(func_name: str, response: Any) -> None:
    """Emit response diagnostics at debug level."""
    if _LOGGER.isEnabledFor(logging.DEBUG):
        try:
            encoded = response.encode() if hasattr(response, "encode") else b""
        except (AttributeError, ValueError, TypeError, UnicodeError) as err:
            _LOGGER.debug("Failed to encode Modbus response: %s", err)
            encoded = b""
        except (OSError, RuntimeError) as err:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected error encoding Modbus response: %s", err)
            encoded = b""
        if encoded:
            _LOGGER.debug("Modbus response: %s", _mask_frame(encoded))
        else:
            _LOGGER.debug("Received from %s: %s", func_name, response)
        return

    try:
        encoded = response.encode() if hasattr(response, "encode") else b""
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        encoded = b""
    if encoded:
        _LOGGER.debug("Modbus response: %s", _mask_frame(encoded))
