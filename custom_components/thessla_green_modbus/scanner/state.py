"""Scanner core state initialization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..const import (
    CONNECTION_MODE_AUTO,
    DEFAULT_BAUD_RATE,
    DEFAULT_PARITY,
    DEFAULT_SERIAL_PORT,
    DEFAULT_STOP_BITS,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
)
from ..scanner_register_maps import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    MULTI_REGISTER_SIZES,
)


@dataclass(frozen=True)
class ScannerConnectionState:
    """Resolved scanner connection state normalized from raw init parameters."""

    connection_type: str
    connection_mode: str
    resolved_connection_mode: str | None
    serial_port: str
    baud_rate: int
    parity: str
    stop_bits: int


def build_connection_state(
    *,
    connection_type: str,
    connection_mode: str,
    resolved_connection_mode: str | None,
    serial_port: str,
    baud_rate: int,
    parity: str,
    stop_bits: int,
) -> ScannerConnectionState:
    """Normalize and freeze scanner connection parameters."""
    try:
        normalized_baud_rate = int(baud_rate)
    except (TypeError, ValueError):
        normalized_baud_rate = DEFAULT_BAUD_RATE

    normalized_parity = str(parity or DEFAULT_PARITY).lower()
    if normalized_parity not in SERIAL_PARITY_MAP:
        normalized_parity = DEFAULT_PARITY

    normalized_stop_bits = SERIAL_STOP_BITS_MAP.get(
        stop_bits,
        SERIAL_STOP_BITS_MAP.get(str(stop_bits), DEFAULT_STOP_BITS),
    )
    if normalized_stop_bits not in (1, 2):
        normalized_stop_bits = DEFAULT_STOP_BITS

    fixed_mode = resolved_connection_mode
    if connection_mode == CONNECTION_MODE_AUTO:
        fixed_mode = None

    return ScannerConnectionState(
        connection_type=connection_type,
        connection_mode=connection_mode,
        resolved_connection_mode=fixed_mode,
        serial_port=serial_port or DEFAULT_SERIAL_PORT,
        baud_rate=normalized_baud_rate,
        parity=normalized_parity,
        stop_bits=normalized_stop_bits,
    )


def apply_connection_state(scanner: Any, state: ScannerConnectionState) -> None:
    """Apply normalized connection state to scanner instance."""
    scanner.connection_type = state.connection_type
    scanner.connection_mode = state.connection_mode
    scanner._resolved_connection_mode = state.resolved_connection_mode
    scanner.serial_port = state.serial_port
    scanner.baud_rate = state.baud_rate
    scanner.parity = state.parity
    scanner.stop_bits = state.stop_bits


def apply_register_defaults(scanner: Any, *, known_missing_registers: dict[str, dict[str, Any]]) -> None:
    """Apply default scanner register maps and known-missing metadata."""
    scanner._input_register_map = INPUT_REGISTERS
    scanner._holding_register_map = HOLDING_REGISTERS
    scanner._coil_register_map = COIL_REGISTERS
    scanner._discrete_input_register_map = DISCRETE_INPUT_REGISTERS
    scanner._known_missing_registers = known_missing_registers
    scanner._multi_register_sizes = MULTI_REGISTER_SIZES
