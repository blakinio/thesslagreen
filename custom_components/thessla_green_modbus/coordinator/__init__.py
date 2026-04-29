"""Coordinator package public API."""

from .coordinator import (
    CoordinatorConfig,
    ThesslaGreenModbusCoordinator,
    _PermanentModbusError,
    get_register_definition,
)

__all__ = [
    "CoordinatorConfig",
    "ThesslaGreenModbusCoordinator",
    "_PermanentModbusError",
    "get_register_definition",
]
