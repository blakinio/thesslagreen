"""Facade module re-exporting grouped service registration helpers."""

from .services_handler_deps import ServiceHandlerDeps
from .services_handlers_data import register_data_services
from .services_handlers_maintenance import register_maintenance_services
from .services_handlers_mode import register_mode_services
from .services_handlers_parameters import register_parameter_services
from .services_handlers_schedule import register_schedule_services

__all__ = [
    "ServiceHandlerDeps",
    "register_mode_services",
    "register_schedule_services",
    "register_parameter_services",
    "register_maintenance_services",
    "register_data_services",
]
