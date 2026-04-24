"""Mode-related service registration helpers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall

from .services_handler_deps import ServiceHandlerDeps
from .services_schema import SET_SPECIAL_MODE_SCHEMA


def register_mode_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register mode-related services."""

    async def set_special_mode(call: ServiceCall) -> None:
        mode = deps.normalize_option(call.data["mode"])
        duration = call.data.get("duration", 0)

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            special_mode_value = deps.special_function_map.get(mode, 0)
            if not await deps.write_register(
                coordinator, "special_mode", special_mode_value, entity_id, "set special mode"
            ):
                deps.logger.error("Failed to set special mode %s for %s", mode, entity_id)
                continue

            if duration > 0 and mode in ["boost", "fireplace", "hood", "party", "bathroom"]:
                duration_register = f"{mode}_duration"
                if duration_register in coordinator.available_registers.get(
                    "holding_registers", set()
                ):
                    if not await deps.write_register(
                        coordinator, duration_register, duration, entity_id, "set special mode"
                    ):
                        deps.logger.error("Failed to set duration for %s on %s", mode, entity_id)
                        continue

            await coordinator.async_request_refresh()
            deps.logger.info("Set special mode %s for %s", mode, entity_id)

    hass.services.async_register(
        deps.domain, "set_special_mode", set_special_mode, SET_SPECIAL_MODE_SCHEMA
    )
    hass.services.async_register(deps.domain, "set_mode", set_special_mode, SET_SPECIAL_MODE_SCHEMA)
    hass.services.async_register(
        deps.domain, "set_special_function", set_special_mode, SET_SPECIAL_MODE_SCHEMA
    )
