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


async def write_register_batch(
    coordinator: Any,
    register_pairs: list[tuple[str, int]],
    entity_id: str,
    action: str,
    write_register_func: Any,
    logger: Any,
    error_messages: dict[str, str],
) -> bool:
    """Write a sequence of register/value pairs and stop on first failure."""
    for register_name, value in register_pairs:
        if not await write_register_func(coordinator, register_name, value, entity_id, action):
            logger.error(error_messages[register_name], entity_id)
            return False
    return True


async def write_register_steps(
    coordinator: Any,
    steps: list[tuple[str, object, bool, str]],
    entity_id: str,
    action: str,
    write_register_func: Any,
    logger: Any,
) -> bool:
    """Write required/optional register steps and stop on first failure.

    Each step is ``(register_name, value, optional, error_message)``.
    Optional values are skipped when ``value`` is ``None``.
    """
    for register_name, value, optional, error_message in steps:
        if optional and value is None:
            continue
        if not await write_register_func(coordinator, register_name, value, entity_id, action):
            logger.error(error_message, entity_id)
            return False
    return True
