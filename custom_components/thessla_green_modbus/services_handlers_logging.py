"""Logging/debug service registration helpers."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, ServiceCall

from .services_handler_deps import ServiceHandlerDeps
from .services_schema import SET_LOG_LEVEL_SCHEMA


def register_logging_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register logging-related services."""

    async def set_debug_logging(call: ServiceCall) -> None:
        level_name = str(call.data.get("level", "debug")).upper()
        duration = int(call.data.get("duration", 900))
        level_value = getattr(logging, level_name, logging.DEBUG)
        manager = hass.data.setdefault(deps.domain, {}).setdefault(
            "_log_level_manager", deps.create_log_level_manager(hass)
        )
        manager.set_level(level_value, duration)

    hass.services.async_register(
        deps.domain, "set_debug_logging", set_debug_logging, SET_LOG_LEVEL_SCHEMA
    )
