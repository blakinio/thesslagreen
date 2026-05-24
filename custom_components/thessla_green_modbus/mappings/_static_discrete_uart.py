"""UART/serial-port configuration select mappings."""

from __future__ import annotations

from typing import Any

_UART_RISK = {
    "risk_level": "advanced",
    "risk_category": "communication_lockout",
    "safety_warning": "Advanced communication setting: changing this may break Modbus communication or make the device unreachable.",
}

UART_SELECT_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    "uart_0_baud": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_0_baud",
        "states": {
            "baud_4800": 0,
            "baud_9600": 1,
            "baud_14400": 2,
            "baud_19200": 3,
            "baud_28800": 4,
            "baud_38400": 5,
            "baud_57600": 6,
            "baud_76800": 7,
            "baud_115200": 8,
        },
        "register_type": "holding_registers",
        **_UART_RISK,
    },
    "uart_0_parity": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_0_parity",
        "states": {"none": 0, "even": 1, "odd": 2},
        "register_type": "holding_registers",
        **_UART_RISK,
    },
    "uart_0_stop": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_0_stop",
        "states": {"one": 0, "two": 1},
        "register_type": "holding_registers",
        **_UART_RISK,
    },
    "uart_1_baud": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_1_baud",
        "states": {
            "baud_4800": 0,
            "baud_9600": 1,
            "baud_14400": 2,
            "baud_19200": 3,
            "baud_28800": 4,
            "baud_38400": 5,
            "baud_57600": 6,
            "baud_76800": 7,
            "baud_115200": 8,
        },
        "register_type": "holding_registers",
        **_UART_RISK,
    },
    "uart_1_parity": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_1_parity",
        "states": {"none": 0, "even": 1, "odd": 2},
        "register_type": "holding_registers",
        **_UART_RISK,
    },
    "uart_1_stop": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_1_stop",
        "states": {"one": 0, "two": 1},
        "register_type": "holding_registers",
        **_UART_RISK,
    },
}

__all__ = ["UART_SELECT_ENTITY_MAPPINGS"]
