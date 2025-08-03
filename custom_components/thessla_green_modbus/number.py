"""Number platform for ThesslaGreen Modbus Integration."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen number entities."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())

    # Air flow rate controls
    if "air_flow_rate_manual" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "air_flow_rate_manual",
                "Rekuperator prędkość",
                "mdi:fan",
                10,
                100,
                1,
                PERCENTAGE,
            )
        )

    if "air_flow_rate_temporary" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "air_flow_rate_temporary",
                "Intensywność chwilowy",
                "mdi:fan-speed-3",
                10,
                100,
                1,
                PERCENTAGE,
            )
        )

    # Temperature controls
    if "supply_air_temperature_manual" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "supply_air_temperature_manual",
                "Temperatura nawiewu manualny",
                "mdi:thermometer",
                20,
                45,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    if "supply_air_temperature_temporary" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "supply_air_temperature_temporary",
                "Temperatura nawiewu chwilowy",
                "mdi:thermometer-lines",
                20,
                45,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    # AirS panel settings
    if "fan_speed_1_coef" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "fan_speed_1_coef",
                "AirS 1 bieg",
                "mdi:fan-speed-1",
                10,
                45,
                1,
                PERCENTAGE,
            )
        )

    if "fan_speed_2_coef" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "fan_speed_2_coef",
                "AirS 2 bieg",
                "mdi:fan-speed-2",
                46,
                75,
                1,
                PERCENTAGE,
            )
        )

    if "fan_speed_3_coef" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "fan_speed_3_coef",
                "AirS 3 bieg",
                "mdi:fan-speed-3",
                76,
                100,
                1,
                PERCENTAGE,
            )
        )

    # ========================================
    # BYPASS SYSTEM PARAMETERS (NOWE!)
    # ========================================
    
    # Minimalna temperatura bypass
    if "min_bypass_temperature" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "min_bypass_temperature",
                "Bypass - Min. temperatura zewn.",
                "mdi:thermometer-low",
                10,
                40,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    # Temperatura FreeHeating
    if "air_temperature_summer_free_heating" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "air_temperature_summer_free_heating",
                "Bypass - Temperatura FreeHeating",
                "mdi:thermometer-plus",
                30,
                60,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    # Temperatura FreeCooling  
    if "air_temperature_summer_free_cooling" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "air_temperature_summer_free_cooling", 
                "Bypass - Temperatura FreeCooling",
                "mdi:thermometer-minus",
                30,
                60,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    # Różnicowanie strumieni bypass
    if "bypass_coef1" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "bypass_coef1",
                "Bypass - Różnicowanie strumieni",
                "mdi:valve",
                10,
                100,
                1,
                PERCENTAGE,
            )
        )

    # Intensywność bypass
    if "bypass_coef2" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "bypass_coef2",
                "Bypass - Intensywność nawiewu",
                "mdi:valve-open",
                10,
                150,
                1,
                PERCENTAGE,
            )
        )

    # ========================================
    # GWC SYSTEM PARAMETERS (BONUS)
    # ========================================
    
    # Min temperatura GWC (zima)
    if "min_gwc_air_temperature" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "min_gwc_air_temperature",
                "GWC - Min. temperatura (zima)",
                "mdi:heat-pump",
                0,
                20,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    # Max temperatura GWC (lato)
    if "max_gwc_air_temperature" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "max_gwc_air_temperature",
                "GWC - Max. temperatura (lato)",
                "mdi:heat-pump",
                30,
                80,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    # Różnica temperatur GWC regeneracji
    if "delta_t_gwc" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "delta_t_gwc",
                "GWC - Różnica temp. regeneracji",
                "mdi:thermometer-chevron-up",
                0,
                10,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    # Czas regeneracji GWC
    if "gwc_regen_period" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "gwc_regen_period",
                "GWC - Czas regeneracji",
                "mdi:timer",
                4,
                8,
                1,
                "h",  # godziny
            )
        )

    # Special function coefficients (pozostałe bez zmian)
    special_coeffs = [
        ("hood_supply_coef", "Intensywność OKAP nawiew", "mdi:kitchen", 100, 150),
        ("hood_exhaust_coef", "Intensywność OKAP wywiew", "mdi:kitchen", 100, 150),
        ("fireplace_supply_coef", "Różnicowanie KOMINEK", "mdi:fireplace", 5, 50),
        ("airing_coef", "Intensywność WIETRZENIE", "mdi:fan-auto", 100, 150),
        ("contamination_coef", "Intensywność czujnik jakości", "mdi:air-filter", 100, 150),
        ("empty_house_coef", "Intensywność PUSTY DOM", "mdi:home-minus", 10, 50),
    ]

    for reg_name, name, icon, min_val, max_val in special_coeffs:
        if reg_name in holding_regs:
            entities.append(
                ThesslaGreenNumber(
                    coordinator,
                    reg_name,
                    name,
                    icon,
                    min_val,
                    max_val,
                    1,
                    PERCENTAGE,
                )
            )

    if entities:
        _LOGGER.debug("Adding %d number entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenNumber(CoordinatorEntity, NumberEntity):
    """ThesslaGreen number entity."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        min_value: float,
        max_value: float,
        step: float,
        unit: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit

        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None

        # Temperature values are stored with 0.5°C resolution
        if "temperature" in self._key:
            return value * 0.5

        # Direct values for percentages and other numbers
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        # Temperature values need to be converted (x2 for 0.5°C resolution)
        if "temperature" in self._key:
            modbus_value = int(value * 2)
        else:
            modbus_value = int(value)

        success = await self.coordinator.async_write_register(self._key, modbus_value)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s to %s", self._key, value)
