"""Mode-related service registration helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .handler_deps import ServiceHandlerDeps
from .schema import SET_SPECIAL_MODE_SCHEMA

_DURATION_REGISTERS = {
    "boost": ("airing_panel_mode_time", 45),
    "airing_manual": ("airing_panel_mode_time", 45),
    "fireplace": ("fireplace_mode_time", 10),
}


async def _refresh_and_log_mode_success(
    coordinator: Any, deps: ServiceHandlerDeps, mode: str, entity_id: str
) -> None:
    await coordinator.async_request_refresh()
    deps.logger.info("Set special mode %s for %s", mode, entity_id)


def register_mode_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register mode-related services."""

    async def set_special_mode(call: ServiceCall) -> None:
        mode = deps.normalize_option(call.data["mode"])
        duration = call.data.get("duration", 0)

        for entity_id, coordinator in await deps.iter_target_coordinators(hass, call):
            if mode not in deps.special_function_map:
                raise ServiceValidationError(f"Unsupported AirPack special function: {mode}")
            duration_register = None
            if duration > 0:
                if mode not in _DURATION_REGISTERS:
                    raise ServiceValidationError(f"No documented duration control for {mode}")
                duration_register, maximum = _DURATION_REGISTERS[mode]
                holding = coordinator.device_client.available_registers.get(
                    "holding_registers", set()
                )
                if duration_register not in holding or not 1 <= duration <= maximum:
                    raise ServiceValidationError(
                        f"Duration unavailable or outside 1..{maximum} minutes for {mode}"
                    )
            if duration_register is not None:
                await deps.write_register(
                    coordinator, duration_register, duration, entity_id, "set special mode duration"
                )
            await deps.write_register(
                coordinator,
                "special_mode",
                deps.special_function_map[mode],
                entity_id,
                "set special mode",
            )

            await _refresh_and_log_mode_success(coordinator, deps, mode, entity_id)

    hass.services.async_register(
        deps.domain, "set_special_mode", set_special_mode, SET_SPECIAL_MODE_SCHEMA
    )
    hass.services.async_register(deps.domain, "set_mode", set_special_mode, SET_SPECIAL_MODE_SCHEMA)
    hass.services.async_register(
        deps.domain, "set_special_function", set_special_mode, SET_SPECIAL_MODE_SCHEMA
    )
