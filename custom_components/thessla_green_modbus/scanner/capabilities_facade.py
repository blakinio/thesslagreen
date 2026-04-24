"""Capabilities facade mixin delegating scanner capability operations."""

from __future__ import annotations

from ..scanner_device_info import DeviceCapabilities
from . import capabilities as scanner_capabilities


class ScannerCapabilitiesFacadeMixin:
    """Delegating capability API used by the scanner core class."""

    def _is_valid_register_value(self, name: str, value: int) -> bool:
        return scanner_capabilities.is_valid_register_value(self, name, value)

    def _analyze_capabilities(self) -> DeviceCapabilities:
        return scanner_capabilities.analyze_capabilities(self)

    def _filter_unsupported_addresses(self, reg_type: str, addrs: set[int]) -> set[int]:
        return scanner_capabilities.filter_unsupported_addresses(self, reg_type, addrs)

    def _log_invalid_value(self, name: str, raw: int) -> None:
        scanner_capabilities.log_invalid_value(self, name, raw)

    def _mark_input_supported(self, address: int) -> None:
        scanner_capabilities.mark_input_supported(self, address)

    def _mark_holding_supported(self, address: int) -> None:
        scanner_capabilities.mark_holding_supported(self, address)

    def _mark_holding_unsupported(self, start: int, end: int, code: int) -> None:
        scanner_capabilities.mark_holding_unsupported(self, start, end, code)

    def _mark_input_unsupported(self, start: int, end: int, code: int | None) -> None:
        scanner_capabilities.mark_input_unsupported(self, start, end, code)
