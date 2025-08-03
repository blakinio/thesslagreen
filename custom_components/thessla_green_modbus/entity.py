"""Base entity for ThesslaGreen Modbus Integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenCoordinator


class ThesslaGreenEntity(CoordinatorEntity[ThesslaGreenCoordinator]):
    """Base entity for ThesslaGreen devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ThesslaGreenCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = key
        
        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            name=device_name,
            manufacturer="ThesslaGreen",
            model="AirPack",
            sw_version=device_info.get("firmware", "Unknown"),
        )

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