"""Validation helpers for config flow payloads and scan results."""

from __future__ import annotations

import dataclasses
import ipaddress
import logging
from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.util.network import is_host_valid
from voluptuous import Invalid as VOL_INVALID

from .const import (
    CONF_BAUD_RATE,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    DEFAULT_BAUD_RATE,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SERIAL_PORT,
    DEFAULT_STOP_BITS,
)
from .errors import CannotConnect


def validate_slave_id(data: dict[str, Any]) -> int:
    """Validate and normalize ``slave_id`` in config payload."""
    try:
        slave_id = int(data[CONF_SLAVE_ID])
    except (KeyError, TypeError, ValueError) as exc:
        raise VOL_INVALID("invalid_slave", path=[CONF_SLAVE_ID]) from exc
    if slave_id < 0:
        raise VOL_INVALID("invalid_slave_low", path=[CONF_SLAVE_ID])
    if slave_id > 247:
        raise VOL_INVALID("invalid_slave_high", path=[CONF_SLAVE_ID])
    data[CONF_SLAVE_ID] = slave_id
    return slave_id


def validate_tcp_config(
    data: dict[str, Any],
    *,
    looks_like_hostname: callable,
) -> tuple[str, int]:
    """Validate and normalize TCP connection fields."""
    host = str(data.get(CONF_HOST, "") or "").strip()
    if not host:
        raise VOL_INVALID("missing_host", path=[CONF_HOST])

    port_raw = data.get(CONF_PORT, DEFAULT_PORT)
    try:
        port = int(port_raw)
    except (TypeError, ValueError) as exc:
        raise VOL_INVALID("invalid_port", path=[CONF_PORT]) from exc
    if not 1 <= port <= 65535:
        raise VOL_INVALID("invalid_port", path=[CONF_PORT])

    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not looks_like_hostname(host):
            raise VOL_INVALID("invalid_host", path=[CONF_HOST]) from None
        if not is_host_valid(host):
            raise VOL_INVALID("invalid_host", path=[CONF_HOST]) from None

    data[CONF_HOST] = host
    data[CONF_PORT] = port
    data.pop(CONF_SERIAL_PORT, None)
    data.pop(CONF_BAUD_RATE, None)
    data.pop(CONF_PARITY, None)
    data.pop(CONF_STOP_BITS, None)
    return host, port


def validate_rtu_config(
    data: dict[str, Any],
    *,
    normalize_baud_rate: callable,
    normalize_parity: callable,
    normalize_stop_bits: callable,
) -> None:
    """Validate and normalize RTU serial fields."""
    serial_port = str(data.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT) or "").strip()
    if not serial_port:
        raise VOL_INVALID("invalid_serial_port", path=[CONF_SERIAL_PORT])
    data[CONF_SERIAL_PORT] = serial_port

    try:
        baud_rate = normalize_baud_rate(data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE))
    except ValueError as err:
        raise VOL_INVALID("invalid_baud_rate", path=[CONF_BAUD_RATE]) from err
    data[CONF_BAUD_RATE] = baud_rate

    try:
        parity = normalize_parity(data.get(CONF_PARITY, DEFAULT_PARITY))
    except ValueError as err:
        raise VOL_INVALID("invalid_parity", path=[CONF_PARITY]) from err
    data[CONF_PARITY] = parity

    try:
        stop_bits = normalize_stop_bits(data.get(CONF_STOP_BITS, DEFAULT_STOP_BITS))
    except ValueError as err:
        raise VOL_INVALID("invalid_stop_bits", path=[CONF_STOP_BITS]) from err
    data[CONF_STOP_BITS] = stop_bits
    data.pop(CONF_HOST, None)
    data.pop(CONF_PORT, None)


def process_scan_capabilities(
    scan_result: dict[str, Any],
    *,
    capabilities_cls: type,
    caps_to_dict: callable,
    logger: logging.Logger,
) -> dict[str, Any]:
    """Extract and validate capabilities from scan result dict."""
    caps_obj = scan_result.get("capabilities")
    if caps_obj is None:
        raise CannotConnect("invalid_capabilities")

    if dataclasses.is_dataclass(caps_obj):
        try:
            caps_dict = caps_to_dict(caps_obj)
        except (TypeError, ValueError, AttributeError) as err:
            logger.error("Capabilities missing required fields: %s", err)
            raise CannotConnect("invalid_capabilities") from err
        if isinstance(caps_obj, capabilities_cls):
            required_fields = {
                field.name
                for field in dataclasses.fields(capabilities_cls)
                if not field.name.startswith("_")
            }
            missing = [f for f in required_fields if f not in caps_dict]
            if missing:
                logger.error("Capabilities missing required fields: %s", set(missing))
                raise CannotConnect("invalid_capabilities")
    elif isinstance(caps_obj, dict):
        caps_dict = caps_to_dict(caps_obj)
    else:
        raise CannotConnect("invalid_capabilities")

    return caps_dict
