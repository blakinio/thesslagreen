"""Scanner orchestration mixin for DeviceClient."""

from __future__ import annotations

from typing import Any

from ..scanner import ThesslaGreenDeviceScanner
from .scan_helpers import (
    normalise_available_registers as _normalise_available_registers_impl,
)


def build_scanner_kwargs(
    device_client: Any,
    *,
    resolved_connection_mode: str | None,
) -> dict[str, Any]:
    """Return constructor kwargs shared by all scanner creation paths."""
    return {
        "host": device_client.config.host,
        "port": device_client.config.port,
        "slave_id": device_client.config.slave_id,
        "timeout": device_client.timeout,
        "retry": device_client.retry,
        "backoff": device_client.backoff,
        "backoff_jitter": device_client.backoff_jitter,
        "scan_uart_settings": device_client.scan_uart_settings,
        "skip_known_missing": device_client.skip_missing_registers,
        "deep_scan": device_client.deep_scan,
        "max_registers_per_request": device_client.effective_batch,
        "safe_scan": device_client.safe_scan,
        "connection_type": device_client.config.connection_type,
        "connection_mode": resolved_connection_mode or device_client.config.connection_mode,
        "serial_port": device_client.config.serial_port,
        "baud_rate": device_client.config.baud_rate,
        "parity": device_client.config.parity,
        "stop_bits": device_client.config.stop_bits,
        "hass": device_client.hass,
    }


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
        return build_scanner_kwargs(
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
