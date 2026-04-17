"""Setup helpers extracted from integration entrypoint module."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import timedelta
from importlib import import_module
from typing import TYPE_CHECKING, Any

from .const import (
    CONF_CONNECTION_MODE,
    CONF_LOG_LEVEL,
    CONF_SLAVE_ID,
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_LOG_LEVEL,
    DOMAIN,
    async_setup_options,
)
from .errors import is_invalid_auth_error
from .mappings import async_setup_entity_mappings
from .modbus_exceptions import ConnectionException, ModbusException
from .utils import resolve_connection_settings

if TYPE_CHECKING:  # pragma: no cover
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])

_platform_cache: list[object] | None = None


def _supports_typed_factory(coordinator_cls: Any) -> bool:
    """Return True when class can safely use from_config in runtime."""
    if not hasattr(coordinator_cls, "from_config"):
        return False
    try:
        from unittest.mock import Mock
    except ImportError:  # pragma: no cover
        return True
    return not isinstance(coordinator_cls, Mock)


def _scan_interval_seconds(scan_interval: timedelta | int) -> int:
    """Normalize scan interval (timedelta|int) to integer seconds."""
    if isinstance(scan_interval, timedelta):
        return int(scan_interval.total_seconds())
    return int(scan_interval)


def _get_platforms(platform_domains: list[str]) -> list[object]:
    """Return supported platform enums or plain strings."""
    global _platform_cache
    if _platform_cache is not None:
        return _platform_cache

    try:  # Import only when running inside Home Assistant
        from homeassistant.const import Platform
    except (ImportError, ModuleNotFoundError, AttributeError):  # pragma: no cover
        _platform_cache = list(platform_domains)
        return _platform_cache

    platforms: list[Platform] = []
    for domain in platform_domains:
        if hasattr(Platform, domain.upper()):
            platforms.append(getattr(Platform, domain.upper()))
        else:  # pragma: no cover
            try:
                platforms.append(Platform(domain))
            except (ValueError, TypeError):  # pragma: no cover
                _LOGGER.warning("Skipping unsupported platform: %s", domain)
    _platform_cache = platforms
    return platforms


def _apply_log_level(log_level: str) -> None:
    """Adjust the integration logger level dynamically."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    base_logger = logging.getLogger(__package__ or DOMAIN)
    base_logger.setLevel(level)
    _LOGGER.debug("Log level set to %s", log_level)


async def async_create_coordinator(hass: HomeAssistant, entry: ConfigEntry) -> Any:  # pragma: no cover
    """Read config entry options and instantiate the coordinator."""
    from .coordinator import CoordinatorConfig, ThesslaGreenModbusCoordinator

    config = CoordinatorConfig.from_entry(entry)
    if CONF_SLAVE_ID not in entry.data and "unit" in entry.data:
        config.slave_id = int(entry.data["unit"])

    connection_type = config.connection_type
    if connection_type not in (CONNECTION_TYPE_TCP, CONNECTION_TYPE_RTU, CONNECTION_TYPE_TCP_RTU):
        connection_type = DEFAULT_CONNECTION_TYPE
    connection_mode = entry.options.get(CONF_CONNECTION_MODE, config.connection_mode)
    connection_type, connection_mode = resolve_connection_settings(connection_type, connection_mode, config.port)
    config.connection_type = connection_type
    config.connection_mode = connection_mode

    log_level = entry.options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)
    _apply_log_level(str(log_level))

    if connection_type == CONNECTION_TYPE_RTU:
        endpoint = config.serial_port or "serial"
        transport_label = "Modbus RTU"
    elif connection_mode == CONNECTION_MODE_TCP_RTU:
        endpoint = f"{config.host}:{config.port}"
        transport_label = "Modbus TCP RTU"
    else:
        endpoint = f"{config.host}:{config.port}"
        transport_label = "Modbus TCP"
        if connection_mode == CONNECTION_MODE_AUTO:
            transport_label = "Modbus TCP (Auto)"

    _LOGGER.info(
        "Initializing ThesslaGreen device: %s via %s (%s) (slave_id=%s, scan_interval=%ds)",
        config.name,
        transport_label,
        endpoint,
        config.slave_id,
        _scan_interval_seconds(config.scan_interval),
    )
    scan_interval_seconds = _scan_interval_seconds(config.scan_interval)

    if _supports_typed_factory(ThesslaGreenModbusCoordinator):
        return ThesslaGreenModbusCoordinator.from_config(hass, config, entry=entry)

    return ThesslaGreenModbusCoordinator(
        hass=hass,
        host=config.host,
        port=config.port,
        slave_id=config.slave_id,
        name=config.name,
        connection_type=config.connection_type,
        connection_mode=config.connection_mode,
        serial_port=config.serial_port,
        baud_rate=config.baud_rate,
        parity=config.parity,
        stop_bits=config.stop_bits,
        timeout=config.timeout,
        retry=config.retry,
        backoff=config.backoff,
        backoff_jitter=config.backoff_jitter,
        force_full_register_list=config.force_full_register_list,
        scan_uart_settings=config.scan_uart_settings,
        deep_scan=config.deep_scan,
        safe_scan=config.safe_scan,
        skip_missing_registers=config.skip_missing_registers,
        max_registers_per_request=config.max_registers_per_request,
        scan_interval=timedelta(seconds=scan_interval_seconds),
        entry=entry,
    )


