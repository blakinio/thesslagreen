"""Config-backed property accessors mixin for coordinator.

Retained properties (host, port) are used by services/handlers_data.py.
Removed properties (slave_id, connection_type, connection_mode, serial_port,
baud_rate, parity, stop_bits) had zero external call sites — callers use
``coordinator.device_client.config.X`` or ``coordinator.device_client.slave_id``
directly.
"""

from __future__ import annotations


class _CoordinatorConfigPropertiesMixin:
    """Thin property accessors that delegate to ``self.device_client.config``."""

    @property
    def host(self) -> str:
        """Host accessor backed by CoordinatorConfig."""
        return self.device_client.config.host

    @host.setter
    def host(self, value: str) -> None:
        self.device_client.config.host = value

    @property
    def port(self) -> int:
        """Port accessor backed by CoordinatorConfig."""
        return self.device_client.config.port

    @port.setter
    def port(self, value: int) -> None:
        self.device_client.config.port = value
