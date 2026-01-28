"""Fan platform for the ThesslaGreen Modbus integration.

The fan entity is only created when the required Modbus registers are
available on the device.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, holding_registers
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .modbus_exceptions import ConnectionException, ModbusException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:  # pragma: no cover
    """Set up ThesslaGreen fan from config entry.

    This is a Home Assistant callback invoked during platform setup.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]

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
        if register in coordinator.available_registers.get(
            "holding_registers", set()
        ) or register in coordinator.available_registers.get("input_registers", set()):
            has_fan_registers = True
            break

    # If force full register list, assume fan is available
    if not has_fan_registers and coordinator.force_full_register_list:
        h_regs = holding_registers()
        has_fan_registers = any(register in h_regs for register in fan_registers[:2])

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

    def __init__(self, coordinator: ThesslaGreenModbusCoordinator) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, "fan", 0)

        # Entity configuration
        self._attr_translation_key = "thessla_green_fan"  # pragma: no cover

        # Fan configuration
        self._attr_supported_features = FanEntityFeature.SET_SPEED  # pragma: no cover

        # Speed range defaults to 10-100% until limits are read from device
        self._attr_speed_count = 10  # pragma: no cover

        _LOGGER.debug("Initialized fan entity")

    @property
    def available(self) -> bool:  # pragma: no cover
        """Return if the fan entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get("on_off_panel_mode") is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on."""
        # Check if system is powered on
        if "on_off_panel_mode" in self.coordinator.data:
            if not self.coordinator.data["on_off_panel_mode"]:
                return False

        # Check current flow rate
        flow_rate = self._get_current_flow_rate()
        if flow_rate is None:
            return None

        return flow_rate > 0

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        flow_rate = self._get_current_flow_rate()
        if flow_rate is None:
            return None

        _, max_pct = self._get_percentage_limits()
        return max(0, min(max_pct, int(flow_rate)))

    def _get_percentage_limits(self) -> tuple[int, int]:
        """Return dynamic min/max percentage limits."""
        min_pct = self.coordinator.data.get("min_percentage")
        max_pct = self.coordinator.data.get("max_percentage")
        try:
            min_val = int(min_pct) if min_pct is not None else 10
        except (TypeError, ValueError):
            min_val = 10
        try:
            max_val = int(max_pct) if max_pct is not None else 150
        except (TypeError, ValueError):
            max_val = 150
        min_val = max(10, min_val)
        max_val = min(150, max_val)
        if max_val < min_val:
            max_val = min_val
        return min_val, max_val

    def _get_current_flow_rate(self) -> float | None:
        """Get current flow rate from available registers."""
        # Priority order for reading current flow rate
        flow_registers = [
            "supply_air_flow",  # Supply air flow rate
            "supply_flow_rate",  # CF measured supply flow rate
            "supply_percentage",  # Supply air percentage
            "air_flow_rate_manual",  # Manual flow rate setting
            "air_flow_rate_temporary_2",  # Temporary flow rate setting
        ]

        for register in flow_registers:
            if register in self.coordinator.data:
                value = self.coordinator.data[register]
                if value is not None and isinstance(value, int | float):
                    return float(value)

        return None

    @property
    def speed_count(self) -> int | None:  # pragma: no cover
        """Return dynamic speed count based on device limits."""
        min_val, max_val = self._get_percentage_limits()
        if max_val < min_val:
            return None
        steps = list(range(min_val, max_val + 1, 10))
        if steps and steps[-1] != max_val:
            steps.append(max_val)
        return len(steps)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:  # pragma: no cover
        """Turn on the fan."""
        try:
            # First ensure system is on
            holding_regs = self.coordinator.available_registers.get("holding_registers", set())
            if "on_off_panel_mode" in holding_registers() and "on_off_panel_mode" in holding_regs:
                await self._write_register("on_off_panel_mode", 1)

            # Set flow rate
            if percentage is not None:
                await self.async_set_percentage(percentage)
            else:
                # Default to 50% if no percentage specified
                await self.async_set_percentage(50)

            _LOGGER.debug("Turned on fan")

        except (ModbusException, ConnectionException, RuntimeError) as exc:
            _LOGGER.error("Failed to turn on fan: %s", exc)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        try:
            holding_regs = self.coordinator.available_registers.get("holding_registers", set())
            if "on_off_panel_mode" in holding_registers() and "on_off_panel_mode" in holding_regs:
                # If system power control is available, use it to turn off
                await self._write_register("on_off_panel_mode", 0)
                self.coordinator.data["on_off_panel_mode"] = 0
            else:
                # Otherwise write zero flow to the active airflow register
                current_mode = self._get_current_mode()
                register = (
                    "air_flow_rate_manual"
                    if current_mode == "manual" or not current_mode
                    else "air_flow_rate_temporary_2"
                )
                if register in holding_registers() and register in holding_regs:
                    await self._write_register(register, 0)
                    self.coordinator.data[register] = 0

            _LOGGER.debug("Turned off fan")

        except (ModbusException, ConnectionException, RuntimeError) as exc:
            _LOGGER.error("Failed to turn off fan: %s", exc)
            raise

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        min_val, max_val = self._get_percentage_limits()
        if percentage < 0:
            _LOGGER.error("Invalid percentage %d (must be >= 0)", percentage)
            return

        try:
            if percentage == 0:
                await self.async_turn_off()
                _LOGGER.debug("Set fan speed to 0%")
                return

            clamped = min(max_val, percentage)
            actual_percentage = max(min_val, clamped)

            # Determine which register to write based on current mode
            current_mode = self._get_current_mode()
            holding_regs = self.coordinator.available_registers.get("holding_registers", set())

            if current_mode == "manual" or not current_mode:
                # Set manual mode and flow rate
                if "mode" in holding_registers() and "mode" in holding_regs:
                    await self._write_register("mode", 1)  # Manual mode
                if (
                    "air_flow_rate_manual" in holding_registers()
                    and "air_flow_rate_manual" in holding_regs
                ):
                    await self._write_register("air_flow_rate_manual", actual_percentage)
            else:
                await self.coordinator.async_write_temporary_airflow(
                    mode=2,
                    airflow=actual_percentage,
                    refresh=False,
                )

            _LOGGER.debug("Set fan speed to %d%%", actual_percentage)

        except (ModbusException, ConnectionException, RuntimeError) as exc:
            _LOGGER.error("Failed to set fan speed to %d%%: %s", percentage, exc)
            raise

    def _get_current_mode(self) -> str | None:
        """Get current system mode."""
        if "mode" in self.coordinator.data:
            mode_value = self.coordinator.data["mode"]
            if mode_value == 0:
                return "auto"
            elif mode_value == 1:
                return "manual"
            elif mode_value == 2:
                return "temporary"
        return None

    async def _write_register(self, register_name: str, value: int) -> None:
        """Write value to register."""
        if register_name not in holding_registers():
            raise ValueError(f"Register {register_name} is not writable")

        holding_regs = self.coordinator.available_registers.get("holding_registers", set())
        if register_name not in holding_regs:
            _LOGGER.debug("Register %s unavailable, skipping write", register_name)
            return

        success = await self.coordinator.async_write_register(register_name, value, refresh=False)
        if not success:
            raise RuntimeError(f"Failed to write register {register_name}")

        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:  # pragma: no cover
        """Return additional state attributes."""
        attributes = {}

        # Add flow information
        if "supply_flow_rate" in self.coordinator.data:
            attributes["supply_flow"] = self.coordinator.data["supply_flow_rate"]

        if "exhaust_flow_rate" in self.coordinator.data:
            attributes["exhaust_flow"] = self.coordinator.data["exhaust_flow_rate"]

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
        if (
            "power_supply_fans" in self.coordinator.data
            and self.coordinator.data["power_supply_fans"]
        ):
            system_status.append("fans_powered")
        if "boost_mode" in self.coordinator.data and self.coordinator.data["boost_mode"]:
            system_status.append("boost_active")
        if "eco_mode" in self.coordinator.data and self.coordinator.data["eco_mode"]:
            system_status.append("eco_active")

        if system_status:
            attributes["system_status"] = system_status

        # Add last update time
        last_update = (
            self.coordinator.statistics.get("last_successful_update")
            or self.coordinator.last_update
        )
        if last_update is not None:
            attributes["last_updated"] = last_update.isoformat()

        return attributes