async def async_start_coordinator(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: Any
) -> bool:  # pragma: no cover
    """Run coordinator async_setup and first refresh."""
    from homeassistant.exceptions import ConfigEntryNotReady
    from homeassistant.helpers.update_coordinator import UpdateFailed

    async def _handle_start_exception(exc: Exception, *, phase: str, user_message: str) -> bool:
        if is_invalid_auth_error(exc):
            _LOGGER.error("Authentication failed during %s: %s", phase, exc)
            await entry.async_start_reauth(hass)
            return False
        if isinstance(exc, ConfigEntryNotReady):
            raise exc
        _LOGGER.error("Failed during %s: %s", phase, exc)
        raise ConfigEntryNotReady(f"{user_message}: {exc}") from exc

    try:
        setup_result = coordinator.async_setup()
        if inspect.isawaitable(setup_result):
            await setup_result
    except asyncio.CancelledError:
        raise
    except (TimeoutError, ConnectionException, ModbusException, OSError) as exc:
        return await _handle_start_exception(
            exc, phase="setup", user_message="Unable to connect to device"
        )
    except Exception as exc:  # noqa: BLE001
        return await _handle_start_exception(
            exc, phase="setup", user_message="Unable to connect to device"
        )

    try:
        refresh_cb = None
        if hasattr(coordinator, "async_config_entry_first_refresh"):
            refresh_cb = coordinator.async_config_entry_first_refresh
        elif hasattr(coordinator, "async_refresh"):
            refresh_cb = coordinator.async_refresh
        elif hasattr(coordinator, "async_request_refresh"):
            refresh_cb = coordinator.async_request_refresh
        if refresh_cb is not None:
            refresh_result = refresh_cb()
            if inspect.isawaitable(refresh_result):
                await refresh_result
    except asyncio.CancelledError:
        raise
    except (TimeoutError, ConnectionException, ModbusException, UpdateFailed, OSError) as exc:
        return await _handle_start_exception(
            exc, phase="initial refresh", user_message="Unable to fetch initial data"
        )
    except Exception as exc:  # noqa: BLE001
        return await _handle_start_exception(
            exc, phase="initial refresh", user_message="Unable to fetch initial data"
        )

    return True


async def async_setup_mappings(hass: HomeAssistant) -> None:  # pragma: no cover
    """Load option lists and entity mappings."""
    await async_setup_options(hass)
    await async_setup_entity_mappings(hass)


async def async_setup_platforms(
    hass: HomeAssistant, entry: ConfigEntry, platform_domains: list[str]
) -> None:  # pragma: no cover
    """Preload platform modules and forward config entry setup."""
    for platform in platform_domains:
        try:
            await hass.async_add_executor_job(import_module, f".{platform}", __package__)
        except (ImportError, ModuleNotFoundError) as err:
            _LOGGER.debug("Could not preload platform %s: %s", platform, err)
        except (TypeError, ValueError, RuntimeError, AttributeError, OSError) as err:
            _LOGGER.exception("Unexpected error preloading platform %s: %s", platform, err)

    platforms = _get_platforms(platform_domains)
    _LOGGER.debug("Setting up platforms: %s", platforms)
    try:
        forward_result = hass.config_entries.async_forward_entry_setups(entry, platforms)
        if inspect.isawaitable(forward_result):
            await forward_result
    except asyncio.CancelledError:
        _LOGGER.info("Platform setup cancelled for %s", platforms)
        raise
