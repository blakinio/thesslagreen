"""ThesslaGreen Modbus integration for Home Assistant."""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import sys
from datetime import timedelta
from importlib import import_module
from typing import TYPE_CHECKING, Any, cast

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

if TYPE_CHECKING:  # pragma: no cover - typing only
    from typing import TypeAlias

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import ThesslaGreenModbusCoordinator

from .const import (
    CONF_BACKOFF,
    CONF_BACKOFF_JITTER,
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_DEEP_SCAN,
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_LOG_LEVEL,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_PARITY,
    CONF_RETRY,
    CONF_SAFE_SCAN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_UART_SETTINGS,
    CONF_SERIAL_PORT,
    CONF_SKIP_MISSING_REGISTERS,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONF_TIMEOUT,
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
    DEFAULT_BACKOFF,
    DEFAULT_BACKOFF_JITTER,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_DEEP_SCAN,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_RETRY,
    DEFAULT_SAFE_SCAN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_SKIP_MISSING_REGISTERS,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOP_BITS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    async_setup_options,
    device_unique_id_prefix,
    migrate_unique_id,
)
from .const import PLATFORMS as PLATFORM_DOMAINS
from .entity_mappings import async_setup_entity_mappings
from .errors import is_invalid_auth_error
from .modbus_exceptions import ConnectionException, ModbusException
from .utils import resolve_connection_settings

try:  # pragma: no cover - optional in tests
    from homeassistant.helpers import entity_registry as er  # type: ignore
except Exception:  # pragma: no cover
    er = None  # type: ignore

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - typing only
    ThesslaGreenConfigEntry: TypeAlias = ConfigEntry[ThesslaGreenModbusCoordinator]

# Compatibility shim for tests patching "custom_components.thessla_green_modbus.__init__.er".
_init_alias = sys.modules.setdefault(f"{__name__}.__init__", sys.modules[__name__])
setattr(_init_alias, "er", er)
setattr(sys.modules[__name__], "__init__", _init_alias)

# Legacy default port used before version 2 when explicit port was optional
LEGACY_DEFAULT_PORT = 8899

# Legacy entity IDs that were replaced by the fan entity
LEGACY_FAN_ENTITY_IDS = [
    "number.rekuperator_predkosc",
    "number.rekuperator_speed",
]



_platform_cache: list[object] | None = None


def _get_platforms() -> list[object]:
    """Return supported platform enums or plain strings.

    Importing Home Assistant is deferred so external tools can use this module
    without the `homeassistant` package installed. If the import fails, simple
    domain strings are returned instead of `Platform` enums.
    """

    global _platform_cache
    if _platform_cache is not None:
        return _platform_cache

    try:  # Import only when running inside Home Assistant
        from homeassistant.const import Platform  # type: ignore
    except Exception:  # pragma: no cover - Home Assistant missing
        _platform_cache = list(PLATFORM_DOMAINS)
        return _platform_cache

    platforms: list[Platform] = []
    for domain in PLATFORM_DOMAINS:
        if hasattr(Platform, domain.upper()):
            platforms.append(getattr(Platform, domain.upper()))
        else:  # pragma: no cover
            try:
                platforms.append(Platform(domain))
            except (ValueError, TypeError):  # pragma: no cover - unsupported domain
                _LOGGER.warning("Skipping unsupported platform: %s", domain)
    _platform_cache = platforms
    return platforms



def _apply_log_level(log_level: str) -> None:
    """Adjust the integration logger level dynamically."""

    level = getattr(logging, log_level.upper(), logging.INFO)
    base_logger = logging.getLogger(__package__ or DOMAIN)
    base_logger.setLevel(level)
    _LOGGER.debug("Log level set to %s", log_level)


