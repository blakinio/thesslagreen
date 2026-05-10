"""Compatibility shim: config flow schema helpers moved to _config_flow.schema."""

from __future__ import annotations

from ._config_flow.schema import (
    build_connection_schema,
    build_reconfigure_schema,
)

__all__ = [
    "build_connection_schema",
    "build_reconfigure_schema",
]
