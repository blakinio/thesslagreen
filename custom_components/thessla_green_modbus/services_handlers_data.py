"""Data/diagnostics service registration helpers."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall

from .services_handler_deps import ServiceHandlerDeps
from .services_schema import (
    REFRESH_DEVICE_DATA_SCHEMA,
    SCAN_ALL_REGISTERS_SCHEMA,
    SET_LOG_LEVEL_SCHEMA,
)


def register_data_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register refresh/scan/logging services."""

    async def refresh_device_data(call: ServiceCall) -> None:
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            await coordinator.async_request_refresh()
            deps.logger.info("Refreshed device data for %s", entity_id)

    async def get_unknown_registers(call: ServiceCall) -> None:
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            hass.bus.async_fire(
                f"{deps.domain}_unknown_registers",
                {
                    "entity_id": entity_id,
                    "unknown_registers": coordinator.unknown_registers,
                    "scanned_registers": coordinator.scanned_registers,
                },
            )

    async def scan_all_registers(call: ServiceCall) -> dict[str, Any] | None:
        results: dict[str, Any] = {}
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            scanner = None
            try:
                scanner = await deps.scanner_create(
                    host=coordinator.host,
                    port=coordinator.port,
                    slave_id=coordinator.slave_id,
                    timeout=int(coordinator.timeout),
                    retry=coordinator.retry,
                    scan_uart_settings=coordinator.scan_uart_settings,
                    skip_known_missing=False,
                    full_register_scan=True,
                    max_registers_per_request=coordinator.effective_batch,
                    hass=hass,
                )
                scan_result = await scanner.scan_device()
            finally:
                if scanner is not None:
                    await scanner.close()

            coordinator.device_scan_result = scan_result
            unknown_registers = scan_result.get("unknown_registers", {})
            summary = {
                "register_count": scan_result.get("register_count", 0),
                "unknown_register_count": sum(len(v) for v in unknown_registers.values()),
            }
            results[entity_id] = {"unknown_registers": unknown_registers, "summary": summary}
            deps.logger.info(
                "Full register scan for %s completed: %s, unknown registers: %s",
                entity_id,
                summary,
                unknown_registers,
            )
        return results or None

    async def set_debug_logging(call: ServiceCall) -> None:
        level_name = str(call.data.get("level", "debug")).upper()
        duration = int(call.data.get("duration", 900))
        level_value = getattr(logging, level_name, logging.DEBUG)
        manager = hass.data.setdefault(deps.domain, {}).setdefault(
            "_log_level_manager", deps.create_log_level_manager(hass)
        )
        manager.set_level(level_value, duration)

    hass.services.async_register(
        deps.domain, "refresh_device_data", refresh_device_data, REFRESH_DEVICE_DATA_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "get_unknown_registers", get_unknown_registers, REFRESH_DEVICE_DATA_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "scan_all_registers", scan_all_registers, SCAN_ALL_REGISTERS_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "set_debug_logging", set_debug_logging, SET_LOG_LEVEL_SCHEMA
    )
