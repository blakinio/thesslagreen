"""Serialize one complete schedule-slot edit and reconcile partial failures."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
from pymodbus.exceptions import ConnectionException, ModbusException

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_write_schedule_slot(
    coordinator: ThesslaGreenModbusCoordinator,
    schedule_register: str,
    start_value: str,
    setting_register: str,
    settings: dict[str, Any] | None,
) -> None:
    """Keep settings and activation time together relative to other HA writes.

    The two non-contiguous device words cannot be physically atomic. A rejected,
    cancelled or uncertain write therefore always requests reconciliation; no
    rollback is guessed and partial completion is never reported as success.
    """
    if not schedule_register.startswith(
        "schedule_"
    ) or setting_register != "setting_" + schedule_register.removeprefix("schedule_"):
        raise ValueError("Mismatched schedule-slot registers")
    start_definition = coordinator._resolve_write_definition(schedule_register)
    if start_definition is None:
        raise ValueError("Schedule register is not writable")
    start_definition.encode(start_value)
    attempted = completed = False
    try:
        async with coordinator.device_client._write_lock:
            if getattr(coordinator, "_shutting_down", False):
                raise HomeAssistantError("Coordinator is shutting down; no schedule write sent")
            writes: list[tuple[str, str | dict[str, Any]]] = (
                [(setting_register, settings)] if settings is not None else []
            )
            writes.append((schedule_register, start_value))
            for name, value in writes:
                attempted = True
                success, _ = await coordinator._locked_single_register_write(
                    register_name=name, value=value, offset=0, refresh=False
                )
                if not success:
                    raise HomeAssistantError(
                        "Schedule update incomplete; settings may have changed. Reconciliation requested."
                    )
            completed = True
    except asyncio.CancelledError:
        raise
    except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError) as err:
        raise HomeAssistantError(
            "Schedule update incomplete; settings may have changed. Reconciliation requested."
        ) from err
    finally:
        if attempted:
            # The transport lock is released before refresh: never re-enter it.
            try:
                await coordinator.async_request_refresh()
            except Exception:
                _LOGGER.exception(
                    "Failed to reconcile schedule after edit of %s", schedule_register
                )
                if completed:
                    raise
