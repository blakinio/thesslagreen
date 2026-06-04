"""Data/diagnostics service registration helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from pymodbus.exceptions import ConnectionException, ModbusException

from ..registers.read_planner import group_reads
from .handler_deps import ServiceHandlerDeps
from .schema import (
    REFRESH_DEVICE_DATA_SCHEMA,
    SCAN_ALL_REGISTERS_SCHEMA,
    VALIDATE_KNOWN_REGISTERS_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

_CATCH_ERRORS = (ModbusException, ConnectionException, TimeoutError, OSError)


def _response_has_data(response: Any) -> bool:
    """Return True if a Modbus response contains register or coil data."""
    if response is None:
        return False
    registers = getattr(response, "registers", None)
    if registers:
        return True
    return bool(getattr(response, "bits", None))


async def _read_batch_via_existing_client(
    device_client: Any,
    reg_type: str,
    start: int,
    count: int,
) -> Any:
    """Read a register batch via device_client's active connection without opening a new one."""
    method_map = {
        "input_registers": "read_input_registers",
        "holding_registers": "read_holding_registers",
        "coil_registers": "read_coils",
        "discrete_inputs": "read_discrete_inputs",
    }
    fn_name = method_map.get(reg_type)
    if fn_name is None:
        raise ValueError(f"Unknown register type: {reg_type}")
    fn = device_client._get_client_method(fn_name)
    return await device_client._call_modbus(fn, start, count=count)


async def _read_known_registers_safe(
    coordinator: Any,
    batch: int,
    delay_ms: int,
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, list[dict[str, Any]]], int]:
    """Read all known register addresses under _write_lock using the active connection.

    Prevents concurrent coordinator polling during validation by holding
    _write_lock for the entire read loop. No new Modbus transport is opened.

    On batch read failure, falls back to individual address reads within the same
    lock and connection, so only truly unsupported addresses are marked missing.

    Returns (available, missing, failed_ranges, retried_individual_count).
    failed_ranges contains {start, count, error} for each batch that needed fallback.
    retried_individual_count is the total number of individual reads performed as fallback.
    """
    dc = coordinator.device_client
    available: dict[str, set[str]] = {}
    missing: dict[str, set[str]] = {}
    failed_ranges: dict[str, list[dict[str, Any]]] = {}
    retried_individual_count = 0

    async with dc._write_lock:
        await coordinator._ensure_connection()

        for reg_type, reg_map in dc._register_maps.items():
            avail: set[str] = set()
            miss: set[str] = set()
            faults: list[dict[str, Any]] = []

            if reg_map:
                addr_to_name: dict[int, str] = {addr: name for name, addr in reg_map.items()}
                groups = group_reads(sorted(addr_to_name.keys()), max_block_size=batch)

                for start, group_count in groups:
                    if delay_ms > 0:
                        await asyncio.sleep(delay_ms / 1000.0)

                    valid_names = {
                        addr_to_name[start + i]
                        for i in range(group_count)
                        if (start + i) in addr_to_name
                    }

                    batch_ok = False
                    batch_error: str | None = None
                    try:
                        resp = await _read_batch_via_existing_client(
                            dc, reg_type, start, group_count
                        )
                        if _response_has_data(resp):
                            avail.update(valid_names)
                            batch_ok = True
                        else:
                            batch_error = "empty_response"
                    except _CATCH_ERRORS as exc:
                        batch_error = type(exc).__name__

                    if not batch_ok:
                        faults.append({"start": start, "count": group_count, "error": batch_error})
                        # Fallback: retry each known address individually to isolate failures.
                        # This ensures only truly unsupported addresses are marked missing.
                        for i in range(group_count):
                            addr = start + i
                            if addr not in addr_to_name:
                                continue
                            name = addr_to_name[addr]
                            retried_individual_count += 1
                            if delay_ms > 0:
                                await asyncio.sleep(delay_ms / 1000.0)
                            try:
                                single_resp = await _read_batch_via_existing_client(
                                    dc, reg_type, addr, 1
                                )
                                if _response_has_data(single_resp):
                                    avail.add(name)
                                else:
                                    miss.add(name)
                            except _CATCH_ERRORS:
                                miss.add(name)

            available[reg_type] = avail
            missing[reg_type] = miss
            failed_ranges[reg_type] = faults

    return available, missing, failed_ranges, retried_individual_count


