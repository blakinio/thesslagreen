"""Reusable typing protocols used across integration layers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Protocol, TypeAlias

from homeassistant.core import HomeAssistant, ServiceCall


class ScannerProtocol(Protocol):
    """Protocol for scanner instances used by service handlers."""

    async def scan_device(self) -> dict[str, Any]: ...
    async def close(self) -> None: ...


class ScannerFactory(Protocol):
    """Protocol for asynchronous scanner factory callables."""

    def __call__(
        self,
        *,
        host: str,
        port: int,
        slave_id: int,
        timeout: int,
        retry: int,
        scan_uart_settings: bool,
        skip_known_missing: bool,
        full_register_scan: bool,
        max_registers_per_request: int,
        hass: HomeAssistant,
    ) -> Awaitable[ScannerProtocol]: ...


IterTargetCoordinators: TypeAlias = Callable[[HomeAssistant, ServiceCall], list[tuple[str, Any]]]  # noqa: UP040
NormalizeOption: TypeAlias = Callable[[str], str]  # noqa: UP040
ClampAirflowRate: TypeAlias = Callable[[Any, int], int]  # noqa: UP040
WriteRegister: TypeAlias = Callable[[Any, str, Any, str, str], Awaitable[bool]]  # noqa: UP040
CreateLogLevelManager: TypeAlias = Callable[[HomeAssistant], Any]  # noqa: UP040
DateTimeNow: TypeAlias = Callable[[], datetime]  # noqa: UP040
