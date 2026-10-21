"""Airing-time service using documented BCD time and 0x2400 disable marker."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .handler_deps import ServiceHandlerDeps
from .schema import SET_AIRING_SCHEDULE_SCHEMA


def register_airing_service(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register the manual/weekly airing-time service."""

    async def set_airing_schedule(call: ServiceCall) -> None:
        schedule = call.data.get("schedule", "manual")
        enabled = call.data.get("enabled", True)
        start = call.data.get("start_time")
        if enabled and start is None:
            raise ServiceValidationError("Enabled airing requires a start time")
        if schedule == "manual":
            name = "manual_airing_time_to_start"
        else:
            day = deps.normalize_option(call.data.get("day", ""))
            if day not in deps.day_to_device_key:
                raise ServiceValidationError("Weekly airing requires a day")
            name = f"airing_{schedule}_{deps.day_to_device_key[day]}"
        value = f"{start.hour:02d}:{start.minute:02d}" if enabled else "disabled"
        for entity_id, coordinator in await deps.iter_target_coordinators(hass, call):
            if name not in coordinator.device_client.available_registers.get(
                "holding_registers", set()
            ):
                raise ServiceValidationError(f"Airing register {name} is unavailable")
            await deps.write_register(coordinator, name, value, entity_id, "set airing time")
            await coordinator.async_request_refresh()

    hass.services.async_register(
        deps.domain, "set_airing_schedule", set_airing_schedule, SET_AIRING_SCHEDULE_SCHEMA
    )
