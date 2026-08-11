"""Transport-aware reconfigure helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT

from ..const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_TYPE,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONNECTION_TYPE_RTU,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_SLAVE_ID,
)


def build_reconfigure_updates(
    entry_data: dict[str, Any], user_input: dict[str, Any]
) -> dict[str, Any]:
    """Return validated endpoint fields appropriate for the entry transport."""
    if entry_data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE) == CONNECTION_TYPE_RTU:
        return {
            CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT],
            CONF_BAUD_RATE: user_input[CONF_BAUD_RATE],
            CONF_PARITY: user_input[CONF_PARITY],
            CONF_STOP_BITS: user_input[CONF_STOP_BITS],
            CONF_SLAVE_ID: user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
        }

    return {
        CONF_HOST: user_input[CONF_HOST],
        CONF_PORT: user_input[CONF_PORT],
        CONF_SLAVE_ID: user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
    }
