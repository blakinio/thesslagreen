"""Config-backed property accessors mixin for coordinator.

Retained properties (host, port, slave_id) are used by entity platforms,
services, core IO modules, and tests.  Removed properties
(connection_type, connection_mode, serial_port, baud_rate, parity,
stop_bits) had zero external call sites — callers already use
``coordinator.device_client.config.X`` directly.
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

    @property
    def slave_id(self) -> int:
        """Slave ID accessor backed by CoordinatorConfig."""
        return self.device_client.config.slave_id

    @slave_id.setter
    def slave_id(self, value: int) -> None:
        self.device_client.config.slave_id = value