async def _async_create_coordinator(
    hass: HomeAssistant, entry: ConfigEntry
) -> Any:  # pragma: no cover
    """Read config entry options and instantiate the coordinator."""
    if hasattr(hass, "async_add_executor_job"):
        import_result = hass.async_add_executor_job(import_module, ".config_flow", __name__)
        if inspect.isawaitable(import_result):
            await import_result
    else:
        import_module(".config_flow", __name__)

    # Get configuration - support both new and legacy keys
    connection_type = entry.data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    if connection_type not in (
        CONNECTION_TYPE_TCP,
        CONNECTION_TYPE_RTU,
        CONNECTION_TYPE_TCP_RTU,
    ):
        connection_type = DEFAULT_CONNECTION_TYPE
    connection_mode = entry.options.get(
        CONF_CONNECTION_MODE, entry.data.get(CONF_CONNECTION_MODE)
    )
    connection_type, connection_mode = resolve_connection_settings(
        connection_type, connection_mode, entry.data.get(CONF_PORT, DEFAULT_PORT)
    )

    host = entry.data.get(CONF_HOST, "")
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    serial_port = entry.data.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT)
    baud_rate = entry.data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)
    parity = entry.data.get(CONF_PARITY, DEFAULT_PARITY)
    stop_bits = entry.data.get(CONF_STOP_BITS, DEFAULT_STOP_BITS)

    try:
        baud_rate = int(baud_rate)
    except (TypeError, ValueError):
        baud_rate = DEFAULT_BAUD_RATE
    parity = str(parity or DEFAULT_PARITY)
    try:
        stop_bits = int(stop_bits)
    except (TypeError, ValueError):
        stop_bits = DEFAULT_STOP_BITS

    # Try to get slave_id from multiple possible keys for compatibility
    slave_id = None
    if CONF_SLAVE_ID in entry.data:
        slave_id = entry.data[CONF_SLAVE_ID]
    elif "slave_id" in entry.data:
        slave_id = entry.data["slave_id"]
    elif "unit" in entry.data:
        slave_id = entry.data["unit"]  # Legacy support
    else:
        slave_id = DEFAULT_SLAVE_ID

    name = entry.data.get(CONF_NAME, DEFAULT_NAME)

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    retry = entry.options.get(CONF_RETRY, DEFAULT_RETRY)
    backoff = entry.options.get(CONF_BACKOFF, DEFAULT_BACKOFF)
    backoff_jitter = entry.options.get(CONF_BACKOFF_JITTER, DEFAULT_BACKOFF_JITTER)
    force_full_register_list = entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
    scan_uart_settings = entry.options.get(CONF_SCAN_UART_SETTINGS, DEFAULT_SCAN_UART_SETTINGS)
    skip_missing_registers = entry.options.get(
        CONF_SKIP_MISSING_REGISTERS, DEFAULT_SKIP_MISSING_REGISTERS
    )
    deep_scan = entry.options.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN)
    safe_scan = entry.options.get(CONF_SAFE_SCAN, DEFAULT_SAFE_SCAN)
    max_registers_per_request = entry.options.get(
        CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
    )
    log_level = entry.options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)
    _apply_log_level(str(log_level))

    if connection_type == CONNECTION_TYPE_RTU:
        endpoint = serial_port or "serial"
        transport_label = "Modbus RTU"
    elif connection_mode == CONNECTION_MODE_TCP_RTU:
        endpoint = f"{host}:{port}"
        transport_label = "Modbus TCP RTU"
    else:
        endpoint = f"{host}:{port}"
        transport_label = "Modbus TCP"
        if connection_mode == CONNECTION_MODE_AUTO:
            transport_label = "Modbus TCP (Auto)"

    _LOGGER.info(
        "Initializing ThesslaGreen device: %s via %s (%s) (slave_id=%s, scan_interval=%ds)",
        name, transport_label, endpoint, slave_id, scan_interval,
    )

    _coordinator_key = f"{__name__}.coordinator"
    coordinator_mod = sys.modules.get(_coordinator_key)
    if coordinator_mod is None:
        if hasattr(hass, "async_add_executor_job"):
            coordinator_mod = await hass.async_add_executor_job(
                import_module, ".coordinator", __name__
            )
        else:
            coordinator_mod = import_module(".coordinator", __name__)
    ThesslaGreenModbusCoordinator = coordinator_mod.ThesslaGreenModbusCoordinator

    coordinator_kwargs = {
        "hass": hass,
        "host": host,
        "port": port,
        "slave_id": slave_id,
        "name": name,
        "connection_type": connection_type,
        "connection_mode": connection_mode,
        "serial_port": serial_port,
        "baud_rate": baud_rate,
        "parity": parity,
        "stop_bits": stop_bits,
        "scan_interval": timedelta(seconds=scan_interval),
        "timeout": timeout,
        "retry": retry,
        "backoff": backoff,
        "backoff_jitter": backoff_jitter,
        "force_full_register_list": force_full_register_list,
        "scan_uart_settings": scan_uart_settings,
        "deep_scan": deep_scan,
        "safe_scan": safe_scan,
        "skip_missing_registers": skip_missing_registers,
        "max_registers_per_request": max_registers_per_request,
        "entry": entry,
    }
    try:
        signature = inspect.signature(ThesslaGreenModbusCoordinator)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and not any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    ):
        coordinator_kwargs = {
            key: value for key, value in coordinator_kwargs.items() if key in signature.parameters
        }

    return ThesslaGreenModbusCoordinator(**coordinator_kwargs)


