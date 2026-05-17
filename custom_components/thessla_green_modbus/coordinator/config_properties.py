"""Config-backed property accessors mixin for coordinator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.models import CoordinatorConfig


class _CoordinatorConfigPropertiesMixin:
    """Thin property accessors that delegate to ``self.config``."""

    config: CoordinatorConfig

    @property
    def host(self) -> str:
        """Host accessor backed by CoordinatorConfig."""
        return self.config.host

    @host.setter
    def host(self, value: str) -> None:
        self.config.host = value

    @property
    def port(self) -> int:
        """Port accessor backed by CoordinatorConfig."""
        return self.config.port

    @port.setter
    def port(self, value: int) -> None:
        self.config.port = value

    @property
    def slave_id(self) -> int:
        """Slave ID accessor backed by CoordinatorConfig."""
        return self.config.slave_id

    @slave_id.setter
    def slave_id(self, value: int) -> None:
        self.config.slave_id = value

    @property
    def connection_type(self) -> str:
        """Connection type accessor backed by CoordinatorConfig."""
        return self.config.connection_type

    @connection_type.setter
    def connection_type(self, value: str) -> None:
        self.config.connection_type = value

    @property
    def connection_mode(self) -> str | None:
        """Connection mode accessor backed by CoordinatorConfig."""
        return self.config.connection_mode

    @connection_mode.setter
    def connection_mode(self, value: str | None) -> None:
        self.config.connection_mode = value

    @property
    def serial_port(self) -> str:
        """Serial port accessor backed by CoordinatorConfig."""
        return self.config.serial_port

    @serial_port.setter
    def serial_port(self, value: str) -> None:
        self.config.serial_port = value

    @property
    def baud_rate(self) -> int:
        """Baud rate accessor backed by CoordinatorConfig."""
        return self.config.baud_rate

    @baud_rate.setter
    def baud_rate(self, value: int) -> None:
        self.config.baud_rate = value

    @property
    def parity(self) -> str:
        """Parity accessor backed by CoordinatorConfig."""
        return self.config.parity

    @parity.setter
    def parity(self, value: str) -> None:
        self.config.parity = value

    @property
    def stop_bits(self) -> int:
        """Stop bits accessor backed by CoordinatorConfig."""
        return self.config.stop_bits

    @stop_bits.setter
    def stop_bits(self, value: int) -> None:
        self.config.stop_bits = value
