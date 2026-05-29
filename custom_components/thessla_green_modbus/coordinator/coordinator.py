"""Asynchronous data coordinator for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as _dt_util

from ..const import (
    CONNECTION_MODE_AUTO,
    DEFAULT_BACKOFF,
    DEFAULT_BACKOFF_JITTER,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_STOP_BITS,
    DOMAIN,
    KNOWN_MISSING_REGISTERS,
    UNKNOWN_MODEL,
)
from ..core.capabilities_mixin import _CoordinatorCapabilitiesMixin
from ..core.client import ThesslaGreenDeviceClient
from ..core.connection import setup_client_with_retry as _setup_client_with_retry_impl
from ..core.connection_test import run_connection_test as _run_connection_test_impl
from ..core.models import CoordinatorConfig
from ..core.retry import _PermanentModbusError
from ..core.scan_helpers import (
    normalise_available_registers as _normalise_available_registers_impl,
)
from ..core.scan_helpers import (
    normalise_cached_register_name as _normalise_cached_register_name_impl,
)
from ..errors import CannotConnect
from ..register_defs_cache import get_register_definitions
from ..registers.maps import input_registers
from ..registers.register_def import RegisterDef
from ..scanner import (
    DeviceCapabilities,
    ThesslaGreenDeviceScanner,  # noqa: F401 – patch target for tests
    is_request_cancelled_error,
)
from ..utils import resolve_connection_settings
from .config_normalization import normalize_scan_interval as _normalize_scan_interval_impl
from .config_properties import _CoordinatorConfigPropertiesMixin
from .device_info import run_device_scan as _run_device_scan_impl
from .device_info import warn_missing_device_info as _warn_missing_device_info_impl
from .diagnostics import (
    device_name as _device_name_impl,
)
from .diagnostics import (
    get_device_info as _get_device_info_impl,
)
from .diagnostics import (
    get_diagnostic_data as _get_diagnostic_data_impl,
)
from .diagnostics import (
    performance_stats as _performance_stats_impl,
)
from .diagnostics import (
    status_overview as _status_overview_impl,
)
from .factory import build_config_from_params as _build_config_from_params_impl
from .init_config import apply_coordinator_config as _apply_coordinator_config_impl
from .init_config import normalize_runtime_config as _normalize_runtime_config_impl
from .lifecycle import async_setup as _async_setup_impl
from .runtime import normalize_backoff as _normalize_backoff_impl
from .runtime import parse_backoff_jitter as _parse_backoff_jitter_impl
from .scan import (
    apply_scan_cache as _apply_scan_cache_impl,
)
from .scan import (
    consume_config_flow_scan_cache as _consume_config_flow_scan_cache_impl,
)
from .scan import (
    firmware_lacks_known_missing as _firmware_lacks_known_missing_impl,
)
from .scan import (
    get_scan_cache_from_entry as _get_scan_cache_from_entry_impl,
)
from .scan import (
    load_full_register_list as _load_full_register_list_impl,
)
from .scan import (
    prepare_registers_for_setup as _prepare_registers_for_setup_impl,
)
from .scan import (
    store_scan_cache as _store_scan_cache_impl,
)
from .scan_result import apply_scan_result as _apply_scan_result_impl
from .schedule import _CoordinatorScheduleMixin
from .state import (
    initialize_runtime_state as _initialize_runtime_state_impl,
)
from .state import normalize_serial_settings as _normalize_serial_settings_impl
from .state import resolve_effective_batch as _resolve_effective_batch_impl
from .update import async_update_data as _async_update_data_impl

__all__ = [
    "CoordinatorConfig",
    "ThesslaGreenModbusCoordinator",
    "_PermanentModbusError",
]


dt_util = _dt_util


def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    from ..utils import utcnow as _utils_utcnow

    return _utils_utcnow()


def get_register_definition(name: str) -> RegisterDef:
    return get_register_definitions()[name]


_LOGGER = logging.getLogger(__name__)


class ThesslaGreenModbusCoordinator(
    _CoordinatorCapabilitiesMixin,
    _CoordinatorConfigPropertiesMixin,
    _CoordinatorScheduleMixin,
    DataUpdateCoordinator[dict[str, Any]],
):
    """Optimized data coordinator for ThesslaGreen Modbus device.

    Acts as the Home Assistant integration boundary.  All device-domain
    operations are delegated to ``self._device_client``.  Access device
    state via ``coordinator.device_client.X``.
    """

    _reauth_scheduled: bool
    _shutting_down: bool
    _stop_listener: Callable[..., Any] | None

    @property
    def device_client(self) -> ThesslaGreenDeviceClient:
        """Return the underlying DeviceClient instance."""
        return self._device_client

    def __init__(
        self,
        hass: HomeAssistant,
        config: CoordinatorConfig,
        *,
        entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the coordinator."""
        cfg = config

        normalized_cfg, resolved_connection_mode, interval_seconds = _normalize_runtime_config_impl(
            cfg,
            normalize_scan_interval=_normalize_scan_interval_impl,
            resolve_connection_settings=resolve_connection_settings,
            normalize_serial_settings=_normalize_serial_settings_impl,
        )
        update_interval = timedelta(seconds=interval_seconds)
        self.scan_interval = interval_seconds

        # Compute effective_batch early so DeviceClient can be created before
        # _apply_coordinator_config_impl runs (which sets attrs via property proxies).
        _pre_effective_batch = _resolve_effective_batch_impl(
            entry, normalized_cfg.max_registers_per_request
        )
        _pre_backoff = _normalize_backoff_impl(normalized_cfg.backoff)
        _pre_jitter = _parse_backoff_jitter_impl(normalized_cfg.backoff_jitter)

        # Create DeviceClient first — it owns all device-domain state and Modbus IO.
        self._device_client = ThesslaGreenDeviceClient(
            normalized_cfg,
            hass=hass,
            effective_batch=_pre_effective_batch,
            resolved_connection_mode=resolved_connection_mode
            if resolved_connection_mode != CONNECTION_MODE_AUTO
            else None,
            backoff=_pre_backoff,
            backoff_jitter=_pre_jitter,
            entry=entry,
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id if entry else normalized_cfg.name}",
            update_interval=update_interval,
        )
        self.hass = hass

        # Apply coordinator config — property proxies forward writes to DeviceClient.
        _apply_coordinator_config_impl(
            self,
            normalized_cfg,
            resolved_connection_mode,
            entry,
            normalize_backoff_fn=_normalize_backoff_impl,
            parse_backoff_jitter_fn=_parse_backoff_jitter_impl,
            resolve_effective_batch_fn=_resolve_effective_batch_impl,
        )

        # Initialize runtime state — property proxies forward writes to DeviceClient.
        _initialize_runtime_state_impl(self, entry=entry)

    @classmethod
    def from_params(
        cls,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        name: str = DEFAULT_NAME,
        scan_interval: timedelta | int = DEFAULT_SCAN_INTERVAL,
        timeout: int = 10,
        retry: int = 3,
        backoff: float = DEFAULT_BACKOFF,
        backoff_jitter: float | tuple[float, float] | None = DEFAULT_BACKOFF_JITTER,
        force_full_register_list: bool = False,
        scan_uart_settings: bool = DEFAULT_SCAN_UART_SETTINGS,
        deep_scan: bool = False,
        safe_scan: bool = False,
        max_registers_per_request: int = DEFAULT_MAX_REGISTERS_PER_REQUEST,
        entry: ConfigEntry | None = None,
        skip_missing_registers: bool = False,
        connection_type: str = DEFAULT_CONNECTION_TYPE,
        connection_mode: str | None = None,
        serial_port: str = DEFAULT_SERIAL_PORT,
        baud_rate: int = DEFAULT_BAUD_RATE,
        parity: str = DEFAULT_PARITY,
        stop_bits: int = DEFAULT_STOP_BITS,
    ) -> ThesslaGreenModbusCoordinator:
        """Construct coordinator from explicit parameters."""
        return cls(
            hass=hass,
            config=_build_config_from_params_impl(
                host=host,
                port=port,
                slave_id=slave_id,
                name=name,
                scan_interval=scan_interval,
                timeout=timeout,
                retry=retry,
                backoff=backoff,
                backoff_jitter=backoff_jitter,
                force_full_register_list=force_full_register_list,
                scan_uart_settings=scan_uart_settings,
                deep_scan=deep_scan,
                safe_scan=safe_scan,
                max_registers_per_request=max_registers_per_request,
                skip_missing_registers=skip_missing_registers,
                connection_type=connection_type,
                connection_mode=connection_mode,
                serial_port=serial_port,
                baud_rate=baud_rate,
                parity=parity,
                stop_bits=stop_bits,
            ),
            entry=entry,
        )

    @staticmethod
    def _parse_backoff_jitter(
        value: float | int | str | tuple[float, float] | list[float] | None,
    ) -> float | tuple[float, float] | None:
        """Normalize backoff_jitter input to None, float, or (float, float)."""
        return _parse_backoff_jitter_impl(value)

    def _trigger_reauth(self, reason: str) -> None:
        """Schedule a reauthentication flow if not already triggered."""

        if self._reauth_scheduled or self.entry is None:
            return

        self._reauth_scheduled = True
        _LOGGER.warning(
            "Starting reauthentication for %s (%s)", self._device_client._device_name, reason
        )
        self.hass.async_create_task(self.entry.async_start_reauth(self.hass))

    def get_register_map(self, register_type: str) -> dict[str, int]:
        """Return the register map for the given register type."""
        return self._device_client.get_register_map(register_type)

    def _apply_scan_result(self, scan_result: dict[str, Any]) -> None:
        """Store and process a completed device scan result."""
        _apply_scan_result_impl(
            self,
            scan_result,
            connection_mode_auto=CONNECTION_MODE_AUTO,
            known_missing_registers=KNOWN_MISSING_REGISTERS,
            device_capabilities_cls=DeviceCapabilities,
            cannot_connect_exc=CannotConnect,
            now_fn=_utcnow,
            logger=_LOGGER,
            unknown_model=UNKNOWN_MODEL,
        )

    async def _run_device_scan(self) -> None:
        """Run a full device scan and apply the result.

        Device scanning is delegated to DeviceClient; the coordinator keeps
        ownership of applying the result (which writes to HA entry options).
        """
        await _run_device_scan_impl(
            create_scanner=self._device_client.async_create_scanner,
            apply_scan_result=self._apply_scan_result,
            logger=_LOGGER,
        )

    def _warn_missing_device_info(self) -> None:
        """Log warnings when model or firmware could not be identified."""
        _warn_missing_device_info_impl(
            device_info=self._device_client.device_info,
            config=self._device_client.config,
            device_name=self._device_client._device_name,
            logger=_LOGGER,
            unknown_model=UNKNOWN_MODEL,
        )

    async def async_setup(self) -> bool:
        """Set up the coordinator by scanning the device."""
        return await _async_setup_impl(self)

    async def _prepare_registers_for_setup(self) -> None:
        """Prepare register availability from full list, cache, or device scan."""
        await _prepare_registers_for_setup_impl(self)

    def _get_scan_cache_from_entry(self) -> dict[str, Any]:
        """Return cached scan payload from config entry options."""
        return _get_scan_cache_from_entry_impl(self.entry)

    def _consume_config_flow_scan_cache(self) -> dict[str, Any]:
        """Read and clear the one-time config-flow scan cache from entry options."""
        return _consume_config_flow_scan_cache_impl(self)

    def _load_full_register_list(self) -> None:
        """Load full register list when forced."""
        _load_full_register_list_impl(self)

    @staticmethod
    def _normalise_cached_register_name(name: str) -> str:
        """Normalise cached register names to current canonical form."""
        return _normalise_cached_register_name_impl(name)

    def _normalise_available_registers(
        self, available: dict[str, list[str] | set[str]]
    ) -> dict[str, set[str]]:
        """Return available register names in canonical form."""
        return _normalise_available_registers_impl(self, available)

    def _apply_scan_cache(self, cache: dict[str, Any]) -> bool:
        """Apply cached scan data if available."""
        return bool(_apply_scan_cache_impl(self, cache))

    @staticmethod
    def _firmware_lacks_known_missing(firmware: Any) -> bool:
        """Return True for firmwares that do not expose KNOWN_MISSING_REGISTERS."""
        return bool(_firmware_lacks_known_missing_impl(firmware))

    def _store_scan_cache(self) -> None:
        """Store scan results in config entry options."""
        _store_scan_cache_impl(self)

    async def _test_connection(self) -> None:
        """HA-boundary adapter — called by coordinator/lifecycle.py during HA setup."""
        async with self._device_client._write_lock:
            await _run_connection_test_impl(
                ensure_connection=self._ensure_connection,
                get_transport=lambda: self._device_client._transport,
                get_client=lambda: self._device_client.client,
                slave_id=self.slave_id,
                test_addresses=list(input_registers().values())[:3],
                is_cancelled_error=is_request_cancelled_error,
                logger=_LOGGER,
            )

    async def _async_setup_client(self) -> bool:
        """Intentional test-facing helper — exercises setup-client-with-retry logic.

        Only invoked in tests; it mirrors the connection-establishment path that runs
        during Home Assistant start-up so that path can be unit-tested without a full
        HA lifecycle.  Returns ``True`` on success and ``False`` on failure.
        """
        return await _setup_client_with_retry_impl(
            ensure_connection=self._ensure_connection,
            logger=_LOGGER,
        )

    async def _ensure_connection(self) -> None:
        """HA-boundary adapter — called by coordinator submodules and duck-typed by core.

        Submodules (schedule, update, retry, client_registers) receive ``coordinator``
        and call ``_ensure_connection()`` to establish the Modbus connection.  This is
        an intentional boundary method; it is *not* proxy debt.
        """
        await self._device_client.async_ensure_connected()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device with optimized batch reading.

        This method overrides ``DataUpdateCoordinator._async_update_data``
        and is called by Home Assistant to refresh entity state.
        """
        return await _async_update_data_impl(self)

    async def _disconnect_locked(self) -> None:
        """HA-boundary adapter — passed as a callback to core.connection_lifecycle.

        ``ensure_connected_lifecycle`` receives this as ``disconnect_locked_fn`` so it
        can disconnect without re-acquiring the already-held client lock.  This is an
        intentional boundary method; it is *not* proxy debt.
        """
        await self._device_client._disconnect_locked()

    async def _disconnect(self) -> None:
        """HA-boundary adapter — disconnect called by coordinator submodules.

        Used by errors, schedule, update, write_path, and async_shutdown.  This is an
        intentional boundary method; it is *not* proxy debt.
        """
        async with self._device_client._client_lock:
            await self._disconnect_locked()

    async def _async_handle_stop(self, _event: Any) -> None:
        """Handle Home Assistant stop to cancel tasks."""
        await self.async_shutdown()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
        self._shutting_down = True
        if self._stop_listener is not None:
            self._stop_listener()
            self._stop_listener = None
        super_shutdown = getattr(super(), "async_shutdown", None)
        if callable(super_shutdown):
            result = super_shutdown()
            if inspect.isawaitable(result):
                await result
        await self._disconnect()

    @property
    def status_overview(self) -> dict[str, Any]:
        """Return a concise online/offline status summary."""
        return _status_overview_impl(self)

    @property
    def performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return _performance_stats_impl(self)

    def get_diagnostic_data(self) -> dict[str, Any]:
        """Return diagnostic information for Home Assistant."""
        return _get_diagnostic_data_impl(self)

    def get_device_info(self) -> dict[str, Any]:
        """Return device info mapping for the connected unit."""
        return _get_device_info_impl(self)

    @property
    def device_name(self) -> str:
        """Return the configured or detected device name."""
        return _device_name_impl(self)