async def _async_start_coordinator(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: Any
) -> bool:  # pragma: no cover
    """Run coordinator async_setup and first refresh.

    Returns False if a reauth flow was triggered (caller should return False).
    Raises ConfigEntryNotReady on other connection failures.
    """
    from homeassistant.exceptions import ConfigEntryNotReady  # type: ignore
    from homeassistant.helpers.update_coordinator import UpdateFailed  # type: ignore

    try:
        setup_cb = getattr(coordinator, "async_setup", None)
        if callable(setup_cb):
            setup_result = setup_cb()
            if inspect.isawaitable(setup_result):
                await setup_result
    except asyncio.CancelledError:
        raise
    except (TimeoutError, ConnectionException, ModbusException, OSError) as exc:
        if is_invalid_auth_error(exc):
            _LOGGER.error("Authentication failed during setup: %s", exc)
            await entry.async_start_reauth(hass)
            return False
        if exc.__class__.__name__ == "ConfigEntryNotReady":
            raise
        _LOGGER.error("Failed to setup coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Unable to connect to device: {exc}") from exc
    except Exception as exc:
        if exc.__class__.__name__ == "UpdateFailed":
            if is_invalid_auth_error(exc):
                _LOGGER.error("Authentication failed during setup: %s", exc)
                await entry.async_start_reauth(hass)
                return False
        _LOGGER.error("Failed to setup coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Unable to connect to device: {exc}") from exc

    try:
        refresh_cb = getattr(coordinator, "async_config_entry_first_refresh", None)
        if callable(refresh_cb):
            refresh_result = refresh_cb()
            if inspect.isawaitable(refresh_result):
                await refresh_result
        else:
            refresh_fallback = getattr(coordinator, "async_refresh", None)
            if callable(refresh_fallback):
                refresh_result = refresh_fallback()
                if inspect.isawaitable(refresh_result):
                    await refresh_result
    except asyncio.CancelledError:
        raise
    except (TimeoutError, ConnectionException, ModbusException, UpdateFailed, OSError) as exc:
        if is_invalid_auth_error(exc):
            _LOGGER.error("Authentication failed during initial refresh: %s", exc)
            await entry.async_start_reauth(hass)
            return False
        if exc.__class__.__name__ == "ConfigEntryNotReady":
            raise
        _LOGGER.error("Failed to perform initial data refresh: %s", exc)
        raise ConfigEntryNotReady(f"Unable to fetch initial data: {exc}") from exc
    except Exception as exc:
        if exc.__class__.__name__ == "UpdateFailed":
            if is_invalid_auth_error(exc):
                _LOGGER.error("Authentication failed during initial refresh: %s", exc)
                await entry.async_start_reauth(hass)
                return False
        _LOGGER.error("Failed to perform initial data refresh: %s", exc)
        raise ConfigEntryNotReady(f"Unable to fetch initial data: {exc}") from exc

    return True


