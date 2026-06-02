"""Device clock synchronization helpers for ThesslaGreen Modbus."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# RTC registers start address (FC03 holding, address 0)
RTC_START_ADDRESS = 0
# Number of RTC registers (date_time, date_time_ddtt, date_time_ggmm, date_time_sscc)
RTC_REGISTER_COUNT = 4
# Read-back tolerance: max seconds between write time and read-back time
RTC_READBACK_TOLERANCE_SECONDS = 5


def bcd_encode(value: int) -> int:
    """Encode integer 0-99 to packed BCD byte."""
    return ((value // 10) << 4) | (value % 10)


def bcd_decode(byte: int) -> int:
    """Decode packed BCD byte to integer."""
    return ((byte >> 4) & 0xF) * 10 + (byte & 0xF)


def encode_rtc_registers(dt: datetime) -> list[int]:
    """Encode a datetime into the 4 RTC holding-register values.

    Register layout (FC03, addresses 0-3):
      addr 0 (date_time):      high=BCD(year%100), low=BCD(month)
      addr 1 (date_time_ddtt): high=BCD(day),      low=BCD(weekday 0=Mon)
      addr 2 (date_time_ggmm): high=BCD(hour),     low=BCD(minute)
      addr 3 (date_time_sscc): high=BCD(second),   low=0x00
    """
    reg_yymm = (bcd_encode(dt.year % 100) << 8) | bcd_encode(dt.month)
    reg_ddtt = (bcd_encode(dt.day) << 8) | bcd_encode(dt.weekday())
    reg_ggmm = (bcd_encode(dt.hour) << 8) | bcd_encode(dt.minute)
    reg_sscc = (bcd_encode(dt.second) << 8) | 0x00
    return [reg_yymm, reg_ddtt, reg_ggmm, reg_sscc]


def decode_rtc_registers(
    raw_yymm: int,
    raw_ddtt: int,
    raw_ggmm: int,
    raw_sscc: int,
) -> str | None:
    """Decode 4 RTC register values to ISO-8601 string or None if invalid.

    Mirrors the decoder in core/capabilities_mixin.py for round-trip testing.
    """
    yy = bcd_decode((raw_yymm >> 8) & 0xFF)
    mm = bcd_decode(raw_yymm & 0xFF)
    dd = bcd_decode((raw_ddtt >> 8) & 0xFF)
    hh = bcd_decode((raw_ggmm >> 8) & 0xFF)
    mi = bcd_decode(raw_ggmm & 0xFF)
    ss = bcd_decode((raw_sscc >> 8) & 0xFF)
    year = 2000 + yy
    if 1 <= mm <= 12 and 1 <= dd <= 31 and hh <= 23 and mi <= 59 and ss <= 59:
        return f"{year:04d}-{mm:02d}-{dd:02d}T{hh:02d}:{mi:02d}:{ss:02d}"
    return None


def _drift_seconds(now: datetime, device_clock_str: str) -> float | None:
    """Return absolute drift in seconds between HA time and device clock string.

    Returns None when the device clock string cannot be parsed.
    """
    try:
        device_dt = datetime.fromisoformat(device_clock_str)
        now_naive = now.replace(tzinfo=None) if now.tzinfo is not None else now
        return abs((now_naive - device_dt).total_seconds())
    except (ValueError, TypeError):
        return None


async def async_perform_clock_sync(
    coordinator: ThesslaGreenModbusCoordinator,
    *,
    force: bool = False,
    max_drift_seconds: int = 300,
    dt_now_fn: Any = None,
    logger: logging.Logger | None = None,
) -> bool:
    """Synchronise device RTC to HA local time.

    Returns True when sync succeeded or was skipped (drift below threshold).
    Returns False when the write failed.
    Raises HomeAssistantError when read-back validation fails.
    """
    from homeassistant.exceptions import HomeAssistantError
    from homeassistant.util import dt as dt_util

    log = logger or _LOGGER
    now_fn = dt_now_fn if dt_now_fn is not None else dt_util.now
    now = now_fn()

    if not force:
        device_clock_str = (coordinator.data or {}).get("device_clock")
        if device_clock_str:
            drift = _drift_seconds(now, device_clock_str)
            if drift is not None and drift <= max_drift_seconds:
                log.debug(
                    "Clock drift %.1fs is within threshold (%ds), skipping sync",
                    drift,
                    max_drift_seconds,
                )
                return True

    payload = encode_rtc_registers(now)
    log.debug("Writing RTC registers: %s (for %s)", payload, now.strftime("%Y-%m-%d %H:%M:%S"))

    # Write registers and immediately read them back under one lock so that no
    # concurrent coordinator scan or update can interleave between the write and
    # the read-back (which would cause Modbus TCP transaction-ID mismatches).
    try:
        write_ok, readback_regs = await coordinator.async_write_and_read_holding_registers(
            start_address=RTC_START_ADDRESS,
            values=payload,
            readback_count=RTC_REGISTER_COUNT,
        )
    except Exception:
        log.exception("Exception while writing RTC registers")
        return False

    if not write_ok:
        log.error(
            "Failed to write RTC clock registers for coordinator at %s",
            coordinator.device_client.config.host
            if hasattr(coordinator, "device_client")
            else "unknown",
        )
        return False

    log.info("Wrote RTC clock %s to device", now.strftime("%Y-%m-%d %H:%M:%S"))

    # Read-back validation using the locked register read (avoids stale coordinator.data).
    if readback_regs is None:
        log.warning("Device clock unavailable after RTC write; skipping validation")
        return True

    readback_str = decode_rtc_registers(*readback_regs)
    if readback_str is None:
        raise HomeAssistantError("RTC read-back validation failed: could not decode registers")

    drift_after = _drift_seconds(now, readback_str)
    if drift_after is None:
        raise HomeAssistantError(
            f"RTC read-back validation failed: could not parse '{readback_str}'"
        )
    if drift_after > RTC_READBACK_TOLERANCE_SECONDS:
        raise HomeAssistantError(
            f"RTC read-back validation failed: wrote {now.strftime('%H:%M:%S')}, "
            f"read back '{readback_str}' (drift {drift_after:.1f}s)"
        )

    log.info("RTC sync validated: read-back within %.1fs of written time", drift_after)
    return True


class ClockSyncManager:
    """Manages periodic and on-start device clock synchronization.

    Attaches to a coordinator as a data-change listener.
    Automatic sync is disabled by default and only runs when
    sync_device_clock_enabled option is True.
    """

    def __init__(
        self,
        hass: Any,
        coordinator: ThesslaGreenModbusCoordinator,
        entry: Any,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._entry = entry
        self._last_sync: datetime | None = None
        self._on_start_done = False
        self._sync_in_progress = False

    def attach(self) -> None:
        """Register as a coordinator listener."""
        self._coordinator.async_add_listener(self._on_update)

    def _options(self) -> dict[str, Any]:
        opts = getattr(self._entry, "options", {}) or {}
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

        return {
            "enabled": bool(
                opts.get(CONF_SYNC_DEVICE_CLOCK_ENABLED, DEFAULT_SYNC_DEVICE_CLOCK_ENABLED)
            ),
            "on_start": bool(
                opts.get(CONF_SYNC_DEVICE_CLOCK_ON_START, DEFAULT_SYNC_DEVICE_CLOCK_ON_START)
            ),
            "interval_hours": int(
                opts.get(
                    CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS, DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS
                )
            ),
            "max_drift": int(
                opts.get(
                    CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
                    DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
                )
            ),
        }

    def _on_update(self) -> None:
        """Called by coordinator after each successful data update."""
        opts = self._options()
        if not opts["enabled"]:
            return
        if self._sync_in_progress:
            return

        data = self._coordinator.data or {}
        if not data.get("device_clock"):
            return

        should_sync = False

        if opts["on_start"] and not self._on_start_done:
            self._on_start_done = True
            should_sync = True
        elif self._last_sync is None:
            should_sync = True
        else:
            from homeassistant.util import dt as dt_util

            elapsed = (
                dt_util.now().replace(tzinfo=None) - self._last_sync.replace(tzinfo=None)
            ).total_seconds()
            if elapsed >= opts["interval_hours"] * 3600:
                should_sync = True

        if should_sync:
            self._hass.async_create_task(self._do_sync(opts["max_drift"]))

    async def _do_sync(self, max_drift_seconds: int) -> None:
        """Run clock sync as a background task."""
        if self._sync_in_progress:
            return
        self._sync_in_progress = True
        try:
            ok = await async_perform_clock_sync(
                self._coordinator,
                force=False,
                max_drift_seconds=max_drift_seconds,
            )
            if ok:
                from homeassistant.util import dt as dt_util

                self._last_sync = dt_util.now().replace(tzinfo=None)
        except Exception:
            _LOGGER.exception("Automatic clock sync failed")
        finally:
            self._sync_in_progress = False
