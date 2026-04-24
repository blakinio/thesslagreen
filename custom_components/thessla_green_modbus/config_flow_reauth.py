"""Helpers for config flow reauthentication step."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.const import CONF_HOST
from voluptuous import Invalid as VOL_INVALID

from .const import (
    CONF_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    MAX_BATCH_REGISTERS,
)
from .errors import CannotConnect, InvalidAuth
from .modbus_exceptions import ConnectionException, ModbusException


async def process_reauth_submission(
    user_input: dict[str, Any],
    *,
    validate_input: Callable[[Any, dict[str, Any]], Awaitable[dict[str, Any]]],
    hass: Any,
    logger,
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Validate and process reauth form submission."""

    errors: dict[str, str] = {}
    try:
        max_regs = user_input.get(
            CONF_MAX_REGISTERS_PER_REQUEST,
            DEFAULT_MAX_REGISTERS_PER_REQUEST,
        )
        if not 1 <= max_regs <= MAX_BATCH_REGISTERS:
            raise VOL_INVALID("max_registers_range", path=[CONF_MAX_REGISTERS_PER_REQUEST])

        info = await validate_input(hass, user_input)
        return info, errors

    except CannotConnect as exc:
        errors["base"] = exc.args[0] if exc.args else "cannot_connect"
    except InvalidAuth:
        errors["base"] = "invalid_auth"
    except VOL_INVALID as err:
        logger.error(
            "Invalid input for %s: %s",
            err.path[0] if err.path else "unknown",
            err,
        )
        errors[err.path[0] if err.path else CONF_HOST] = err.error_message
    except (ConnectionException, ModbusException):
        logger.exception("Modbus communication error")
        errors["base"] = "cannot_connect"
    except ValueError as err:
        logger.error("Invalid value provided: %s", err)
        errors["base"] = "invalid_input"
    except KeyError as err:
        logger.error("Missing required data: %s", err)
        errors["base"] = "invalid_input"

    return None, errors