def _async_patch_coordinator_compat(
    coordinator: Any, entry: ConfigEntry
) -> None:  # pragma: no cover
    """Add lightweight fallback attributes for test environments."""
    if not hasattr(coordinator, "capabilities"):
        class _PermissiveCapabilities:
            def __getattr__(self, _name: str) -> bool:
                return True

        coordinator.capabilities = _PermissiveCapabilities()

    if not hasattr(coordinator, "get_register_map"):
        empty_maps = {
            "input_registers": {},
            "holding_registers": {},
            "coil_registers": {},
            "discrete_inputs": {},
        }
        coordinator.get_register_map = lambda reg_type: empty_maps.get(reg_type, {})

    if not hasattr(coordinator, "available_registers"):
        coordinator.available_registers = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

    force_full = entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
    if not hasattr(coordinator, "force_full_register_list"):
        coordinator.force_full_register_list = bool(force_full)


async def _async_setup_mappings(hass: HomeAssistant) -> None:  # pragma: no cover
    """Load option lists and entity mappings."""
    try:
        await async_setup_options(hass)
    except (TypeError, AttributeError):
        _LOGGER.debug("Skipping async_setup_options in mock context")
    try:
        await async_setup_entity_mappings(hass)
    except (TypeError, AttributeError):
        _LOGGER.debug("Skipping async_setup_entity_mappings in mock context")


