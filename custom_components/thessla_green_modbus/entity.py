"""Base entity for ThesslaGreen Modbus Integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator


class ThesslaGreenEntity(CoordinatorEntity[ThesslaGreenModbusCoordinator]):
    """Base entity for ThesslaGreen devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ThesslaGreenModbusCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = key
        # Home Assistant reads ``_attr_device_info`` directly during entity
        # setup; keeping this attribute avoids additional property wrappers.
        self._attr_device_info = coordinator.get_device_info()  # pragma: no cover

    @property
    def unique_id(self) -> str:
        """Return unique ID for this entity."""
        host = self.coordinator.host.replace(":", "-")
        return (
            f"{DOMAIN}_{host}_{self.coordinator.port}_"
            f"{self.coordinator.slave_id}_{self._key}"
        )

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
