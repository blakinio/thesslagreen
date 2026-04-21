"""Payload normalization helpers for config flow."""

from __future__ import annotations

import dataclasses
from typing import Any

from voluptuous import Invalid as VOL_INVALID

from .const import (
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
    DEFAULT_CONNECTION_TYPE,
)


def caps_to_dict(obj: Any) -> dict[str, Any]:
    """Return a JSON-serializable dict from a capabilities object."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        data = dict(obj.as_dict()) if hasattr(obj, "as_dict") else dataclasses.asdict(obj)
    elif hasattr(obj, "as_dict"):
        data = obj.as_dict()
    elif isinstance(obj, dict):
        data = dict(obj)
    else:
        data = {k: v for k, v in getattr(obj, "__dict__", {}).items()}

    for key, value in list(data.items()):
        if isinstance(value, set):
            data[key] = sorted(value)
    return data


def normalize_connection_type(data: dict[str, Any]) -> str:
    """Normalize connection_type in data dict and return canonical type."""
    connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    if connection_type not in (CONNECTION_TYPE_TCP, CONNECTION_TYPE_TCP_RTU, CONNECTION_TYPE_RTU):
        raise VOL_INVALID("invalid_transport", path=[CONF_CONNECTION_TYPE])
    if connection_type == CONNECTION_TYPE_TCP_RTU:
        data[CONF_CONNECTION_TYPE] = CONNECTION_TYPE_TCP
        data[CONF_CONNECTION_MODE] = CONNECTION_MODE_TCP_RTU
        return str(CONNECTION_TYPE_TCP)
    if connection_type == CONNECTION_TYPE_TCP:
        data[CONF_CONNECTION_TYPE] = CONNECTION_TYPE_TCP
        data.pop(CONF_CONNECTION_MODE, None)
        return str(CONNECTION_TYPE_TCP)
    data[CONF_CONNECTION_TYPE] = CONNECTION_TYPE_RTU
    data.pop(CONF_CONNECTION_MODE, None)
    return str(CONNECTION_TYPE_RTU)