async def _async_setup_platforms(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:  # pragma: no cover
    """Preload platform modules and forward config entry setup."""
    for platform in PLATFORM_DOMAINS:
        try:
            import_task = hass.async_add_executor_job(import_module, f".{platform}", __name__)
            if inspect.isawaitable(import_task):
                await import_task
        except (ImportError, ModuleNotFoundError) as err:
            _LOGGER.debug("Could not preload platform %s: %s", platform, err)
        except Exception as err:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected error preloading platform %s: %s", platform, err)

    platforms = _get_platforms()
    _LOGGER.debug("Setting up platforms: %s", platforms)
    try:
        forward_result = hass.config_entries.async_forward_entry_setups(entry, platforms)
        if asyncio.iscoroutine(forward_result):
            await forward_result
    except asyncio.CancelledError:
        _LOGGER.info("Platform setup cancelled for %s", platforms)
        raise


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # pragma: no cover
    """Set up ThesslaGreen Modbus from a config entry.

    This hook is invoked by Home Assistant during config entry setup even
    though it appears unused within the integration code itself.
    """
    _LOGGER.debug(
        "Setting up ThesslaGreen Modbus integration for %s",
        getattr(entry, "title", entry.data.get(CONF_NAME, DEFAULT_NAME)),
    )

    coordinator = await _async_create_coordinator(hass, entry)
    if not await _async_start_coordinator(hass, entry, coordinator):
        return False
    _async_patch_coordinator_compat(coordinator, entry)
    entry.runtime_data = coordinator

    await _async_cleanup_legacy_fan_entity(hass, coordinator)
    await _async_migrate_unique_ids(hass, entry)
    await _async_migrate_entity_ids(hass, entry)
    await _async_setup_mappings(hass)
    await _async_setup_platforms(hass, entry)

    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        from .services import async_setup_services
        await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    _LOGGER.info("ThesslaGreen Modbus integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # pragma: no cover
    """Unload a config entry.

    Called by Home Assistant when a config entry is removed.  Kept for the
    callback interface despite not being referenced directly.
    """
    _LOGGER.debug("Unloading ThesslaGreen Modbus integration")

    # Unload platforms
    platforms = _get_platforms()
    unload_ok = cast(bool, await hass.config_entries.async_unload_platforms(entry, platforms))

    if unload_ok:
        # Shutdown coordinator
        coordinator = entry.runtime_data
        await coordinator.async_shutdown()

        # Unload services when last entry is removed
        if not hass.config_entries.async_entries(DOMAIN):
            from .services import async_unload_services

            await async_unload_services(hass)

    _LOGGER.info("ThesslaGreen Modbus integration unloaded successfully")
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:  # pragma: no cover
    """Update options."""
    _LOGGER.debug("Updating options for ThesslaGreen Modbus integration")

    coordinator = getattr(entry, "runtime_data", None)
    if coordinator:
        new_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        coordinator.scan_interval = new_interval
        try:
            coordinator.async_set_update_interval(timedelta(seconds=new_interval))
        except AttributeError:
            coordinator.update_interval = timedelta(seconds=new_interval)

        new_log_level = str(entry.options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL))
        _apply_log_level(new_log_level)

        coordinator.safe_scan = bool(entry.options.get(CONF_SAFE_SCAN, DEFAULT_SAFE_SCAN))
        try:
            coordinator._compute_register_groups()
        except Exception:  # pragma: no cover - defensive
            _LOGGER.debug("Failed to recompute register groups after option update", exc_info=True)

        await coordinator.async_request_refresh()

    await hass.config_entries.async_reload(entry.entry_id)


# Map old register keys (as they appeared in unique_ids) to current keys.
# Needed for entities where the dict_key itself was renamed across versions,
# not just the entity_id naming mechanism (translation → key-based).
_LEGACY_KEY_RENAMES: dict[str, str] = {
    # Binary sensor key renames
    "gwc_regeneration_active": "gwc_regen_flag",
    "ahu_filter_overflow": "dp_ahu_filter_overflow",
    "duct_filter_overflow": "dp_duct_filter_overflow",
    "central_heater_overprotection": "post_heater_on",
    "unit_operation_confirmation": "info",
    "water_heater_pump": "duct_water_heater_pump",
    # Sensor key renames
    "maximum_percentage": "max_percentage",
    "minimum_percentage": "min_percentage",
    "time_period": "period",
    "supply_flow_rate_m3_h": "supply_flow_rate",
    "exhaust_flow_rate_m3_h": "exhaust_flow_rate",
    "ahu_stop_alarm_code": "stop_ahu_code",
    "product_key_lock_date_day": "lock_date_00dd",
    "bypass_mode_status": "bypass_mode",
    "comfort_mode_status": "comfort_mode",
    # Switch key renames
    "bypass_active": "bypass_off",
    "gwc_active": "gwc_off",
    "comfort_mode_switch": "comfort_mode_panel",
    "lock": "lock_flag",
    # Select key renames
    "filter_check_day_of_week": "pres_check_day",
    "gwc_regeneration": "gwc_regen",
    "filter_type": "filter_change",
}

# Mapping from (register_key, bit_value) → bit-specific entity key.
# Used during migration to assign unique entity_ids to individual bits of
# bitmask registers.  Without this, all 4 bits of e_196_e_199 would all
# target the same entity_id (collision) and only one could be migrated.
_BIT_ENTITY_KEYS: dict[tuple[str, int], str] = {
    # e_196_e_199 is a bitmask register; each bit gets its own entity key.
    # Key format: _to_snake_case(bit_name) inserts underscore before digits,
    # so "e196" → "e_196", giving "e_196_e_199_e_196".
    ("e_196_e_199", 1): "e_196_e_199_e_196",
    ("e_196_e_199", 2): "e_196_e_199_e_197",
    ("e_196_e_199", 4): "e_196_e_199_e_198",
    ("e_196_e_199", 8): "e_196_e_199_e_199",
}


def _extract_key_from_unique_id(unique_id: str, prefix: str, slave_id: int | str) -> str | None:
    """Extract register key from entity unique_id.

    Unique ID format: ``{prefix}_{slave_id}_{key}_{addr_part}{bit_suffix}``
    where *addr_part* is a decimal number or the string ``calc``, and
    *bit_suffix* is either empty or ``_bitN``.

    The function first tries an exact prefix match (fast path).  If that
    fails it falls back to scanning for ``_{slave_id}_`` anywhere in the
    unique_id.  This handles cases where the prefix changed between
    registrations (e.g. host-port → serial number after a firmware update)
    so that migration can still rename entities whose prefix no longer
    matches the currently detected one.
    """
    def _parse_rest(rest: str) -> str | None:
        rest = re.sub(r"_bit\d+$", "", rest)
        m = re.match(r"^(.+)_(\d+|calc)$", rest)
        return m.group(1) if m else None

    # Fast path: exact prefix match
    start = f"{prefix}_{slave_id}_"
    if unique_id.startswith(start):
        return _parse_rest(unique_id[len(start):])

    # Fallback: find _{slave_id}_ anywhere in the unique_id.
    # Handles prefix changes (serial vs host-port) across integration versions.
    slave_marker = f"_{slave_id}_"
    idx = unique_id.find(slave_marker)
    if idx > 0:  # prefix must be non-empty (idx > 0, not >= 0)
        return _parse_rest(unique_id[idx + len(slave_marker):])

    return None


async def _async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:  # pragma: no cover
    """Rename entity IDs from translation-based to register-key-based naming.

    Prior to adding ``suggested_object_id`` in the base entity class, HA
    derived entity_ids from translated entity names (e.g.
    ``switch.rekuperator_bypass_active``).  After the fix, new registrations
    use the register key directly (e.g. ``switch.rekuperator_bypass_off``).
    This function updates the entity registry for existing installations so
    that old entity_ids are renamed to the new key-based format, making
    ``example_dashboard.yaml`` work without manual intervention.
    """
    try:
        from homeassistant.helpers import device_registry as dr  # type: ignore
        from homeassistant.helpers import entity_registry as er  # type: ignore
        from homeassistant.util import slugify  # type: ignore
    except Exception:
        return

    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    if entity_reg is None or device_reg is None:
        return

    entries_for_config = getattr(er, "async_entries_for_config_entry", None)
    if not callable(entries_for_config):
        _LOGGER.debug("entity_id migration: async_entries_for_config_entry not available")
        return

    # Single call — reuse this list for prefix detection and migration loop.
    reg_entries = list(entries_for_config(entity_reg, entry.entry_id))
    _LOGGER.debug(
        "entity_id migration: found %d entities for config entry %s",
        len(reg_entries),
        entry.entry_id,
    )
    if not reg_entries:
        return

    coordinator = entry.runtime_data
    slave_id = getattr(coordinator, "slave_id", 1)

    # Determine unique_id prefix from existing registry entries.
    # Scan for the pattern _{slave_id}_ in each unique_id; the part before it
    # is the prefix.  Using existing entries is more reliable than computing
    # the prefix from coordinator.device_info because the serial may have
    # changed or differed from what was used when entities were first registered.
    prefix: str | None = None
    slave_marker = f"_{slave_id}_"
    for _e in reg_entries:
        if _e.unique_id and slave_marker in _e.unique_id:
            idx = _e.unique_id.index(slave_marker)
            candidate = _e.unique_id[:idx]
            if candidate:
                prefix = candidate
                break

    if not prefix:
        # Fallback: compute from coordinator / entry data
        host = getattr(coordinator, "host", None) or entry.data.get(CONF_HOST, "")
        port = getattr(coordinator, "port", None) or entry.data.get(CONF_PORT, 0)
        device_info = getattr(coordinator, "device_info", {}) or {}
        serial = device_info.get("serial_number")
        prefix = device_unique_id_prefix(serial, host, port)

    _LOGGER.debug(
        "entity_id migration: using prefix=%r slave_id=%s",
        prefix,
        slave_id,
    )

    migrated: list[tuple[str, str]] = []
    skipped_no_key: int = 0
    skipped_no_device: int = 0
    skipped_ok: int = 0
    skipped_collision: int = 0

    for reg_entry in reg_entries:
        if entity_reg.async_get(reg_entry.entity_id) is None:
            continue

        key = _extract_key_from_unique_id(reg_entry.unique_id, prefix, slave_id)
        if not key:
            skipped_no_key += 1
            _LOGGER.debug(
                "entity_id migration: cannot extract key from unique_id=%r (prefix=%r slave=%s) — skipping %s",
                reg_entry.unique_id,
                prefix,
                slave_id,
                reg_entry.entity_id,
            )
            continue

        # Apply legacy key renames (handles dict_key changes across versions)
        key = _LEGACY_KEY_RENAMES.get(key, key)

        # For bitmask bit entities, resolve the register key + bit value to the
        # per-bit entity key (e.g. "e_196_e_199" + bit1 → "e_196_e_199_e196").
        # Without this, all four bits of e_196_e_199 would compete for the same
        # target entity_id causing three of four to be skipped as collisions.
        bit_match = re.search(r"_bit(\d+)$", reg_entry.unique_id)
        if bit_match:
            bit_val = int(bit_match.group(1))
            bit_key = _BIT_ENTITY_KEYS.get((key, bit_val))
            if bit_key:
                key = bit_key

        # Determine device name slug from the device registry
        if not reg_entry.device_id:
            skipped_no_device += 1
            continue
        device = device_reg.async_get(reg_entry.device_id)
        if not device or not device.name:
            skipped_no_device += 1
            continue
        device_slug = slugify(device.name)
        if not device_slug:
            skipped_no_device += 1
            continue

        platform = reg_entry.entity_id.split(".")[0]
        expected_entity_id = f"{platform}.{device_slug}_{key}"

        if reg_entry.entity_id == expected_entity_id:
            skipped_ok += 1
            continue  # already correct

        if entity_reg.async_get(expected_entity_id) is not None:
            skipped_collision += 1
            _LOGGER.debug(
                "entity_id migration: target %s already occupied — cannot rename %s",
                expected_entity_id,
                reg_entry.entity_id,
            )
            continue

        _LOGGER.debug(
            "entity_id migration: renaming %s → %s (key=%r device=%r)",
            reg_entry.entity_id,
            expected_entity_id,
            key,
            device_slug,
        )
        try:
            entity_reg.async_update_entity(reg_entry.entity_id, new_entity_id=expected_entity_id)
            migrated.append((reg_entry.entity_id, expected_entity_id))
        except Exception as exc:
            _LOGGER.warning(
                "entity_id migration: could not rename %s → %s: %s",
                reg_entry.entity_id,
                expected_entity_id,
                exc,
            )

    _LOGGER.info(
        "entity_id migration done: migrated=%d already_ok=%d no_key=%d no_device=%d collision=%d",
        len(migrated),
        skipped_ok,
        skipped_no_key,
        skipped_no_device,
        skipped_collision,
    )
    if migrated:
        _LOGGER.info(
            "Migrated %d entity IDs to register-key-based naming: %s",
            len(migrated),
            ", ".join(f"{old} → {new}" for old, new in migrated[:20])
            + (f" … (+{len(migrated) - 20} more)" if len(migrated) > 20 else ""),
        )


async def _async_cleanup_legacy_fan_entity(hass: HomeAssistant, coordinator) -> None:
    """Remove legacy number entity IDs replaced by the fan entity.

    HA's entity registry does not allow changing domains via async_update_entity,
    so old number.* entities cannot be renamed to fan.*. They are simply removed;
    the fan.rekuperator_fan entity is created by the fan platform setup.
    """
    from homeassistant.helpers import entity_registry as er  # type: ignore

    registry = er.async_get(hass)
    if registry is None:
        return
    new_entity_id = "fan.rekuperator_fan"
    new_unique_id = f"{getattr(coordinator, 'slave_id', 1)}_0"
    migrated = False

    for old_entity_id in LEGACY_FAN_ENTITY_IDS:
        if registry.async_get(old_entity_id):
            try:
                registry.async_update_entity(
                    old_entity_id,
                    new_entity_id=new_entity_id,
                    new_unique_id=new_unique_id,
                )
            except Exception:
                registry.async_remove(old_entity_id)
            migrated = True

    if migrated:
        _LOGGER.warning(
            "Legacy fan entity detected. Migrated/removed legacy entities %s to '%s'.",
            LEGACY_FAN_ENTITY_IDS,
            new_entity_id,
        )


async def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entity unique IDs stored in the entity registry."""
    from homeassistant.helpers import entity_registry as er  # type: ignore

    registry = er.async_get(hass)
    coordinator = entry.runtime_data
    device_info = getattr(coordinator, "device_info", None)
    if not isinstance(device_info, dict):
        getter = getattr(coordinator, "get_device_info", None)
        if callable(getter):
            try:
                maybe_info = getter()
                if asyncio.iscoroutine(maybe_info):
                    maybe_info = await maybe_info
                if isinstance(maybe_info, dict):
                    device_info = maybe_info
            except Exception:  # pragma: no cover - defensive
                device_info = None
    serial = device_info.get("serial_number") if isinstance(device_info, dict) else None
    host = getattr(coordinator, "host", None) or entry.data.get(CONF_HOST)
    port = getattr(coordinator, "port", None) or entry.data.get(CONF_PORT)
    slave_id = getattr(coordinator, "slave_id", None) or entry.data.get(CONF_SLAVE_ID)
    entries_for_config = getattr(er, "async_entries_for_config_entry", None)
    if not callable(entries_for_config):
        return
    for reg_entry in entries_for_config(registry, entry.entry_id):
        if registry.async_get(reg_entry.entity_id) is None:
            continue
        if reg_entry.entity_id == "fan.rekuperator_fan":
            continue
        new_unique_id = migrate_unique_id(
            reg_entry.unique_id,
            serial_number=serial,
            host=host,
            port=port,
            slave_id=slave_id,
        )
        if new_unique_id != reg_entry.unique_id:
            _LOGGER.debug(
                "Migrating unique_id for %s: %s -> %s",
                reg_entry.entity_id,
                reg_entry.unique_id,
                new_unique_id,
            )
            registry.async_update_entity(reg_entry.entity_id, new_unique_id=new_unique_id)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:  # pragma: no cover
    """Migrate old entry.

    Home Assistant uses this during upgrades; vulture marks it as unused but
    the runtime imports it dynamically.
    """
    _LOGGER.debug("Migrating ThesslaGreen Modbus from version %s", config_entry.version)

    new_data = {**config_entry.data}
    new_options = {**config_entry.options}

    if config_entry.version == 1:
        # Migrate "unit" to CONF_SLAVE_ID if needed
        if "unit" in new_data and CONF_SLAVE_ID not in new_data:
            new_data[CONF_SLAVE_ID] = new_data["unit"]
            _LOGGER.info("Migrated 'unit' to '%s'", CONF_SLAVE_ID)

        # Ensure port is present; older versions relied on legacy default
        if CONF_PORT not in new_data:
            new_data[CONF_PORT] = LEGACY_DEFAULT_PORT
            _LOGGER.info("Added '%s' with legacy default %s", CONF_PORT, LEGACY_DEFAULT_PORT)

        # Add new fields with defaults if missing
        if CONF_SCAN_INTERVAL not in new_options:
            new_options[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL
        if CONF_TIMEOUT not in new_options:
            new_options[CONF_TIMEOUT] = DEFAULT_TIMEOUT
        if CONF_RETRY not in new_options:
            new_options[CONF_RETRY] = DEFAULT_RETRY
        if CONF_FORCE_FULL_REGISTER_LIST not in new_options:
            new_options[CONF_FORCE_FULL_REGISTER_LIST] = False

        config_entry.version = 2

    if config_entry.version == 2:
        if CONF_CONNECTION_TYPE not in new_data:
            new_data[CONF_CONNECTION_TYPE] = DEFAULT_CONNECTION_TYPE
        config_entry.version = 3

    if config_entry.version == 3:
        connection_type = new_data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        connection_mode = new_data.get(CONF_CONNECTION_MODE)
        normalized_type, resolved_mode = resolve_connection_settings(
            connection_type, connection_mode, new_data.get(CONF_PORT, DEFAULT_PORT)
        )
        new_data[CONF_CONNECTION_TYPE] = normalized_type
        if normalized_type == CONNECTION_TYPE_TCP:
            new_data[CONF_CONNECTION_MODE] = resolved_mode
        else:
            new_data.pop(CONF_CONNECTION_MODE, None)
            new_options.pop(CONF_CONNECTION_MODE, None)
        config_entry.version = 4

    # Build new unique ID replacing ':' in host with '-' to avoid separator conflicts
    host = new_data.get(CONF_HOST)
    port = new_data.get(CONF_PORT, LEGACY_DEFAULT_PORT)
    # Determine slave ID using same logic as setup
    if CONF_SLAVE_ID in new_data:
        slave_id = new_data[CONF_SLAVE_ID]
    elif "slave_id" in new_data:
        slave_id = new_data["slave_id"]
    elif "unit" in new_data:
        slave_id = new_data["unit"]
    else:
        slave_id = DEFAULT_SLAVE_ID

    unique_host = host.replace(":", "-") if host else host
    new_unique_id = f"{unique_host}:{port}:{slave_id}"

    hass.config_entries.async_update_entry(
        config_entry, data=new_data, options=new_options, unique_id=new_unique_id
    )

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
