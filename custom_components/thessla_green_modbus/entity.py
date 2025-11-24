"""Base entity classes for ThesslaGreen Modbus integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import device_unique_id_prefix
from .coordinator import ThesslaGreenModbusCoordinator


class ThesslaGreenEntity(CoordinatorEntity[ThesslaGreenModbusCoordinator]):
    """Base entity for ThesslaGreen devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        key: str,
        address: int,
        *,
        bit: int | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = key
        self._address = address
        self._bit = bit
        # Home Assistant reads ``_attr_device_info`` directly during entity
        # setup; keeping this attribute avoids additional property wrappers.
        self._attr_device_info = coordinator.get_device_info()  # pragma: no cover

    @property
    def unique_id(self) -> str:
        """Return unique ID for this entity."""
        bit_suffix = f"_bit{self._bit}" if self._bit is not None else ""
        device_info = getattr(self.coordinator, "device_info", {}) or {}
        serial_number = device_info.get("serial_number")
        prefix = device_unique_id_prefix(
            serial_number,
            getattr(self.coordinator, "host", ""),
            getattr(self.coordinator, "port", 0),
        )
        return f"{prefix}_{self.coordinator.slave_id}_{self._key}_{self._address}{bit_suffix}"

    @property
    def available(self) -> bool:  # pragma: no cover
        """Return if entity is available.

        This property forms part of the entity API and is queried by Home
        Assistant even though it is not referenced in the codebase.
        """
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get(self._key) is not None
        )
