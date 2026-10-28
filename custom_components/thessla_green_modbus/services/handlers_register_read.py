"""Read named register definitions through the existing, serialized connection."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError

from ..registers.loader import get_register_definition
from .handler_deps import ServiceHandlerDeps
from .handlers_data import _READ_ERRORS, _read_batch_via_existing_client
from .schema import _target_schema

READ_REGISTER_DIAGNOSTICS_SCHEMA = _target_schema(
    {vol.Required("names"): vol.All([str], vol.Length(min=1, max=32))}
)
_TYPES = {1: "coil_registers", 2: "discrete_inputs", 3: "holding_registers", 4: "input_registers"}


async def read_register_diagnostics(coordinator: Any, names: list[str]) -> dict[str, Any]:
    """Return raw and decoded values; never write or open a second connection."""
    try:
        definitions = [get_register_definition(name) for name in dict.fromkeys(names)]
    except KeyError as exc:
        raise ServiceValidationError(f"Unknown register name: {exc.args[0]}") from exc
    records: dict[str, Any] = {}
    cache: dict[tuple[int, int, int], Any] = {}
    dc = coordinator.device_client
    async with dc._write_lock:
        await coordinator._ensure_connection()
        for definition in definitions:
            function, start, count = definition.function, definition.address, definition.length
            if function == 3:
                for block_start, block_count in ((0, 4), (7, 3)):
                    if block_start <= start < block_start + block_count:
                        start, count = block_start, block_count
                        break
            key = (function, start, count)
            record: dict[str, Any] = {
                "function": function,
                "address": definition.address,
                "raw": None,
                "decoded": None,
            }
            records[definition.name] = record
            try:
                if key not in cache:
                    cache[key] = await _read_batch_via_existing_client(
                        dc, _TYPES[function], start, count
                    )
                response = cache[key]
                if response is None:
                    record["status"] = "indeterminate"
                    continue
                if response.isError():
                    record.update(status="modbus_exception", exception_code=response.exception_code)
                    continue
                values = response.bits if function in (1, 2) else response.registers
                offset = definition.address - start
                raw = list(values[offset : offset + definition.length])
                if len(raw) != definition.length:
                    record["status"] = "incomplete_response"
                    continue
                record["raw"] = raw
                record["decoded"] = definition.decode(raw if definition.length > 1 else raw[0])
                record["status"] = "ok"
            except _READ_ERRORS as exc:
                record.update(status="indeterminate", error=type(exc).__name__)
            except (ValueError, TypeError) as exc:
                record.update(status="decode_error", error=str(exc))
    return {"registers": records, "writes_sent": 0}


def register_register_read_service(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register a bounded, read-only diagnostic action."""

    async def handle(call: ServiceCall) -> dict[str, Any]:
        targets = await deps.iter_target_coordinators(hass, call)
        unique = {id(coordinator): coordinator for _, coordinator in targets}
        if len(unique) != 1:
            raise ServiceValidationError("Select exactly one device")
        return await read_register_diagnostics(next(iter(unique.values())), call.data["names"])

    hass.services.async_register(
        deps.domain,
        "read_register_diagnostics",
        handle,
        READ_REGISTER_DIAGNOSTICS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
