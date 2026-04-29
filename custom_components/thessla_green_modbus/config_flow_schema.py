"""Schema builders used by config flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .config_flow_options import denormalize_option
from .const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_TYPE,
    CONF_DEEP_SCAN,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_DEEP_SCAN,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SERIAL_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOP_BITS,
    DOMAIN,
    MAX_BATCH_REGISTERS,
)
from .utils import resolve_connection_settings


def _option_default(prefix: str, options: list[Any], value: Any, fallback: Any) -> Any:
    target = value if value not in (None, "") else fallback
    candidate = denormalize_option(prefix, target)
    if options and candidate in options:
        return candidate
    if options:
        return options[0]
    return target


def _resolve_defaults(
    current_values: dict[str, Any], discovered_host: str | None
) -> dict[str, Any]:
    """Resolve normalized defaults used by schema sections."""
    connection_default = current_values.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    port_default = current_values.get(CONF_PORT, DEFAULT_PORT)
    normalized_type, resolved_mode = resolve_connection_settings(
        connection_default,
        current_values.get("connection_mode"),
        port_default,
    )
    if normalized_type == CONNECTION_TYPE_TCP and resolved_mode == "tcp_rtu":
        connection_default = CONNECTION_TYPE_TCP_RTU
    else:
        connection_default = normalized_type
    return {
        "connection_default": connection_default,
        "host_default": current_values.get(CONF_HOST, discovered_host or ""),
        "port_default": port_default,
        "slave_default": current_values.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
        "serial_port_default": current_values.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT),
    }


def _build_connection_type_field(connection_default: str) -> dict[Any, Any]:
    return {
        vol.Required(
            CONF_CONNECTION_TYPE,
            default=connection_default,
            description={
                "selector": {
                    "select": {
                        "options": [
                            {"value": CONNECTION_TYPE_TCP, "label": f"{DOMAIN}.connection_type_tcp"},
                            {
                                "value": CONNECTION_TYPE_TCP_RTU,
                                "label": f"{DOMAIN}.connection_type_tcp_rtu",
                            },
                            {"value": CONNECTION_TYPE_RTU, "label": f"{DOMAIN}.connection_type_rtu"},
                        ]
                    }
                }
            },
        ): vol.In({CONNECTION_TYPE_TCP, CONNECTION_TYPE_TCP_RTU, CONNECTION_TYPE_RTU})
    }


def _build_tcp_fields(host_default: str, port_default: int) -> dict[Any, Any]:
    return {
        vol.Required(CONF_HOST, default=host_default): str,
        vol.Required(CONF_PORT, default=port_default): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }


def _build_rtu_fields(
    serial_port_default: str,
    *,
    baud_default: Any,
    baud_validator: Any,
    parity_default: Any,
    parity_validator: Any,
    stop_bits_default: Any,
    stop_bits_validator: Any,
) -> dict[Any, Any]:
    return {
        vol.Required(CONF_SERIAL_PORT, default=serial_port_default): str,
        vol.Required(CONF_BAUD_RATE, default=baud_default): baud_validator,
        vol.Required(CONF_PARITY, default=parity_default): parity_validator,
        vol.Required(CONF_STOP_BITS, default=stop_bits_default): stop_bits_validator,
    }


def build_connection_schema(
    defaults: dict[str, Any],
    *,
    discovered_host: str | None = None,
    modbus_baud_rates: list[int] | None = None,
    modbus_parity: list[str] | None = None,
    modbus_stop_bits: list[str] | None = None,
) -> vol.Schema:
    """Return schema for connection details with provided defaults."""
    current_values = defaults or {}

    resolved_defaults = _resolve_defaults(current_values, discovered_host)
    connection_default = resolved_defaults["connection_default"]
    host_default = resolved_defaults["host_default"]
    port_default = resolved_defaults["port_default"]
    slave_default = resolved_defaults["slave_default"]
    serial_port_default = resolved_defaults["serial_port_default"]

    baud_options = modbus_baud_rates if modbus_baud_rates is not None else []
    parity_options = modbus_parity if modbus_parity is not None else []
    stop_bits_options = modbus_stop_bits if modbus_stop_bits is not None else []

    baud_default = _option_default(
        "modbus_baud_rate_",
        baud_options,
        current_values.get(CONF_BAUD_RATE),
        DEFAULT_BAUD_RATE,
    )
    parity_default = _option_default(
        "modbus_parity_",
        parity_options,
        current_values.get(CONF_PARITY),
        DEFAULT_PARITY,
    )
    stop_bits_default = _option_default(
        "modbus_stop_bits_",
        stop_bits_options,
        current_values.get(CONF_STOP_BITS),
        DEFAULT_STOP_BITS,
    )

    if not baud_options:
        try:
            baud_default = int(baud_default)
        except (TypeError, ValueError):
            baud_default = DEFAULT_BAUD_RATE
    if not parity_options:
        parity_default = str(parity_default)
    if not stop_bits_options:
        stop_bits_default = str(stop_bits_default)

    baud_validator: Any = (
        vol.In(baud_options)
        if baud_options
        else vol.All(vol.Coerce(int), vol.Range(min=1200, max=230400))
    )
    parity_validator: Any = (
        vol.In(parity_options) if parity_options else vol.In(["none", "even", "odd"])
    )
    stop_bits_validator: Any = (
        vol.In(stop_bits_options) if stop_bits_options else vol.In(["1", "2"])
    )

    data_schema: dict[Any, Any] = {
        **_build_connection_type_field(connection_default),
        vol.Required(CONF_SLAVE_ID, default=slave_default): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=247)
        ),
        vol.Optional(CONF_NAME, default=current_values.get(CONF_NAME, DEFAULT_NAME)): str,
        vol.Optional(
            CONF_DEEP_SCAN,
            default=current_values.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN),
            description={"advanced": True},
        ): bool,
        vol.Optional(
            CONF_MAX_REGISTERS_PER_REQUEST,
            default=current_values.get(
                CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
            ),
            description={"selector": {"number": {"min": 1, "max": MAX_BATCH_REGISTERS, "step": 1}}},
        ): int,
    }

    if connection_default in (CONNECTION_TYPE_TCP, CONNECTION_TYPE_TCP_RTU):
        data_schema.update(_build_tcp_fields(host_default, port_default))
    else:
        data_schema.update(
            _build_rtu_fields(
                serial_port_default,
                baud_default=baud_default,
                baud_validator=baud_validator,
                parity_default=parity_default,
                parity_validator=parity_validator,
                stop_bits_default=stop_bits_default,
                stop_bits_validator=stop_bits_validator,
            )
        )

    return vol.Schema(data_schema)
