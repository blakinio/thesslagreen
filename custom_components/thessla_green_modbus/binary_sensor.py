"""Binary sensor platform for the ThesslaGreen Modbus integration.

Entities are created dynamically based on the registers reported by the
device scanner. Only registers available on the target device are exposed
as binary sensor entities.
"""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capability_rules import capability_block_reason
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .mappings import BINARY_SENSOR_ENTITY_MAPPINGS

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

BINARY_SENSOR_DEFINITIONS: dict[str, dict[str, Any]] = BINARY_SENSOR_ENTITY_MAPPINGS
LEGACY_PROBLEM_KEY_PATTERN = re.compile(r"^problem(?:_\d+)?$")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen binary sensor entities."""
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data

    entities = []
    skipped_stale_problem = 0

    for key, sensor_def in BINARY_SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]
        register_name = sensor_def.get("register", key)
        if LEGACY_PROBLEM_KEY_PATTERN.fullmatch(register_name):
            _LOGGER.debug(
                "Skipping stale binary sensor key '%s' during entity creation",
                register_name,
            )
            skipped_stale_problem += 1
            continue

        if reason := capability_block_reason(register_name, coordinator.device_client.capabilities):
            _LOGGER.info("Entity skipped due to capability: %s (%s)", register_name, reason)
            continue

        register_map = coordinator.device_client.get_register_map(register_type)
        available = coordinator.device_client.available_registers.get(register_type, set())
        force_create = (
            coordinator.device_client.force_full_register_list and register_name in register_map
        )

        if register_name in available or force_create:
            address = register_map.get(register_name)
            if address is None:
                _LOGGER.warning("No address for binary sensor: %s, skipping", register_name)
                continue
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator,
                    register_name,
                    address,
                    sensor_def,
                )
            )
            _LOGGER.debug("Created binary sensor: %s", sensor_def["translation_key"])

    if entities:
        # The coordinator has completed its first refresh before platforms are
        # forwarded; per-entity initial updates only duplicate Modbus traffic.
        async_add_entities(entities, False)
        _LOGGER.debug(
            "Created %d binary sensor entities for %s",
            len(entities),
            coordinator.device_client.device_name,
        )
        if skipped_stale_problem:
            _LOGGER.info(
                "Skipped %d stale problem_* binary sensor keys during setup",
                skipped_stale_problem,
            )
    else:
        _LOGGER.warning("No binary sensor entities created - no compatible registers found")


class ThesslaGreenBinarySensor(ThesslaGreenEntity, BinarySensorEntity):
    """Binary sensor entity for ThesslaGreen device."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        address: int,
        sensor_definition: dict[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            coordinator,
            register_name,
            address,
            bit=sensor_definition.get("bit"),
        )

        self._register_name = register_name
        self._sensor_def = sensor_definition
        self._attr_icon = sensor_definition.get("icon")
        self._attr_device_class: BinarySensorDeviceClass | None = sensor_definition.get(
            "device_class"
        )

        _ec = sensor_definition.get("entity_category")
        self._attr_entity_category = EntityCategory(_ec) if _ec else None
        if self._attr_entity_category is EntityCategory.DIAGNOSTIC:
            self._attr_entity_registry_enabled_default = False

        self._attr_translation_key = sensor_definition.get("translation_key")

        _LOGGER.debug(
            "Binary sensor initialized: %s (%s)",
            sensor_definition.get("translation_key"),
            register_name,
        )

    @property
    def suggested_object_id(self) -> str:
        """Return bit-specific object ID for bitmask sensors, register key otherwise."""
        tk = self._attr_translation_key
        if tk and tk != self._key:
            return str(tk)
        return super().suggested_object_id

    _DIAG_PREFIXES = ("s_", "e_", "f_")
    _DIAG_NAMES: ClassVar[frozenset[str]] = frozenset({"alarm", "error"})

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._register_name in self._DIAG_NAMES or self._register_name.startswith(
            self._DIAG_PREFIXES
        ):
            return self.coordinator.last_update_success and not getattr(
                self.coordinator.device_client, "offline_state", False
            )
        return super().available

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        value = self.coordinator.data.get(self._register_name)

        if value is None:
            return None

        register_type = self._sensor_def["register_type"]
        bit = self._sensor_def.get("bit")

        if register_type in ["coil_registers", "discrete_inputs"]:
            result = bool(value)
        elif register_type == "input_registers":
            result = bool(value & bit) if bit is not None else bool(value)
        elif register_type == "holding_registers":
            result = bool(value & bit) if bit is not None else bool(value)
        else:
            result = False

        if self._sensor_def.get("inverted"):
            return not result
        return result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}

        if self.coordinator.device_client.device_scan_result:
            attrs["register_name"] = self._register_name
            attrs["register_type"] = self._sensor_def["register_type"]

        raw_value = self.coordinator.data.get(self._register_name)
        if raw_value is not None:
            attrs["raw_value"] = raw_value
            if self._sensor_def.get("bitmask") and self._sensor_def.get("bit") is None:
                attrs["bitmask"] = raw_value

        if (
            "alarm" in self._register_name
            or "error" in self._register_name
            or self._register_name.startswith(("s_", "e_"))
        ):
            if self.is_on is not None:
                attrs["severity"] = "warning" if self.is_on else "normal"

        return attrs

    @property
    def icon(self) -> str:
        """Return the icon for the binary sensor."""
        base_icon = self._attr_icon if isinstance(self._attr_icon, str) else None

        if base_icon and self._register_name in [
            "bypass",
            "gwc",
            "power_supply_fans",
            "heating_cable",
        ]:
            if self.is_on:
                return base_icon
            if "fan" in base_icon:
                return base_icon.replace("fan", "fan-off")
            if "heating" in base_icon:
                return "mdi:radiator-off"
            if "pipe" in base_icon:
                return "mdi:pipe"

        if (
            "alarm" in self._register_name
            or "error" in self._register_name
            or self._register_name.startswith(("s_", "e_"))
        ):
            if self.is_on is None:
                return "mdi:help-circle"
            return "mdi:alert-circle" if self.is_on else "mdi:check-circle"

        return base_icon or "mdi:fan-off"
