"""Data/diagnostics service registration helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall

from .handler_deps import ServiceHandlerDeps
from .schema import (
    REFRESH_DEVICE_DATA_SCHEMA,
    SCAN_ALL_REGISTERS_SCHEMA,
    VALIDATE_KNOWN_REGISTERS_SCHEMA,
)


def register_data_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register refresh/scan services."""

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
                    "unknown_registers": coordinator.device_client.unknown_registers,
                    "scanned_registers": coordinator.device_client.scanned_registers,
                },
            )

    async def scan_all_registers(call: ServiceCall) -> dict[str, Any] | None:
        results: dict[str, Any] = {}
        known_registers_only: bool = call.data.get("known_registers_only", False)
        delay_ms: int = call.data.get("delay_between_requests_ms", 0)
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            effective_batch = coordinator.device_client.effective_batch
            batch = call.data.get("max_registers_per_request", effective_batch)
            deps.logger.info(
                "Scan all registers started for %s: batch=%d, delay=%dms, known_only=%s",
                entity_id,
                batch,
                delay_ms,
                known_registers_only,
            )
            scanner = None
            try:
                scanner = await deps.scanner_create(
                    host=coordinator.host,
                    port=coordinator.port,
                    slave_id=coordinator.slave_id,
                    timeout=int(coordinator.device_client.timeout),
                    retry=coordinator.device_client.retry,
                    scan_uart_settings=coordinator.device_client.scan_uart_settings,
                    skip_known_missing=False,
                    full_register_scan=not known_registers_only,
                    max_registers_per_request=batch,
                    delay_between_requests_ms=delay_ms,
                    hass=hass,
                )
                scan_result = await scanner.scan_device()
            finally:
                if scanner is not None:
                    await scanner.close()

            coordinator.device_client.device_scan_result = scan_result
            unknown_registers = scan_result.get("unknown_registers", {})
            failed_count = sum(
                len(v)
                for v in scan_result.get("failed_addresses", {})
                .get("modbus_exceptions", {})
                .values()
            )
            summary = {
                "register_count": scan_result.get("register_count", 0),
                "unknown_register_count": sum(len(v) for v in unknown_registers.values()),
                "failed_count": failed_count,
            }
            results[entity_id] = {"unknown_registers": unknown_registers, "summary": summary}
            deps.logger.info(
                "Scan all registers completed for %s: %s",
                entity_id,
                summary,
            )
        return results or None

    async def validate_known_registers(call: ServiceCall) -> dict[str, Any] | None:
        """Read only known registers from integration definitions."""
        results: dict[str, Any] = {}
        delay_ms: int = call.data.get("delay_between_requests_ms", 0)
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            effective_batch = coordinator.device_client.effective_batch
            batch = call.data.get("max_registers_per_request", effective_batch)
            deps.logger.info(
                "Validate known registers started for %s: batch=%d, delay=%dms",
                entity_id,
                batch,
                delay_ms,
            )
            scanner = None
            try:
                scanner = await deps.scanner_create(
                    host=coordinator.host,
                    port=coordinator.port,
                    slave_id=coordinator.slave_id,
                    timeout=int(coordinator.device_client.timeout),
                    retry=coordinator.device_client.retry,
                    scan_uart_settings=False,
                    skip_known_missing=False,
                    full_register_scan=False,
                    max_registers_per_request=batch,
                    delay_between_requests_ms=delay_ms,
                    hass=hass,
                )
                scan_result = await scanner.scan_device()
            finally:
                if scanner is not None:
                    await scanner.close()

            available = scan_result.get("available_registers", {})
            missing = scan_result.get("missing_registers", {})
            summary = {
                "supported_count": sum(len(v) for v in available.values()),
                "missing_count": sum(len(v) for v in missing.values()),
            }
            results[entity_id] = {"available_registers": available, "summary": summary}
            deps.logger.info(
                "Validate known registers completed for %s: %s",
                entity_id,
                summary,
            )
        return results or None

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
        deps.domain,
        "validate_known_registers",
        validate_known_registers,
        VALIDATE_KNOWN_REGISTERS_SCHEMA,
    )
