"""Asynchronous data coordinator for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as _dt_util
from pymodbus.client import AsyncModbusTcpClient

from .._coordinator_connection_test import run_connection_test as _run_connection_test_impl
from .._coordinator_device_info import run_device_scan as _run_device_scan_impl
from .._coordinator_device_info import warn_missing_device_info as _warn_missing_device_info_impl
from .._coordinator_factory import build_config_from_params as _build_config_from_params_impl
from .._coordinator_init import normalize_runtime_config as _normalize_runtime_config_impl
from .._coordinator_register_groups import (
    compute_register_groups as _compute_register_groups_impl,
)
from .._coordinator_register_processing import (
    find_register_name as _find_register_name_impl,
)
from .._coordinator_register_processing import (
    process_register_value as _process_register_value_impl,
)
from .._coordinator_scan_result import apply_scan_result as _apply_scan_result_impl
from .._coordinator_scanner_kwargs import build_scanner_kwargs as _build_scanner_kwargs_impl
from .._coordinator_transport_select import select_auto_transport as _select_auto_transport_impl
from ..const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_BACKOFF,
    DEFAULT_BACKOFF_JITTER,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_STOP_BITS,
    DOMAIN,
    HOLDING_BATCH_BOUNDARIES,
    KNOWN_MISSING_REGISTERS,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
    UNKNOWN_MODEL,
    input_registers,
)
from ..coordinator_config import normalize_scan_interval as _normalize_scan_interval_impl
from ..coordinator_diagnostics import (
    device_name as _device_name_impl,
)
from ..coordinator_diagnostics import (
    get_device_info as _get_device_info_impl,
)
from ..coordinator_diagnostics import (
    get_diagnostic_data as _get_diagnostic_data_impl,
)
from ..coordinator_diagnostics import (
    performance_stats as _performance_stats_impl,
)
from ..coordinator_diagnostics import (
    status_overview as _status_overview_impl,
)
from ..coordinator_runtime import normalize_backoff as _normalize_backoff_impl
from ..coordinator_runtime import parse_backoff_jitter as _parse_backoff_jitter_impl
from ..coordinator_state import (
    initialize_runtime_state as _initialize_runtime_state_impl,
)
from ..coordinator_state import normalize_serial_settings as _normalize_serial_settings_impl
from ..coordinator_state import resolve_effective_batch as _resolve_effective_batch_impl
from ..errors import CannotConnect
from ..modbus_exceptions import ConnectionException, ModbusException
from ..modbus_helpers import group_reads
from ..modbus_transport import (
    BaseModbusTransport,
)
from ..register_defs_cache import get_register_definitions
from ..registers.register_def import RegisterDef
from ..scanner import (
    DeviceCapabilities,
    ThesslaGreenDeviceScanner,
    is_request_cancelled_error,
)
from ..utils import resolve_connection_settings
from .capabilities import _CoordinatorCapabilitiesMixin
from .connection import (
    build_rtu_transport as _build_rtu_transport_impl,
)
from .connection import (
    build_tcp_transport as _build_tcp_transport_impl,
)
from .connection import (
    connect_direct_tcp_client as _connect_direct_tcp_client_impl,
)
from .connection import (
    connect_transport_or_client as _connect_transport_or_client_impl,
)
from .connection import (
    ensure_transport_selected as _ensure_transport_selected_impl,
)
from .connection import (
    reconnect_client_if_needed as _reconnect_client_if_needed_impl,
)
from .connection import (
    setup_client_with_retry as _setup_client_with_retry_impl,
)
from .io import _ModbusIOMixin
from .models import CoordinatorConfig
from .retry import _PermanentModbusError
from .scan import (
    apply_scan_cache as _apply_scan_cache_impl,
)
from .scan import (
    firmware_lacks_known_missing as _firmware_lacks_known_missing_impl,
)
from .scan import (
    load_full_register_list as _load_full_register_list_impl,
)
from .scan import (
    normalise_available_registers as _normalise_available_registers_impl,
)
from .scan import (
    normalise_cached_register_name as _normalise_cached_register_name_impl,
)
from .scan import (
    store_scan_cache as _store_scan_cache_impl,
)
from .schedule import _CoordinatorScheduleMixin
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


_ORIGINAL_ASYNC_MODBUS_TCP_CLIENT = AsyncModbusTcpClient


def get_register_definition(name: str) -> RegisterDef:
    return get_register_definitions()[name]


_LOGGER = logging.getLogger(__name__)


class ThesslaGreenModbusCoordinator(
    _ModbusIOMixin,
    _CoordinatorCapabilitiesMixin,
    _CoordinatorScheduleMixin,
    DataUpdateCoordinator[dict[str, Any]],
):
    """Optimized data coordinator for ThesslaGreen Modbus device."""

    offline_state: bool
    _reauth_scheduled: bool
    _stop_listener: Callable[..., Any] | None

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

        try:
            super().__init__(
                hass,
                _LOGGER,
                config_entry=entry,
                name=f"{DOMAIN}_{entry.entry_id if entry else normalized_cfg.name}",
                update_interval=update_interval,
            )
        except TypeError:
            super().__init__(
                hass,
                _LOGGER,
                name=f"{DOMAIN}_{entry.entry_id if entry else normalized_cfg.name}",
                update_interval=update_interval,
            )
        self.hass = hass

        self._device_name = normalized_cfg.name
        self.config = normalized_cfg
        self._resolved_connection_mode = resolved_connection_mode
        self.timeout = normalized_cfg.timeout
        self.retry = normalized_cfg.retry
        self.backoff = _normalize_backoff_impl(normalized_cfg.backoff)

        self.backoff_jitter = self._parse_backoff_jitter(normalized_cfg.backoff_jitter)
        self.force_full_register_list = normalized_cfg.force_full_register_list
        self.scan_uart_settings = normalized_cfg.scan_uart_settings
        self.deep_scan = normalized_cfg.deep_scan
        self.safe_scan = normalized_cfg.safe_scan
        self.entry = entry
        self.skip_missing_registers = normalized_cfg.skip_missing_registers

        self.effective_batch = _resolve_effective_batch_impl(
            entry, normalized_cfg.max_registers_per_request
        )
        self.max_registers_per_request = self.effective_batch

        self.config.max_registers_per_request = self.max_registers_per_request
        self.config.backoff = self.backoff
        self.config.backoff_jitter = self.backoff_jitter

        _initialize_runtime_state_impl(self, entry=entry)

    @property
    def host(self) -> str:
        """Host accessor backed by CoordinatorConfig."""
        return self.config.host

    @host.setter
    def host(self, value: str) -> None:
        self.config.host = value

    @property
    def port(self) -> int:
        """Port accessor backed by CoordinatorConfig."""
        return self.config.port

    @port.setter
    def port(self, value: int) -> None:
        self.config.port = value

    @property
    def slave_id(self) -> int:
        """Slave ID accessor backed by CoordinatorConfig."""
        return self.config.slave_id

    @slave_id.setter
    def slave_id(self, value: int) -> None:
        self.config.slave_id = value

    @property
    def connection_type(self) -> str:
        """Connection type accessor backed by CoordinatorConfig."""
        return self.config.connection_type

    @connection_type.setter
    def connection_type(self, value: str) -> None:
        self.config.connection_type = value

    @property
    def connection_mode(self) -> str | None:
        """Connection mode accessor backed by CoordinatorConfig."""
        return self.config.connection_mode

    @connection_mode.setter
    def connection_mode(self, value: str | None) -> None:
        self.config.connection_mode = value

    @property
    def serial_port(self) -> str:
        """Serial port accessor backed by CoordinatorConfig."""
        return self.config.serial_port

    @serial_port.setter
    def serial_port(self, value: str) -> None:
        self.config.serial_port = value

    @property
    def baud_rate(self) -> int:
        """Baud rate accessor backed by CoordinatorConfig."""
        return self.config.baud_rate

    @baud_rate.setter
    def baud_rate(self, value: int) -> None:
        self.config.baud_rate = value

    @property
    def parity(self) -> str:
        """Parity accessor backed by CoordinatorConfig."""
        return self.config.parity

    @parity.setter
    def parity(self, value: str) -> None:
        self.config.parity = value

    @property
    def stop_bits(self) -> int:
        """Stop bits accessor backed by CoordinatorConfig."""
        return self.config.stop_bits

    @stop_bits.setter
    def stop_bits(self, value: int) -> None:
        self.config.stop_bits = value

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
        _LOGGER.warning("Starting reauthentication for %s (%s)", self._device_name, reason)
        self.hass.async_create_task(self.entry.async_start_reauth(self.hass))

    def get_register_map(self, register_type: str) -> dict[str, int]:
        """Return the register map for the given register type."""
        return cast(dict[str, int], self._register_maps.get(register_type, {}))

    def _get_client_method(self, name: str) -> Callable[..., Any]:
        """Return a Modbus method from transport/client or a no-op placeholder."""

        transport = self._transport
        transport_method = getattr(transport, name, None) if transport is not None else None
        if callable(transport_method):
            return cast(Callable[..., Any], transport_method)
        """Return a Modbus client method or a no-op async placeholder."""

        client = self.client
        method = getattr(client, name, None) if client is not None else None
        if callable(method):
            return cast(Callable[..., Any], method)

        async def _missing_method(*_args: Any, **_kwargs: Any) -> Any:
            return None

        _missing_method.__name__ = name
        return _missing_method

    async def _read_coils_transport(
        self,
        _slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        if not self.client:
            raise ConnectionException("Modbus client is not connected")
        return await self._call_modbus(
            self.client.read_coils,
            address,
            count=count,
            attempt=attempt,
        )

    async def _read_discrete_inputs_transport(
        self,
        _slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        if not self.client:
            raise ConnectionException("Modbus client is not connected")
        return await self._call_modbus(
            self.client.read_discrete_inputs,
            address,
            count=count,
            attempt=attempt,
        )

    def _build_scanner_kwargs(self) -> dict[str, Any]:
        """Return constructor kwargs shared by all scanner creation paths."""
        return _build_scanner_kwargs_impl(
            self,
            resolved_connection_mode=self._resolved_connection_mode,
        )

    async def _create_scanner(self) -> Any:
        """Instantiate a ThesslaGreenDeviceScanner using its create() factory."""
        kwargs = self._build_scanner_kwargs()
        return await ThesslaGreenDeviceScanner.create(**kwargs)

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
        """Run a full device scan and apply the result."""
        await _run_device_scan_impl(
            create_scanner=self._create_scanner,
            apply_scan_result=self._apply_scan_result,
            logger=_LOGGER,
        )

    def _warn_missing_device_info(self) -> None:
        """Log warnings when model or firmware could not be identified."""
        _warn_missing_device_info_impl(
            device_info=self.device_info,
            config=self.config,
            device_name=self._device_name,
            logger=_LOGGER,
            unknown_model=UNKNOWN_MODEL,
        )

    async def async_setup(self) -> bool:
        """Set up the coordinator by scanning the device."""
        if self.config.connection_type == CONNECTION_TYPE_RTU:
            endpoint = self.config.serial_port or "serial"
        else:
            endpoint = f"{self.config.host}:{self.config.port}"
        _LOGGER.info(
            "Setting up ThesslaGreen coordinator for %s via %s",
            endpoint,
            self.config.connection_type.upper(),
        )

        if self.force_full_register_list:
            _LOGGER.info("Using full register list (skipping scan)")
            self._load_full_register_list()
        elif not self.enable_device_scan:
            cache: dict[str, Any] = {}
            if self.entry is not None:
                raw_cache = self.entry.options.get("device_scan_cache", {})
                if isinstance(raw_cache, dict):
                    cache = raw_cache
            if cache and self._apply_scan_cache(cache):
                _LOGGER.info("Using cached device scan results")
            else:
                _LOGGER.info("Device scan disabled; falling back to full register list")
                self._load_full_register_list()
        else:
            await self._run_device_scan()

        self._warn_missing_device_info()

        # Pre-compute register groups for batch reading
        self._compute_register_groups()

        # Test initial connection
        await self._test_connection()

        # Ensure we clean up tasks when Home Assistant stops
        if self._stop_listener is None and hasattr(self.hass, "bus"):
            self._stop_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._async_handle_stop
            )

        return True

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

    def _compute_register_groups(self) -> None:
        """Pre-compute register groups for optimized batch reading."""
        _compute_register_groups_impl(
            self,
            get_register_definition=get_register_definition,
            group_reads=group_reads,
            holding_batch_boundaries=HOLDING_BATCH_BOUNDARIES,
        )

    def _mark_registers_failed(self, names: Iterable[str | None]) -> None:
        """Record registers that failed to read."""
        failed: set[str] = getattr(self, "_failed_registers", set())
        failed.update(name for name in names if name)
        self._failed_registers = failed

    def _clear_register_failure(self, name: str) -> None:
        """Remove register from failed list on successful read."""
        if hasattr(self, "_failed_registers"):
            self._failed_registers.discard(name)

    async def _test_connection(self) -> None:
        """Test initial connection to the device."""
        async with self._write_lock:
            await _run_connection_test_impl(
                ensure_connection=self._ensure_connection,
                get_transport=lambda: self._transport,
                slave_id=self.config.slave_id,
                test_addresses=list(input_registers().values())[:3],
                is_cancelled_error=is_request_cancelled_error,
                logger=_LOGGER,
            )

    async def _async_setup_client(self) -> bool:
        """Set up the Modbus client if needed.

        Although only invoked in tests within this repository, this helper
        mirrors the logic executed during Home Assistant start-up. It returns
        ``True`` on success and ``False`` on failure.
        """
        return await _setup_client_with_retry_impl(
            ensure_connection=self._ensure_connection,
            logger=_LOGGER,
        )

    async def _ensure_connection(self) -> None:
        """Ensure Modbus connection is established."""

        await self._ensure_connected()

    def _build_tcp_transport(
        self,
        mode: str,
    ) -> BaseModbusTransport:
        return _build_tcp_transport_impl(
            mode=mode,
            host=self.config.host,
            port=self.config.port,
            retry=self.retry,
            backoff=self.backoff,
            max_backoff=DEFAULT_MAX_BACKOFF,
            timeout=self.timeout,
            offline_state=self.offline_state,
            connection_type_tcp=CONNECTION_TYPE_TCP,
            connection_mode_tcp_rtu=CONNECTION_MODE_TCP_RTU,
        )

    async def _try_direct_client_connect(self, *, allow_parameterless_ctor: bool) -> bool:
        """Try connecting via AsyncModbusTcpClient and store the connected client."""
        from custom_components.thessla_green_modbus import coordinator as coordinator_pkg

        tcp_client_cls = getattr(coordinator_pkg, "AsyncModbusTcpClient", AsyncModbusTcpClient)
        direct_client = await _connect_direct_tcp_client_impl(
            host=self.config.host,
            port=self.config.port,
            timeout=self.timeout,
            tcp_client_cls=tcp_client_cls,
            allow_parameterless_ctor=allow_parameterless_ctor,
        )
        if direct_client is not None:
            self.client = direct_client
            self._transport = None
            return True
        return False

    async def _select_auto_transport(self) -> None:
        """Attempt auto-detection between RTU-over-TCP and Modbus TCP."""

        transport, mode = await _select_auto_transport_impl(
            resolved_connection_mode=self._resolved_connection_mode,
            build_tcp_transport=self._build_tcp_transport,
            try_direct_client_connect=lambda allow_parameterless_ctor: self._try_direct_client_connect(
                allow_parameterless_ctor=allow_parameterless_ctor
            ),
            port=self.config.port,
            timeout=self.timeout,
            slave_id=self.config.slave_id,
            host=self.config.host,
            logger=_LOGGER,
        )
        if transport is not None:
            self._transport = transport
        if mode is not None:
            self._resolved_connection_mode = mode

    async def _ensure_connected(self) -> None:
        """Ensure Modbus connection is established using the shared client."""

        async with self._client_lock:
            if self._transport is not None and self._transport.is_connected():
                return
            if self._transport is None and self.client is not None:
                if await _reconnect_client_if_needed_impl(self.client):
                    return
            if self._transport is not None or self.client is not None:
                await self._disconnect_locked()

            try:
                parity = SERIAL_PARITY_MAP.get(
                    self.config.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY]
                )
                stop_bits = SERIAL_STOP_BITS_MAP.get(
                    self.config.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]
                )
                selected_transport, selected_mode = await _ensure_transport_selected_impl(
                    current_transport=self._transport,
                    connection_type=self.config.connection_type,
                    connection_mode=self.config.connection_mode,
                    host=self.config.host,
                    port=self.config.port,
                    serial_port=self.config.serial_port,
                    baudrate=self.config.baud_rate,
                    parity=parity,
                    stopbits=stop_bits,
                    retry=self.retry,
                    backoff=self.backoff,
                    max_backoff=DEFAULT_MAX_BACKOFF,
                    timeout=self.timeout,
                    offline_state=self.offline_state,
                    connection_type_rtu=CONNECTION_TYPE_RTU,
                    connection_mode_auto=CONNECTION_MODE_AUTO,
                    connection_mode_tcp=CONNECTION_MODE_TCP,
                    build_rtu_transport_fn=_build_rtu_transport_impl,
                    build_tcp_transport_fn=self._build_tcp_transport,
                    select_auto_transport_fn=lambda: _select_auto_transport_impl(
                        resolved_connection_mode=self._resolved_connection_mode,
                        build_tcp_transport=self._build_tcp_transport,
                        try_direct_client_connect=lambda allow_parameterless_ctor: self._try_direct_client_connect(
                            allow_parameterless_ctor=allow_parameterless_ctor
                        ),
                        port=self.config.port,
                        timeout=self.timeout,
                        slave_id=self.config.slave_id,
                        host=self.config.host,
                        logger=_LOGGER,
                    ),
                )
                if selected_transport is not None:
                    self._transport = selected_transport
                if selected_mode is not None:
                    self._resolved_connection_mode = selected_mode

                self.client = await _connect_transport_or_client_impl(
                    transport=self._transport,
                    client=self.client,
                )
                _LOGGER.debug("Modbus connection established")
                self.offline_state = False
            except (ModbusException, ConnectionException) as exc:
                self.statistics["connection_errors"] += 1
                self.offline_state = True
                _LOGGER.exception("Failed to establish connection: %s", exc)
                raise
            except TimeoutError as exc:
                self.statistics["connection_errors"] += 1
                self.offline_state = True
                _LOGGER.warning("Connection attempt timed out: %s", exc)
                raise
            except OSError as exc:
                self.statistics["connection_errors"] += 1
                self.offline_state = True
                _LOGGER.exception("Unexpected error establishing connection: %s", exc)
                raise

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device with optimized batch reading.

        This method overrides ``DataUpdateCoordinator._async_update_data``
        and is called by Home Assistant to refresh entity state.
        """
        return await _async_update_data_impl(self)

    def _find_register_name(self, register_type: str, address: int) -> str | None:
        """Find register name by address using pre-built reverse maps."""
        return _find_register_name_impl(self._reverse_maps, register_type, address)

    def _process_register_value(self, register_name: str, value: int) -> Any:
        """Decode a raw register value via dedicated register-processing helpers."""
        return _process_register_value_impl(register_name, value)

    async def _disconnect_locked(self) -> None:
        """Disconnect from Modbus device without acquiring locks."""

        if self._transport is not None:
            try:
                await self._transport.close()
            except (ModbusException, ConnectionException):
                _LOGGER.debug("Error disconnecting", exc_info=True)
            except OSError:
                _LOGGER.exception("Unexpected error disconnecting")
        elif self.client is not None:
            try:
                close = getattr(self.client, "close", None)
                if callable(close):
                    if inspect.iscoroutinefunction(close):
                        await close()
                    else:
                        result = close()
                        if inspect.isawaitable(result):
                            await result
            except (ModbusException, ConnectionException):
                _LOGGER.debug("Error disconnecting", exc_info=True)
            except OSError:
                _LOGGER.exception("Unexpected error disconnecting")

        self.client = None
        self.offline_state = True
        _LOGGER.debug("Disconnected from Modbus device")

    async def _disconnect(self) -> None:
        """Disconnect from Modbus device."""

        async with self._client_lock:
            await self._disconnect_locked()

    async def _async_handle_stop(self, _event: Any) -> None:
        """Handle Home Assistant stop to cancel tasks."""
        await self.async_shutdown()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
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
