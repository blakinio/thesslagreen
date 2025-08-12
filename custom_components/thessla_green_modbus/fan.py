"""Fan platform for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

try:  # pragma: no cover - handle missing pymodbus during tests
    from pymodbus.exceptions import ConnectionException, ModbusException
except (ModuleNotFoundError, ImportError):  # pragma: no cover

    class ConnectionException(Exception):
        """Fallback exception when pymodbus is unavailable."""

        pass

    class ModbusException(Exception):
        """Fallback Modbus exception when pymodbus is unavailable."""

        pass

from .const import DOMAIN
from .registers import HOLDING_REGISTERS
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen fan from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Check if fan control is available
    fan_registers = [
        "air_flow_rate_manual",
        "air_flow_rate_auto",
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
        has_fan_registers = any(
            register in HOLDING_REGISTERS for register in fan_registers[:2]
        )  # Only check writable registers

    if has_fan_registers:
        async_add_entities([ThesslaGreenFan(coordinator)])
        _LOGGER.info("Added fan entity")
    else:
        _LOGGER.debug("No fan control registers available - skipping fan entity")


class ThesslaGreenFan(ThesslaGreenEntity, FanEntity):
    """ThesslaGreen fan entity."""

    def __init__(self, coordinator: ThesslaGreenModbusCoordinator) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, "fan")

        # Entity configuration
        self._attr_translation_key = "thessla_green_fan"

        # Fan configuration
        self._attr_supported_features = FanEntityFeature.SET_SPEED

        # Speed range (10-100% as per ThesslaGreen specs)
        self._attr_speed_count = 10  # 10%, 20%, ..., 100%

        _LOGGER.debug("Initialized fan entity")

    @property
    def available(self) -> bool:
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

        # Convert to percentage (clamp to 0-100)
        return max(0, min(100, int(flow_rate)))

    def _get_current_flow_rate(self) -> float | None:
        """Get current flow rate from available registers."""
        # Priority order for reading current flow rate
        flow_registers = [
            "supply_air_flow",  # Supply air flow rate
            "supply_percentage",  # Supply air percentage
            "air_flow_rate_manual",  # Manual flow rate setting
            "air_flow_rate_auto",  # Auto flow rate setting
        ]

        for register in flow_registers:
            if register in self.coordinator.data:
                value = self.coordinator.data[register]
                if value is not None and isinstance(value, (int, float)):
                    return float(value)

        return None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        try:
            # First ensure system is on
            if "on_off_panel_mode" in HOLDING_REGISTERS:
                await self._write_register("on_off_panel_mode", 1)

            # Set flow rate
            if percentage is not None:
                await self.async_set_percentage(percentage)
            else:
                # Default to 50% if no percentage specified
                await self.async_set_percentage(50)

            _LOGGER.info("Turned on fan")

        except (ModbusException, ConnectionException, RuntimeError) as exc:
            _LOGGER.error("Failed to turn on fan: %s", exc)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        try:
            if "on_off_panel_mode" in HOLDING_REGISTERS:
                # If system power control is available, use it to turn off
                await self._write_register("on_off_panel_mode", 0)
                self.coordinator.data["on_off_panel_mode"] = 0
            else:
                # Otherwise write zero flow to the active airflow register
                current_mode = self._get_current_mode()
                register = (
                    "air_flow_rate_manual"
                    if current_mode == "manual" or not current_mode
                    else "air_flow_rate_auto"
                )
                if register in HOLDING_REGISTERS:
                    await self._write_register(register, 0)
                    self.coordinator.data[register] = 0

            _LOGGER.info("Turned off fan")

        except (ModbusException, ConnectionException, RuntimeError) as exc:
            _LOGGER.error("Failed to turn off fan: %s", exc)
            raise

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage < 0 or percentage > 100:
            _LOGGER.error("Invalid percentage %d (must be 0-100)", percentage)
            return

        try:
            if percentage == 0:
                await self.async_turn_off()
                _LOGGER.info("Set fan speed to 0%")
                return

            # Ensure minimum flow rate (ThesslaGreen typically requires 10% minimum)
            actual_percentage = max(10, percentage)

            # Determine which register to write based on current mode
            current_mode = self._get_current_mode()

            if current_mode == "manual" or not current_mode:
                # Set manual mode and flow rate
                if "mode" in HOLDING_REGISTERS:
                    await self._write_register("mode", 1)  # Manual mode
                if "air_flow_rate_manual" in HOLDING_REGISTERS:
                    await self._write_register("air_flow_rate_manual", actual_percentage)
            else:
                # Auto mode - set auto flow rate
                if "air_flow_rate_auto" in HOLDING_REGISTERS:
                    await self._write_register("air_flow_rate_auto", actual_percentage)

            _LOGGER.info("Set fan speed to %d%%", actual_percentage)

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
        if register_name not in HOLDING_REGISTERS:
            raise ValueError(f"Register {register_name} is not writable")

        success = await self.coordinator.async_write_register(
            register_name, value, refresh=False
        )
        if not success:
            raise RuntimeError(f"Failed to write register {register_name}")

        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}

        # Add flow information
        if "supply_flowrate" in self.coordinator.data:
            attributes["supply_flow"] = self.coordinator.data["supply_flowrate"]

        if "exhaust_flowrate" in self.coordinator.data:
            attributes["exhaust_flow"] = self.coordinator.data["exhaust_flowrate"]

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
        if self.coordinator.last_successful_update:
            attributes["last_updated"] = self.coordinator.last_successful_update.isoformat()

        return attributes
