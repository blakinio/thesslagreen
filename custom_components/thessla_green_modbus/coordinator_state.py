"""Coordinator state normalization and initialization helpers."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_ENABLE_DEVICE_SCAN,
    CONF_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_BAUD_RATE,
    DEFAULT_ENABLE_DEVICE_SCAN,
    DEFAULT_PARITY,
    DEFAULT_SERIAL_PORT,
    DEFAULT_STOP_BITS,
    MAX_REGS_PER_REQUEST,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
    coil_registers,
    discrete_input_registers,
    holding_registers,
    input_registers,
)
from .scanner import DeviceCapabilities


def normalize_serial_settings(
    serial_port: str,
    baud_rate: int,
    parity: str,
    stop_bits: int,
) -> tuple[str, int, str, int]:
    """Return canonical serial settings."""
    normalized_serial_port = serial_port or DEFAULT_SERIAL_PORT
    try:
        normalized_baud_rate = int(baud_rate)
    except (TypeError, ValueError):
        normalized_baud_rate = DEFAULT_BAUD_RATE

    parity_norm = str(parity or DEFAULT_PARITY).lower()
    if parity_norm not in SERIAL_PARITY_MAP:
        parity_norm = DEFAULT_PARITY

    normalized_stop_bits = SERIAL_STOP_BITS_MAP.get(
        stop_bits,
        SERIAL_STOP_BITS_MAP.get(str(stop_bits), DEFAULT_STOP_BITS),
    )
    if normalized_stop_bits not in (1, 2):  # pragma: no cover
        normalized_stop_bits = DEFAULT_STOP_BITS

    return normalized_serial_port, normalized_baud_rate, parity_norm, normalized_stop_bits


def resolve_effective_batch(entry: ConfigEntry | None, max_registers_per_request: int) -> int:
    """Compute bounded max registers per request."""
    if entry is not None:
        try:
            effective_batch = min(
                int(entry.options.get(CONF_MAX_REGISTERS_PER_REQUEST, MAX_REGS_PER_REQUEST)),
                MAX_REGS_PER_REQUEST,
            )
        except (TypeError, ValueError):
            effective_batch = MAX_REGS_PER_REQUEST
    else:
        effective_batch = min(int(max_registers_per_request), MAX_REGS_PER_REQUEST)
    return max(1, effective_batch)


def initialize_runtime_state(coordinator: Any, *, entry: ConfigEntry | None) -> None:
    """Initialize mutable runtime state containers for a coordinator instance."""
    coordinator.enable_device_scan = (
        bool(entry.options.get(CONF_ENABLE_DEVICE_SCAN, DEFAULT_ENABLE_DEVICE_SCAN))
        if entry is not None
        else DEFAULT_ENABLE_DEVICE_SCAN
    )

    coordinator._reauth_scheduled = False
    coordinator.offline_state = False

    coordinator.client = None
    coordinator._transport = None
    coordinator._client_lock = asyncio.Lock()
    coordinator._write_lock = asyncio.Lock()
    coordinator._update_in_progress = False

    coordinator._stop_listener = None

    coordinator.device_info = {}
    coordinator.capabilities = DeviceCapabilities()
    if entry and isinstance(entry.data.get("capabilities"), dict):
        with suppress(TypeError, ValueError):
            coordinator.capabilities = DeviceCapabilities(**entry.data["capabilities"])

    coordinator.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
        "calculated": {"estimated_power", "total_energy"},
    }

    coordinator._register_maps = {
        "input_registers": input_registers().copy(),
        "holding_registers": holding_registers().copy(),
        "coil_registers": coil_registers().copy(),
        "discrete_inputs": discrete_input_registers().copy(),
    }
    coordinator._reverse_maps = {
        key: {addr: name for name, addr in mapping.items()}
        for key, mapping in coordinator._register_maps.items()
    }
    coordinator._input_registers_rev = coordinator._reverse_maps["input_registers"]
    coordinator._holding_registers_rev = coordinator._reverse_maps["holding_registers"]
    coordinator._coil_registers_rev = coordinator._reverse_maps["coil_registers"]
    coordinator._discrete_inputs_rev = coordinator._reverse_maps["discrete_inputs"]

    coordinator._register_groups = {}
    coordinator._consecutive_failures = 0
    coordinator._max_failures = 5

    coordinator.device_scan_result = None
    coordinator.unknown_registers = {}
    coordinator.scanned_registers = {}

    coordinator.statistics = {
        "successful_reads": 0,
        "failed_reads": 0,
        "connection_errors": 0,
        "timeout_errors": 0,
        "last_error": None,
        "last_successful_update": None,
        "average_response_time": 0.0,
        "total_registers_read": 0,
    }

    coordinator.last_scan = None
    from .utils import utcnow

    coordinator._last_power_timestamp = utcnow()
    coordinator._total_energy = 0.0
