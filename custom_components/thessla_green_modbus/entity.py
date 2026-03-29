"""Base entity classes for ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.helpers import update_coordinator as update_coordinator_helper

CoordinatorEntity = getattr(update_coordinator_helper, "CoordinatorEntity", object)

from .const import device_unique_id_prefix
from .coordinator import ThesslaGreenModbusCoordinator


class ThesslaGreenEntity(CoordinatorEntity):
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
        try:
            super().__init__(coordinator)
        except TypeError:
            try:
                super().__init__()
            except TypeError:
                _LOGGER.debug("CoordinatorEntity MRO fallback: super().__init__() also failed")
            self.coordinator = coordinator
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
        addr_part = "calc" if self._address is None else self._address
        return f"{prefix}_{self.coordinator.slave_id}_{self._key}_{addr_part}{bit_suffix}"

    @property
    def available(self) -> bool:  # pragma: no cover
        """Return if entity is available.

        This property forms part of the entity API and is queried by Home
        Assistant even though it is not referenced in the codebase.
        """
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get(self._key) is not None
            and not getattr(self.coordinator, "offline_state", False)
        )
