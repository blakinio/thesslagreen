"""Base entity classes for ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MAX_VENTILATION_PERCENT, device_unique_id_prefix
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)


class ThesslaGreenEntity(CoordinatorEntity):
    """Base entity for ThesslaGreen devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        key: str,
        address: int | None,
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
        self._attr_device_info = coordinator.get_device_info()  # pragma: no cover - defensive

    @property
    def suggested_object_id(self) -> str:
        """Return suggested entity object ID based on register key.

        Using the register key (not the translated name) guarantees that
        entity_ids are stable regardless of translation changes and are
        predictable from the register map.
        """
        return self._key

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
    def available(self) -> bool:  # pragma: no cover - defensive
        """Return if entity is available.

        This property forms part of the entity API and is queried by Home
        Assistant even though it is not referenced in the codebase.
        """
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get(self._key) is not None
            and not getattr(self.coordinator, "offline_state", False)
        )

    def _percentage_limits(self) -> tuple[int, int]:
        """Return min/max percentage limits derived from coordinator data."""
        min_pct = self.coordinator.data.get("min_percentage")
        max_pct = self.coordinator.data.get("max_percentage")
        try:
            min_val = int(min_pct)
        except (TypeError, ValueError):
            min_val = 0
        try:
            max_val = int(max_pct)
        except (TypeError, ValueError):
            max_val = MAX_VENTILATION_PERCENT
        min_val = max(0, min_val)
        max_val = min(MAX_VENTILATION_PERCENT, max_val)
        if max_val < min_val:
            max_val = min_val
        return min_val, max_val

    async def _write_register(
        self,
        register_name: str,
        value: Any,
        *,
        offset: int = 0,
        refresh: bool = True,
        include_offset: bool = False,
    ) -> None:
        """Write a register via the coordinator."""
        kwargs: dict[str, Any] = {"refresh": False}
        if include_offset or offset != 0:
            kwargs["offset"] = offset

        success = await self.coordinator.async_write_register(register_name, value, **kwargs)
        if not success:
            raise RuntimeError(f"Failed to write register {register_name}")
        if refresh:
            await self.coordinator.async_request_refresh()
