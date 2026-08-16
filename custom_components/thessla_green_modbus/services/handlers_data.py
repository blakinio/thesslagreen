"""Data/diagnostics service registration helpers."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from pymodbus.exceptions import ConnectionException, ModbusException

from ..const import KNOWN_MISSING_CLASSIFICATION
from ..registers.read_planner import group_reads
from .handler_deps import ServiceHandlerDeps
from .schema import (
    REFRESH_DEVICE_DATA_SCHEMA,
    SCAN_ALL_REGISTERS_SCHEMA,
    VALIDATE_KNOWN_REGISTERS_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

_TRANSPORT_ERRORS = (ConnectionException, TimeoutError, OSError)
_READ_ERRORS = (ModbusException, *_TRANSPORT_ERRORS)


def _response_has_data(response: Any) -> bool:
    """Return True if a Modbus response contains register or coil data."""
    if response is None:
        return False
    registers = getattr(response, "registers", None)
    if registers:
        return True
    return bool(getattr(response, "bits", None))


def _response_is_modbus_error(response: Any) -> bool:
    """Return True only when the device returned an explicit Modbus error response."""
    if response is None:
        return False
    is_error = getattr(response, "isError", None)
    if not callable(is_error):
        return False
    try:
        return bool(is_error())
    except (TypeError, ValueError):
        return False


async def _read_batch_via_existing_client(
    device_client: Any,
    reg_type: str,
    start: int,
    count: int,
) -> Any:
    """Read a register batch through the already-owned Modbus connection.

    Transport wrapper methods already accept ``slave_id`` explicitly and own
    connection/retry handling. They must therefore be called directly rather
    than routed back through ``DeviceClient._call_modbus`` (which is intended
    for raw pymodbus methods and injects the slave ID itself).
    """
    method_map = {
        "input_registers": "read_input_registers",
        "holding_registers": "read_holding_registers",
        "coil_registers": "read_coils",
        "discrete_inputs": "read_discrete_inputs",
    }
    fn_name = method_map.get(reg_type)
    if fn_name is None:
        raise ValueError(f"Unknown register type: {reg_type}")

    transport = getattr(device_client, "_transport", None)
    if transport is not None:
        transport_fn = getattr(transport, fn_name, None)
        # Real transport read APIs are async.  Do not mistake a loose MagicMock
        # attribute (or another non-async compatibility shim) for that contract;
        # fall back to the already-owned raw client path instead.
        if callable(transport_fn) and inspect.iscoroutinefunction(transport_fn):
            return await transport_fn(device_client.slave_id, start, count=count)

    raw_client = getattr(device_client, "client", None)
    fn = getattr(raw_client, fn_name, None) if raw_client is not None else None
    if not callable(fn):
        # Compatibility fallback for legacy/mocked DeviceClient shapes.  At
        # runtime this resolves a raw client method when no transport wrapper
        # implements the requested operation (notably coil/discrete reads).
        fn = device_client._get_client_method(fn_name)
    return await device_client._call_modbus(fn, start, count=count)


async def _read_known_registers_safe(
    coordinator: Any,
    batch: int,
    delay_ms: int,
) -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, list[dict[str, Any]]],
    int,
]:
    """Validate known addresses through the coordinator's existing connection.

    The entire validation runs under the device write lock, preventing regular
    polling from interleaving with diagnostic reads. Explicit Modbus error
    responses are classified as unsupported. Connection failures, timeouts,
    raised Modbus exceptions, and empty/ambiguous responses are classified as
    indeterminate so a transient transport problem is never reported as a
    missing register.
    """
    dc = coordinator.device_client
    available: dict[str, set[str]] = {}
    missing: dict[str, set[str]] = {}
    indeterminate: dict[str, set[str]] = {}
    failed_ranges: dict[str, list[dict[str, Any]]] = {}
    retried_individual_count = 0

    async with dc._write_lock:
        await coordinator._ensure_connection()

        for reg_type, reg_map in dc._register_maps.items():
            avail: set[str] = set()
            miss: set[str] = set()
            unknown: set[str] = set()
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
                        elif _response_is_modbus_error(resp):
                            batch_error = "modbus_error_response"
                        else:
                            batch_error = "ambiguous_empty_response"
                    except _READ_ERRORS as exc:
                        batch_error = type(exc).__name__

                    if batch_ok:
                        continue

                    faults.append({"start": start, "count": group_count, "error": batch_error})
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
                        except _READ_ERRORS:
                            unknown.add(name)
                            continue

                        if _response_has_data(single_resp):
                            avail.add(name)
                        elif _response_is_modbus_error(single_resp):
                            miss.add(name)
                        else:
                            unknown.add(name)

            available[reg_type] = avail
            missing[reg_type] = miss
            indeterminate[reg_type] = unknown
            failed_ranges[reg_type] = faults

    return available, missing, indeterminate, failed_ranges, retried_individual_count


async def _scan_with_polling_paused(
    hass: HomeAssistant,
    coordinator: Any,
    deps: ServiceHandlerDeps,
    *,
    batch: int,
    delay_ms: int,
    known_registers_only: bool,
) -> dict[str, Any]:
    """Run the separate scanner only while the coordinator transport is offline.

    Holding the device write lock pauses coordinator IO. The primary transport
    is disconnected before the scanner opens its connection/serial port, and
    is restored before the lock is released. This prevents concurrent Modbus
    clients and works for TCP, RTU-over-TCP, and serial RTU configurations.
    """
    dc = coordinator.device_client
    cfg = dc.config
    scanner = None

    async with dc._write_lock:
        await dc.async_disconnect()
        try:
            scanner = await deps.scanner_create(
                host=cfg.host,
                port=cfg.port,
                slave_id=cfg.slave_id,
                timeout=int(dc.timeout),
                retry=dc.retry,
                scan_uart_settings=dc.scan_uart_settings,
                skip_known_missing=False,
                full_register_scan=not known_registers_only,
                max_registers_per_request=batch,
                delay_between_requests_ms=delay_ms,
                connection_type=cfg.connection_type,
                connection_mode=cfg.connection_mode,
                serial_port=cfg.serial_port,
                baud_rate=cfg.baud_rate,
                parity=cfg.parity,
                stop_bits=cfg.stop_bits,
                hass=hass,
            )
            return await scanner.scan_device()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            raise HomeAssistantError(f"Register scan failed: {err}") from err
        finally:
            if scanner is not None:
                try:
                    await scanner.close()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Failed to close diagnostic scanner cleanly: %s", err)
            try:
                await dc.async_ensure_connected()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                raise HomeAssistantError(
                    f"Register scan finished but the primary Modbus connection could not be restored: {err}"
                ) from err


def _register_refresh_device_data_service(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register the refresh_device_data and get_unknown_registers services."""

    async def refresh_device_data(call: ServiceCall) -> None:
        for entity_id, coordinator in await deps.iter_target_coordinators(hass, call):
            await coordinator.async_request_refresh()
            deps.logger.info("Refreshed device data for %s", entity_id)

    async def get_unknown_registers(call: ServiceCall) -> None:
        for entity_id, coordinator in await deps.iter_target_coordinators(hass, call):
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
    """Register a full scanner that cannot overlap regular coordinator IO."""

    async def scan_all_registers(call: ServiceCall) -> dict[str, Any]:
        results: dict[str, Any] = {}
        known_registers_only: bool = call.data.get("known_registers_only", False)
        delay_ms: int = call.data.get("delay_between_requests_ms", 0)
        for entity_id, coordinator in await deps.iter_target_coordinators(hass, call):
            effective_batch = coordinator.device_client.effective_batch
            batch = call.data.get("max_registers_per_request", effective_batch)
            deps.logger.info(
                "Isolated register scan started for %s: batch=%d, delay=%dms, known_only=%s",
                entity_id,
                batch,
                delay_ms,
                known_registers_only,
            )
            scan_result = await _scan_with_polling_paused(
                hass,
                coordinator,
                deps,
                batch=batch,
                delay_ms=delay_ms,
                known_registers_only=known_registers_only,
            )

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
            deps.logger.info("Isolated register scan completed for %s: %s", entity_id, summary)
        return results

    hass.services.async_register(
        deps.domain,
        "scan_all_registers",
        scan_all_registers,
        SCAN_ALL_REGISTERS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def _register_validate_known_registers_service(
    hass: HomeAssistant, deps: ServiceHandlerDeps
) -> None:
    """Register validation through the active coordinator connection."""

    async def validate_known_registers(call: ServiceCall) -> dict[str, Any]:
        """Read only known registers via the active coordinator connection."""
        results: dict[str, Any] = {}
        delay_ms: int = call.data.get("delay_between_requests_ms", 0)
        for entity_id, coordinator in await deps.iter_target_coordinators(hass, call):
            effective_batch = coordinator.device_client.effective_batch
            batch = call.data.get("max_registers_per_request", effective_batch)
            deps.logger.info(
                "validate_known_registers started for %s: batch=%d, delay=%dms",
                entity_id,
                batch,
                delay_ms,
            )

            (
                available,
                missing,
                indeterminate,
                failed_ranges,
                retried_count,
            ) = await _read_known_registers_safe(coordinator, batch, delay_ms)

            missing_by_type = {rt: len(v) for rt, v in missing.items() if v}
            indeterminate_by_type = {rt: len(v) for rt, v in indeterminate.items() if v}
            summary = {
                "supported_count": sum(len(v) for v in available.values()),
                "missing_count": sum(len(v) for v in missing.values()),
                "indeterminate_count": sum(len(v) for v in indeterminate.values()),
                "missing_by_type": missing_by_type,
                "indeterminate_by_type": indeterminate_by_type,
                "retried_individual_count": retried_count,
            }
            missing_sorted: dict[str, list[str]] = {rt: sorted(v) for rt, v in missing.items()}
            indeterminate_sorted: dict[str, list[str]] = {
                rt: sorted(v) for rt, v in indeterminate.items()
            }
            available_sorted: dict[str, list[str]] = {rt: sorted(v) for rt, v in available.items()}
            classification: dict[str, str] = {}
            for names in missing.values():
                for name in names:
                    if name in KNOWN_MISSING_CLASSIFICATION:
                        classification[name] = KNOWN_MISSING_CLASSIFICATION[name]
            results[entity_id] = {
                "available_registers": available_sorted,
                "missing_registers": missing_sorted,
                "indeterminate_registers": indeterminate_sorted,
                "failed_ranges": failed_ranges,
                "summary": summary,
                "register_classification": classification,
            }
            deps.logger.info(
                "validate_known_registers completed for %s: supported=%d, missing=%d, indeterminate=%d",
                entity_id,
                summary["supported_count"],
                summary["missing_count"],
                summary["indeterminate_count"],
            )
            for rt, sorted_names in missing_sorted.items():
                if sorted_names:
                    _LOGGER.debug(
                        "validate_known_registers unsupported %s for %s: %s",
                        rt,
                        entity_id,
                        sorted_names,
                    )
            for rt, sorted_names in indeterminate_sorted.items():
                if sorted_names:
                    _LOGGER.warning(
                        "validate_known_registers indeterminate %s for %s: %s",
                        rt,
                        entity_id,
                        sorted_names,
                    )
        return results

    hass.services.async_register(
        deps.domain,
        "validate_known_registers",
        validate_known_registers,
        VALIDATE_KNOWN_REGISTERS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def register_data_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register refresh/scan services."""
    _register_refresh_device_data_service(hass, deps)
    _register_scan_all_registers_service(hass, deps)
    _register_validate_known_registers_service(hass, deps)
