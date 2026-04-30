"""Coordinator setup/lifecycle orchestration helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from ..const import CONNECTION_TYPE_RTU

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])


def resolve_setup_endpoint(coordinator: ThesslaGreenModbusCoordinator) -> str:
    """Return user-friendly endpoint string for setup logs."""
    if coordinator.config.connection_type == CONNECTION_TYPE_RTU:
        return coordinator.config.serial_port or "serial"
    return f"{coordinator.config.host}:{coordinator.config.port}"


async def async_setup(coordinator: ThesslaGreenModbusCoordinator) -> bool:
    """Perform coordinator setup lifecycle without changing coordinator state contract."""
    endpoint = resolve_setup_endpoint(coordinator)
    _LOGGER.info(
        "Setting up ThesslaGreen coordinator for %s via %s",
        endpoint,
        coordinator.config.connection_type.upper(),
    )

    await coordinator._prepare_registers_for_setup()
    coordinator._warn_missing_device_info()
    coordinator._compute_register_groups()
    await coordinator._test_connection()

    if coordinator._stop_listener is None and hasattr(coordinator.hass, "bus"):
        coordinator._stop_listener = coordinator.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, coordinator._async_handle_stop
        )

    return True
