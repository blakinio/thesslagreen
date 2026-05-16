"""Scanner orchestration mixin for DeviceClient."""

from __future__ import annotations

from typing import Any

from ..scanner import ThesslaGreenDeviceScanner
from .scan_helpers import (
    normalise_available_registers as _normalise_available_registers_impl,
)
from .scanner_kwargs import build_scanner_kwargs as _build_scanner_kwargs_impl


class _DeviceClientScannerMixin:
    """Scanner orchestration for ThesslaGreenDeviceClient.

    Extracted from core/client.py to keep client.py focused on composition and
    public API. All methods require the standard DeviceClient attributes
    (config, _resolved_connection_mode, available_registers, etc.).
    """

    _resolved_connection_mode: str | None

    # ------------------------------------------------------------------
    # Scanner / device scan
    # ------------------------------------------------------------------

    def _build_scanner_kwargs(self) -> dict[str, Any]:
        """Return constructor kwargs for scanner creation."""
        return _build_scanner_kwargs_impl(
            self,
            resolved_connection_mode=self._resolved_connection_mode,
        )

    async def async_create_scanner(self) -> ThesslaGreenDeviceScanner:
        """Instantiate a ThesslaGreenDeviceScanner using its create() factory."""
        return await ThesslaGreenDeviceScanner.create(**self._build_scanner_kwargs())

    async def async_scan_device(self) -> dict[str, Any]:
        """Run a full device scan and return the raw scan result.

        The caller (coordinator) is responsible for applying the result via
        ``apply_scan_result`` / ``_apply_scan_result_impl``.
        """
        scanner = await self.async_create_scanner()
        return await scanner.scan_device()

    def _normalise_available_registers(
        self, available: dict[str, list[str] | set[str]]
    ) -> dict[str, set[str]]:
        """Return available register names in canonical form."""
        return _normalise_available_registers_impl(self, available)
