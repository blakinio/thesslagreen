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
        self._attr_device_info = coordinator.get_device_info()

    @property
    def unique_id(self) -> str:
        """Return unique ID for this entity."""
        return f"{DOMAIN}_{self.coordinator.host}_{self.coordinator.slave_id}_{self._key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get(self._key) is not None
        )
