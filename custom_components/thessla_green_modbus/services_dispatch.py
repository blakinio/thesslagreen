"""Common coordinator dispatch helpers for service handlers."""

from __future__ import annotations

from typing import Any

from .modbus_exceptions import ConnectionException, ModbusException


async def write_register(
    coordinator: Any,
    register: str,
    value: Any,
    entity_id: str,
    action: str,
    logger: Any,
) -> bool:
    """Write to a register with consistent error handling."""
    try:
        return bool(await coordinator.async_write_register(register, value, refresh=False))
    except (ModbusException, ConnectionException) as err:
        logger.error("Failed to %s for %s: %s", action, entity_id, err)
        return False


async def refresh_and_log_success(
    coordinator: Any,
    logger: Any,
    message: str,
    *args: object,
) -> None:
    """Refresh coordinator data and emit a success log line."""
    await coordinator.async_request_refresh()
    logger.info(message, *args)


async def write_optional_register(
    coordinator: Any,
    register_name: str,
    value: object,
    entity_id: str,
    action: str,
    error_message: str,
    write_register_func: Any,
    logger: Any,
) -> bool:
    """Write optional register value when provided."""
    if value is None:
        return True
    if not await write_register_func(coordinator, register_name, value, entity_id, action):
        logger.error(error_message, entity_id)
        return False
    return True


async def write_mapped_optional_register(
    coordinator: Any,
    register_name: str,
    option_value: str | None,
    option_map: dict[str, int],
    entity_id: str,
    action: str,
    error_message: str,
    write_register_func: Any,
    logger: Any,
) -> bool:
    """Write mapped register value when option is provided."""
    if option_value is None:
        return True
    return await write_optional_register(
        coordinator,
        register_name,
        option_map[option_value],
        entity_id,
        action,
        error_message,
        write_register_func,
        logger,
    )
