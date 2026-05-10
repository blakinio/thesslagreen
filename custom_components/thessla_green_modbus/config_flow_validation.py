"""Compatibility shim: config flow validation helpers moved to _config_flow.validation."""

from __future__ import annotations

from ._config_flow.validation import (
    process_scan_capabilities,
    process_scan_capabilities_bound,
    validate_rtu_config,
    validate_rtu_config_bound,
    validate_slave_id,
    validate_tcp_config,
    validate_tcp_config_bound,
)

__all__ = [
    "process_scan_capabilities",
    "process_scan_capabilities_bound",
    "validate_rtu_config",
    "validate_rtu_config_bound",
    "validate_slave_id",
    "validate_tcp_config",
    "validate_tcp_config_bound",
]
