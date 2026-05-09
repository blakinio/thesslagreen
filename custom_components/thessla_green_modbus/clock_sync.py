"""Device clock synchronisation helpers for ThesslaGreen Modbus."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_SYNC_DEVICE_CLOCK_ENABLED,
    CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
    CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    CONF_SYNC_DEVICE_CLOCK_ON_START,
    DEFAULT_SYNC_DEVICE_CLOCK_ENABLED,
    DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
    DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    DEFAULT_SYNC_DEVICE_CLOCK_ON_START,
)
from .modbus_exceptions import ConnectionException, ModbusException
from .utils import encode_datetime_to_rtc_registers

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# RTC register block starts at holding register address 0.
_RTC_START_ADDRESS = 0

# Names used for coordinator data read-back after write.
_RTC_REGISTER_NAMES = ("date_time", "date_time_ddtt", "date_time_ggmm", "date_time_sscc")


def clock_sync_options(options: dict[str, Any]) -> dict[str, Any]:
    """Extract clock sync options from config entry options with defaults."""
    return {
        CONF_SYNC_DEVICE_CLOCK_ENABLED: bool(
            options.get(CONF_SYNC_DEVICE_CLOCK_ENABLED, DEFAULT_SYNC_DEVICE_CLOCK_ENABLED)
        ),
        CONF_SYNC_DEVICE_CLOCK_ON_START: bool(
            options.get(CONF_SYNC_DEVICE_CLOCK_ON_START, DEFAULT_SYNC_DEVICE_CLOCK_ON_START)
        ),
        CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS: int(
            options.get(
                CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
                DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
            )
        ),
        CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS: int(
            options.get(
                CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
                DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
            )
        ),
    }


def _parse_device_clock(device_clock: str | None) -> datetime | None:
    """Parse ISO-format device clock string returned by coordinator data."""
    if not device_clock:
        return None
    try:
        return datetime.fromisoformat(device_clock)
    except (ValueError, TypeError):
        return None


def _validate_drift(
    written_at: datetime,
    device_clock: str | None,
    max_drift_seconds: int,
    *,
    raise_on_failure: bool,
) -> bool:
    """Return True when device clock drift is within the allowed threshold.

    ``written_at`` is the local datetime that was written to the device.
    ``device_clock`` is the ISO string read back from coordinator data.
    """
    parsed = _parse_device_clock(device_clock)
    if parsed is None:
        if raise_on_failure:
            raise HomeAssistantError(
                "Could not read device clock back after synchronisation — validation skipped"
            )
        _LOGGER.warning("Device clock unavailable after write; drift cannot be validated")
        return False

    drift = abs((parsed - written_at.replace(tzinfo=None)).total_seconds())
    if drift > max_drift_seconds:
        msg = (
            f"Device clock drift {drift:.0f}s exceeds threshold {max_drift_seconds}s "
            f"after synchronisation (device reports {device_clock})"
        )
        if raise_on_failure:
            raise HomeAssistantError(msg)
        _LOGGER.error(msg)
        return False

    _LOGGER.info(
        "Device clock synchronised successfully (drift %.0fs, threshold %ds)",
        drift,
        max_drift_seconds,
    )
    return True


async def async_sync_device_clock(
    coordinator: ThesslaGreenModbusCoordinator,
    now: datetime,
    max_drift_seconds: int,
    *,
    raise_on_failure: bool = False,
    entity_id: str = "",
) -> bool:
    """Write current local time to all four RTC registers, then validate drift.

    Returns True on success.  On failure logs an error and optionally raises
    HomeAssistantError (when ``raise_on_failure`` is True).
    """
    if not getattr(coordinator, "last_update_success", False):
        msg = "Coordinator is offline; skipping device clock synchronisation"
        _LOGGER.warning(msg)
        if raise_on_failure:
            raise HomeAssistantError(msg)
        return False

    values = encode_datetime_to_rtc_registers(now)
    label = f" for {entity_id}" if entity_id else ""

    try:
        success = await coordinator.async_write_registers(
            start_address=_RTC_START_ADDRESS,
            values=values,
            refresh=True,
        )
    except (ModbusException, ConnectionException) as err:
        msg = f"Failed to write RTC registers{label}: {err}"
        _LOGGER.error(msg)
        if raise_on_failure:
            raise HomeAssistantError(msg) from err
        return False

    if not success:
        msg = f"Write of RTC registers returned failure{label}"
        _LOGGER.error(msg)
        if raise_on_failure:
            raise HomeAssistantError(msg)
        return False

    _LOGGER.debug(
        "Wrote RTC payload %s (start_address=%d)%s",
        values,
        _RTC_START_ADDRESS,
        label,
    )

    device_clock = (getattr(coordinator, "data", None) or {}).get("device_clock")
    return _validate_drift(
        now,
        device_clock,
        max_drift_seconds,
        raise_on_failure=raise_on_failure,
    )


def should_auto_sync(options: dict[str, Any]) -> bool:
    """Return True when automatic clock sync is enabled in options."""
    return bool(options.get(CONF_SYNC_DEVICE_CLOCK_ENABLED, DEFAULT_SYNC_DEVICE_CLOCK_ENABLED))


def should_sync_on_start(options: dict[str, Any]) -> bool:
    """Return True when clock sync on coordinator start is enabled."""
    return bool(options.get(CONF_SYNC_DEVICE_CLOCK_ON_START, DEFAULT_SYNC_DEVICE_CLOCK_ON_START))


def sync_interval(options: dict[str, Any]) -> timedelta:
    """Return the configured clock sync interval as a timedelta."""
    hours = int(
        options.get(CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS, DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS)
    )
    return timedelta(hours=max(1, min(168, hours)))
