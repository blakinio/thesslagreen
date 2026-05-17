"""Shared Modbus client/transport factories for device-client tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.thessla_green_modbus.core.client import ThesslaGreenDeviceClient
from custom_components.thessla_green_modbus.core.models import CoordinatorConfig


def make_config(**kwargs) -> CoordinatorConfig:
    """Return a CoordinatorConfig with test-friendly defaults.

    All keyword arguments override the defaults and are forwarded to
    ``CoordinatorConfig.__init__``.
    """
    defaults: dict = dict(
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test-device",
        timeout=5,
        retry=3,
        scan_interval=30,
    )
    defaults.update(kwargs)
    return CoordinatorConfig(**defaults)


def make_client(**kwargs) -> ThesslaGreenDeviceClient:
    """Return a ThesslaGreenDeviceClient with test-friendly defaults.

    All keyword arguments are forwarded to ``ThesslaGreenDeviceClient.__init__``.
    The ``config`` and ``hass`` arguments default to values produced by
    :func:`make_config` and a fresh ``MagicMock`` respectively.
    """
    config = make_config()
    hass = MagicMock()
    return ThesslaGreenDeviceClient(
        config,
        hass=hass,
        effective_batch=100,
        resolved_connection_mode=None,
        backoff=0.5,
        backoff_jitter=None,
        **kwargs,
    )
