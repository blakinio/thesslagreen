"""Base entity for ThesslaGreen Modbus Integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_AIRFLOW_UNIT,
    DEFAULT_AIRFLOW_UNIT,
    AIRFLOW_RATE_REGISTERS,
    AIRFLOW_UNIT_M3H,
)  # noqa: F401
    AIRFLOW_RATE_REGISTERS,
    AIRFLOW_UNIT_M3H,
    CONF_AIRFLOW_UNIT,
    DEFAULT_AIRFLOW_UNIT,
    DOMAIN,
)
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
        host = self.coordinator.host.replace(":", "-")

        base = (
            f"{DOMAIN}_{host}_{self.coordinator.port}_"
            f"{self.coordinator.slave_id}_{self._key}"
        )
        return base



        base = f"{DOMAIN}_{host}_{self.coordinator.port}_{self.coordinator.slave_id}_{self._key}"
        airflow_unit = getattr(getattr(self.coordinator, "entry", None), "options", {}).get(
            CONF_AIRFLOW_UNIT,
            DEFAULT_AIRFLOW_UNIT,
        )
        if self._key in AIRFLOW_RATE_REGISTERS and airflow_unit == AIRFLOW_UNIT_M3H:
            # unique ID should remain consistent regardless of airflow unit
            return base
        return base

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get(self._key) is not None
        )
