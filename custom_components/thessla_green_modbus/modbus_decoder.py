"""Helpers for decoding and formatting Modbus frames for logging."""

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
            return bytes([slave_id, 0x04, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF])
        if func_name == "read_holding_registers":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 0x03, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF])
        if func_name == "read_coils":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 0x01, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF])
        if func_name == "read_discrete_inputs":
            addr = int(positional[0])
            count = int(kwargs.get("count", positional[1] if len(positional) > 1 else 1))
            return bytes([slave_id, 0x02, addr >> 8, addr & 0xFF, count >> 8, count & 0xFF])
        if func_name == "write_register":
            addr = int(kwargs.get("address", positional[0]))
            value = int(kwargs.get("value", positional[1] if len(positional) > 1 else 0))
            return bytes([slave_id, 0x06, addr >> 8, addr & 0xFF, value >> 8, value & 0xFF])
        if func_name == "write_registers":
            addr = int(kwargs.get("address", positional[0]))
            values = [
                int(v) for v in kwargs.get("values", positional[1] if len(positional) > 1 else [])
            ]
            qty = len(values)
            frame = bytearray(
                [
                    slave_id,
                    0x10,
                    addr >> 8,
                    addr & 0xFF,
                    qty >> 8,
                    qty & 0xFF,
                    qty * 2,
                ]
            )
            for v in values:
                frame.extend([v >> 8, v & 0xFF])
            return bytes(frame)
        if func_name == "write_coil":
            addr = int(kwargs.get("address", positional[0]))
            value = (
                0xFF00
                if kwargs.get("value", positional[1] if len(positional) > 1 else False)
                else 0x0000
            )
            return bytes([slave_id, 0x05, addr >> 8, addr & 0xFF, value >> 8, value & 0xFF])
    except (ValueError, TypeError, IndexError) as err:
        _LOGGER.warning("Failed to build Modbus request frame: %s", err)
        return b""
    except Exception as err:  # pragma: no cover - unexpected
        _LOGGER.exception("Unexpected error building Modbus request frame: %s", err)
        return b""

    return b""