def _register_refresh_device_data_service(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register the refresh_device_data and get_unknown_registers services."""

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

    hass.services.async_register(
        deps.domain, "refresh_device_data", refresh_device_data, REFRESH_DEVICE_DATA_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "get_unknown_registers", get_unknown_registers, REFRESH_DEVICE_DATA_SCHEMA
    )


def _register_scan_all_registers_service(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register the scan_all_registers service.

    WARNING: scan_all_registers opens a SEPARATE Modbus connection and will cause
    transaction_id mismatch errors while the coordinator is actively polling.
    For safe real-device validation, use validate_known_registers instead.
    """

    async def scan_all_registers(call: ServiceCall) -> dict[str, Any] | None:
        results: dict[str, Any] = {}
        known_registers_only: bool = call.data.get("known_registers_only", False)
        delay_ms: int = call.data.get("delay_between_requests_ms", 0)
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            effective_batch = coordinator.device_client.effective_batch
            batch = call.data.get("max_registers_per_request", effective_batch)
            deps.logger.warning(
                "scan_all_registers opens a SEPARATE Modbus TCP connection to %s:%s for %s. "
                "This WILL cause transaction_id mismatch errors while the coordinator is "
                "actively polling. Stop or disable the integration first, or use "
                "validate_known_registers which reuses the active connection safely.",
                coordinator.device_client.config.host,
                coordinator.device_client.config.port,
                entity_id,
            )
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
                    host=coordinator.device_client.config.host,
                    port=coordinator.device_client.config.port,
                    slave_id=coordinator.device_client.config.slave_id,
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

    hass.services.async_register(
        deps.domain, "scan_all_registers", scan_all_registers, SCAN_ALL_REGISTERS_SCHEMA
    )


def _register_validate_known_registers_service(
    hass: HomeAssistant, deps: ServiceHandlerDeps
) -> None:
    """Register the validate_known_registers service.

    Uses the coordinator's existing Modbus connection under _write_lock.
    No second connection is opened — safe to call while the integration is active.
    """

    async def validate_known_registers(call: ServiceCall) -> dict[str, Any] | None:
        """Read only known registers via the active coordinator connection."""
        results: dict[str, Any] = {}
        delay_ms: int = call.data.get("delay_between_requests_ms", 0)
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            effective_batch = coordinator.device_client.effective_batch
            batch = call.data.get("max_registers_per_request", effective_batch)
            deps.logger.info(
                "validate_known_registers started for %s: batch=%d, delay=%dms",
                entity_id,
                batch,
                delay_ms,
            )

            available, missing, failed_ranges, retried_count = await _read_known_registers_safe(
                coordinator, batch, delay_ms
            )

            missing_by_type = {rt: len(v) for rt, v in missing.items() if v}
            summary = {
                "supported_count": sum(len(v) for v in available.values()),
                "missing_count": sum(len(v) for v in missing.values()),
                "missing_by_type": missing_by_type,
                "retried_individual_count": retried_count,
            }
            missing_sorted: dict[str, list[str]] = {rt: sorted(v) for rt, v in missing.items()}
            results[entity_id] = {
                "available_registers": available,
                "missing_registers": missing_sorted,
                "failed_ranges": failed_ranges,
                "summary": summary,
            }
            deps.logger.info(
                "validate_known_registers completed for %s: supported=%d, missing=%d, by_type=%s",
                entity_id,
                summary["supported_count"],
                summary["missing_count"],
                missing_by_type,
            )
            for rt, names in missing_sorted.items():
                if names:
                    _LOGGER.debug(
                        "validate_known_registers missing %s for %s: %s",
                        rt,
                        entity_id,
                        names,
                    )
        return results or None

    hass.services.async_register(
        deps.domain,
        "validate_known_registers",
        validate_known_registers,
        VALIDATE_KNOWN_REGISTERS_SCHEMA,
    )


def register_data_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register refresh/scan services."""
    _register_refresh_device_data_service(hass, deps)
    _register_scan_all_registers_service(hass, deps)
    _register_validate_known_registers_service(hass, deps)
