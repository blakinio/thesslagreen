"""Fan platform for the ThesslaGreen Modbus integration.

The fan entity is only created when the required Modbus registers are
available on the device.
"""

from __future__ import annotations

import asyncio
import logging
from time import monotonic
from typing import Any, ClassVar

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymodbus.exceptions import ConnectionException, ModbusException

from .const import FAN_DEFAULT_PERCENT, FAN_SPEED_LEVELS
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .registers.maps import holding_registers

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Transient optimistic display window: after a successful fan airflow write the
# GUI shows the requested percentage for at most this many seconds, until the
# supply_percentage / exhaust_percentage status registers catch up on the next
# full poll.  Fan writes keep targeted_readback=False (the setpoint registers
# are not 1:1 with the displayed status registers), so without this the GUI
# would lag one poll interval behind the physical device.
_PENDING_PERCENTAGE_TTL = 10.0
# Once the confirmed supply/exhaust status registers land within this many
# percentage points of the requested value, the optimistic value is dropped in
# favour of the real device reading.
_PENDING_PERCENTAGE_MATCH_TOLERANCE = 2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen fan from config entry.

    This is a Home Assistant callback invoked during platform setup.
    """
    coordinator: ThesslaGreenModbusCoordinator = entry.runtime_data

    # Check if fan control is available based on registers discovered by
    # ThesslaGreenDeviceScanner.scan_device()
    fan_registers = [
        "air_flow_rate_manual",
        "air_flow_rate_temporary_2",
        "supply_percentage",
        "exhaust_percentage",
    ]

    has_fan_registers = False
    for register in fan_registers:
        if register in coordinator.device_client.available_registers.get(
            "holding_registers", set()
        ) or register in coordinator.device_client.available_registers.get(
            "input_registers", set()
        ):
            has_fan_registers = True
            break

    if has_fan_registers:
        entities = [ThesslaGreenFan(coordinator)]
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning("Cancelled while adding fan entity, retrying without initial state")
            async_add_entities(entities, False)
            return
        _LOGGER.debug("Added fan entity")
    else:
        _LOGGER.debug("No fan control registers available - skipping fan entity")


class ThesslaGreenFan(ThesslaGreenEntity, FanEntity):
    """ThesslaGreen fan entity.

    ``_attr_*`` attributes and entity methods implement the Home Assistant
    ``FanEntity`` API and may appear unused to static analysis.
    """

    _MODE_MAP: ClassVar[dict[int, str]] = {0: "auto", 1: "manual", 2: "temporary"}

    def __init__(self, coordinator: ThesslaGreenModbusCoordinator) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, "ventilation", 0)

        # Entity configuration
        self._attr_translation_key = "thessla_green_fan"

        # Fan configuration
        self._attr_supported_features = FanEntityFeature.SET_SPEED

        # Speed range (0-150% as per ThesslaGreen specs)
        self._attr_speed_count = FAN_SPEED_LEVELS

        # Transient optimistic percentage shown immediately after a successful
        # airflow write, before the supply_percentage / exhaust_percentage
        # status registers are refreshed by the next full poll.
        self._pending_percentage: int | None = None
        self._pending_percentage_ts: float = 0.0

        _LOGGER.debug("Initialized fan entity")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Drop the optimistic pending percentage once real status catches up.

        The coordinator notifies this entity on every poll (and on targeted
        read-backs of other registers).  As soon as the confirmed
        supply/exhaust status registers reflect the requested speed the
        optimistic override is no longer needed, so it is cleared before the
        normal state write.
        """
        self._clear_pending_if_confirmed()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if the fan entity is available."""
        return self._coordinator_connected() and self._has_value("on_off_panel_mode")

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on."""
        # Check if system is powered on
        if (
            "on_off_panel_mode" in self.coordinator.data
            and not self.coordinator.data["on_off_panel_mode"]
        ):
            return False

        # Check current flow rate
        flow_rate = self._effective_flow_rate()
        if flow_rate is None:
            return None

        return flow_rate > 0

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage, clamped to 0–100 per HA spec.

        The physical device may report flow rates above 100 % (e.g. 109 %
        when max_percentage = 109).  HA FanEntity.percentage must stay in
        0–100; the raw device value is preserved in extra_state_attributes
        as ``supply_percentage``.

        Immediately after a successful airflow write a short-lived optimistic
        value is used (see ``_effective_flow_rate``) so the GUI reflects the
        requested speed without waiting a full poll for the status registers.
        """
        flow_rate = self._effective_flow_rate()
        if flow_rate is None:
            return None

        _min_pct, max_pct = self._percentage_limits()
        raw_clamped = max(0, min(max_pct, int(flow_rate)))
        return min(100, raw_clamped)

    def _effective_flow_rate(self) -> float | None:
        """Return the optimistic pending percentage if fresh, else real status.

        The pending value is only honoured while it is still within its TTL and
        has not been superseded by a confirmed status reading; otherwise the
        normal status/setpoint logic in ``_get_current_flow_rate`` applies.
        """
        pending = self._pending_percentage_value()
        if pending is not None:
            return float(pending)
        return self._get_current_flow_rate()

    def _pending_percentage_value(self) -> int | None:
        """Return the transient pending percentage while it is still fresh.

        The value is set optimistically right after a successful airflow write
        so the GUI reflects the requested speed immediately.  It self-expires
        after ``_PENDING_PERCENTAGE_TTL`` seconds; reading it after expiry also
        clears it so later polls fall back to confirmed device state.
        """
        if self._pending_percentage is None:
            return None
        if monotonic() - self._pending_percentage_ts > _PENDING_PERCENTAGE_TTL:
            self._pending_percentage = None
            return None
        return self._pending_percentage

    def _confirmed_status_flow_rate(self) -> float | None:
        """Return the device-reported percentage from status registers only.

        Unlike ``_get_current_flow_rate`` this never falls back to setpoint
        registers, so the optimistic pending value is only cleared once the
        actual supply/exhaust status registers reflect the requested speed
        (setpoint registers update on the very next poll and would otherwise
        clear the override prematurely, defeating its purpose).
        """
        data = self.coordinator.data
        for register in ("supply_percentage", "exhaust_percentage"):
            value = data.get(register)
            if value is not None and isinstance(value, int | float):
                return float(value)
        return None

    def _clear_pending_if_confirmed(self) -> None:
        """Clear the optimistic pending percentage once real status matches it."""
        if self._pending_percentage is None:
            return
        confirmed = self._confirmed_status_flow_rate()
        if (
            confirmed is not None
            and abs(confirmed - self._pending_percentage) <= _PENDING_PERCENTAGE_MATCH_TOLERANCE
        ):
            self._pending_percentage = None

    def _set_pending_percentage(self, percentage: int) -> None:
        """Record an optimistic percentage and push it to the GUI immediately.

        Only called after a confirmed-successful airflow write.  ``percentage``
        is the raw device value that was written (before the HA 0–100 clamp),
        matching the units of supply_percentage / exhaust_percentage so the
        confirmation comparison in ``_clear_pending_if_confirmed`` is valid.
        """
        self._pending_percentage = percentage
        self._pending_percentage_ts = monotonic()
        # ``hass`` is None in unit tests (entity not added to a platform); the
        # optimistic state is still stored and returned by ``percentage``.
        if self.hass is not None:
            self.async_write_ha_state()

    def _get_current_flow_rate(self) -> float | None:
        """Get current percentage-based flow rate from available registers.

        Only percentage-like registers are used; m³/h airflow registers
        (supply_air_flow, supply_flow_rate, etc.) are intentionally excluded
        because treating them as a percentage would clamp 268 m³/h → 100 %.
        """
        data = self.coordinator.data

        # Device-reported percentage sensors take priority.
        for register in ("supply_percentage", "exhaust_percentage"):
            value = data.get(register)
            if value is not None and isinstance(value, int | float):
                return float(value)

        # Mode-aware setpoint fallback.
        current_mode = self._get_current_mode()
        if current_mode == "temporary":
            candidates: tuple[str, ...] = ("air_flow_rate_temporary_2", "air_flow_rate_manual")
        else:
            candidates = ("air_flow_rate_manual",)

        for register in candidates:
            value = data.get(register)
            if value is not None and isinstance(value, int | float):
                return float(value)

        return None

    def _validate_percentage_write_path(self, percentage: int) -> None:
        """Ensure a positive fan-speed request has a writable device path."""
        if percentage <= 0:
            return
        current_mode = self._get_current_mode()
        if current_mode == "temporary":
            return
        register = (
            "air_flow_rate_manual"
            if current_mode == "manual" or not current_mode
            else "air_flow_rate_temporary_2"
        )
        if not self._is_writable_holding_register(register):
            raise ServiceValidationError(
                f"Fan speed control register {register} is unavailable on this device."
            )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan without reporting success for an unsupported speed path."""
        requested_percentage = FAN_DEFAULT_PERCENT if percentage is None else percentage
        if requested_percentage < 0:
            raise ServiceValidationError("Fan percentage must be greater than or equal to 0.")

        self._validate_percentage_write_path(requested_percentage)
        if self._is_writable_holding_register("on_off_panel_mode"):
            await self._write_register("on_off_panel_mode", 1, refresh=False)

        await self.async_set_percentage(requested_percentage)
        _LOGGER.debug("Turned on fan")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan and fail explicitly when no write path exists."""
        self._pending_percentage = None
        if self._is_writable_holding_register("on_off_panel_mode"):
            await self._write_register("on_off_panel_mode", 0)
            self.coordinator.data["on_off_panel_mode"] = 0
            _LOGGER.debug("Turned off fan")
            return

        current_mode = self._get_current_mode()
        register = (
            "air_flow_rate_manual"
            if current_mode == "manual" or not current_mode
            else "air_flow_rate_temporary_2"
        )
        if not self._is_writable_holding_register(register):
            raise ServiceValidationError(
                "Fan cannot be turned off because no writable power or airflow register is available."
            )
        await self._write_register(register, 0)
        self.coordinator.data[register] = 0
        _LOGGER.debug("Turned off fan")

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed and surface unsupported or failed writes to Home Assistant."""
        min_pct, max_pct = self._percentage_limits()
        if percentage < 0:
            raise ServiceValidationError("Fan percentage must be greater than or equal to 0.")

        requested = min(percentage, max_pct)
        if requested == 0:
            await self.async_turn_off()
            _LOGGER.debug("Set fan speed to 0%%")
            return

        actual_percentage = max(min_pct, requested)
        current_mode = self._get_current_mode()

        if current_mode == "manual" or not current_mode:
            if not self._is_writable_holding_register("air_flow_rate_manual"):
                raise ServiceValidationError(
                    "Manual fan speed control is unavailable on this device."
                )
            if self._is_writable_holding_register("mode"):
                await self._write_register("mode", 1, refresh=False)
            await self._write_register("air_flow_rate_manual", actual_percentage, refresh=False)
            self._set_pending_percentage(actual_percentage)
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Set fan speed to %d%%", actual_percentage)
            return

        if current_mode == "temporary":
            try:
                success = await self.coordinator.async_write_temporary_airflow(
                    actual_percentage, refresh=False
                )
            except (
                ModbusException,
                ConnectionException,
                TimeoutError,
                OSError,
                RuntimeError,
            ) as exc:
                raise HomeAssistantError("Failed to write temporary fan airflow.") from exc
            if not success:
                raise HomeAssistantError("Device did not confirm the temporary fan airflow write.")
            self._set_pending_percentage(actual_percentage)
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Set fan speed to %d%%", actual_percentage)
            return

        if not self._is_writable_holding_register("air_flow_rate_temporary_2"):
            raise ServiceValidationError(
                "Temporary fan speed control is unavailable on this device."
            )
        await self._write_register("air_flow_rate_temporary_2", actual_percentage, refresh=False)
        self._set_pending_percentage(actual_percentage)
        await self.coordinator.async_request_refresh()
        _LOGGER.debug("Set fan speed to %d%%", actual_percentage)

    def _get_current_mode(self) -> str | None:
        """Get current system mode."""
        if "mode" in self.coordinator.data:
            return self._MODE_MAP.get(self.coordinator.data["mode"])
        return None

    async def _write_register(
        self,
        register_name: str,
        value: Any,
        *,
        offset: int = 0,
        refresh: bool = True,
        include_offset: bool = False,
    ) -> None:
        """Write a discovered holding register and require device confirmation."""
        del include_offset
        if register_name not in holding_registers():
            raise ServiceValidationError(f"Register {register_name} is not writable.")

        holding_regs = self.coordinator.device_client.available_registers.get(
            "holding_registers", set()
        )
        if register_name not in holding_regs:
            raise ServiceValidationError(f"Register {register_name} is unavailable on this device.")

        kwargs: dict[str, Any] = {"refresh": False, "targeted_readback": False}
        if offset != 0:
            kwargs["offset"] = offset
        try:
            success = await self.coordinator.async_write_register(
                register_name, int(value), **kwargs
            )
        except (ModbusException, ConnectionException, TimeoutError, OSError, RuntimeError) as exc:
            raise HomeAssistantError(f"Failed to write fan register {register_name}.") from exc
        if not success:
            raise HomeAssistantError(
                f"Device did not confirm write to fan register {register_name}."
            )
        if refresh:
            await self.coordinator.async_request_refresh()

    def _is_writable_holding_register(self, register_name: str) -> bool:
        """Return True if a register is writable and available on this device."""
        return (
            register_name in holding_registers()
            and register_name
            in self.coordinator.device_client.available_registers.get("holding_registers", set())
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}

        # Add m³/h flow information (supply_air_flow preferred, supply_flow_rate as fallback).
        supply_flow = self.coordinator.data.get("supply_air_flow")
        if supply_flow is None:
            supply_flow = self.coordinator.data.get("supply_flow_rate")
        if supply_flow is not None:
            attributes["supply_flow"] = supply_flow

        exhaust_flow = self.coordinator.data.get("exhaust_air_flow")
        if exhaust_flow is None:
            exhaust_flow = self.coordinator.data.get("exhaust_flow_rate")
        if exhaust_flow is not None:
            attributes["exhaust_flow"] = exhaust_flow

        if "supply_percentage" in self.coordinator.data:
            attributes["supply_percentage"] = self.coordinator.data["supply_percentage"]

        if "exhaust_percentage" in self.coordinator.data:
            attributes["exhaust_percentage"] = self.coordinator.data["exhaust_percentage"]

        # Add current mode
        current_mode = self._get_current_mode()
        if current_mode:
            attributes["operating_mode"] = current_mode

        # Add system status
        system_status = []
        if self.coordinator.data.get("power_supply_fans"):
            system_status.append("fans_powered")
        if self.coordinator.data.get("boost_mode"):
            system_status.append("boost_active")
        if self.coordinator.data.get("eco_mode"):
            system_status.append("eco_active")

        if system_status:
            attributes["system_status"] = system_status

        # Add last update time
        last_update = (
            self.coordinator.device_client.statistics.get("last_successful_update")
            or self.coordinator.last_update
        )
        if last_update is not None:
            attributes["last_updated"] = last_update.isoformat()

        return attributes
