"""Base entity for TeslaGreen Modbus Integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_INFO
from .coordinator import TeslaGreenCoordinator


class TeslaGreenEntity(CoordinatorEntity[TeslaGreenCoordinator]):
    """Base entity for TeslaGreen devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TeslaGreenCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(**DEVICE_INFO)
        self._key = key

    @property
    def unique_id(self) -> str:
        """Return unique ID for this entity."""
        return f"{DOMAIN}_{self.coordinator.entry.entry_id}_{self._key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get(self._key) is not None
        )
