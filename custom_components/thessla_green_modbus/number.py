"""Number platform for ThesslaGreen Modbus Integration - FIXED VERSION."""
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

    # ====== COMPATIBILITY LAYER FOR OLD ENTITY IDs ======
    # Dodaj stare entity ID dla kompatybilności wstecznej
    if "air_flow_rate_manual" in holding_regs:
        # Główna entytia z nową nazwą
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "air_flow_rate_manual",
                "Intensywność manualny",
                "mdi:fan",
                10,
                100,
                1,
                PERCENTAGE,
            )
        )
        
        # COMPATIBILITY: Dodaj alias z starym entity_id dla kompatybilności
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "air_flow_rate_manual",  # Ten sam rejestr
                "Prędkość rekuperatora",  # Stara nazwa
                "mdi:fan",
                10,
                100,
                1,
                PERCENTAGE,
                custom_entity_id="rekuperator_predkosc"  # Wymuś stary entity_id
            )
        )

    # Air flow rate controls
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

    # Alternative registers from documentation (0x1131, 0x1134)
    if "air_flow_rate_temporary_alt" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "air_flow_rate_temporary_alt",
                "Intensywność chwilowy (alt)",
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

    # Alternative temperature register (0x1134)
    if "supply_air_temperature_temporary_alt" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "supply_air_temperature_temporary_alt",
                "Temperatura nawiewu chwilowy (alt)",
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
    # BYPASS SYSTEM PARAMETERS
    # ========================================
    if "min_bypass_temperature" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "min_bypass_temperature",
                "Bypass - Min. temperatura",
                "mdi:thermometer-low",
                10,
                30,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    if "air_temperature_summer_free_heating" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "air_temperature_summer_free_heating",
                "Bypass - Temperatura FreeHeating",
                "mdi:fire",
                15,
                25,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    if "air_temperature_summer_free_cooling" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "air_temperature_summer_free_cooling",
                "Bypass - Temperatura FreeCooling", 
                "mdi:snowflake",
                20,
                35,
                0.5,
                UnitOfTemperature.CELSIUS,
            )
        )

    if "bypass_coef1" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "bypass_coef1",
                "Bypass - Różnicowanie",
                "mdi:percent",
                0,
                50,
                1,
                PERCENTAGE,
            )
        )

    if "bypass_coef2" in holding_regs:
        entities.append(
            ThesslaGreenNumber(
                coordinator,
                "bypass_coef2",
                "Bypass - Intensywność",
                "mdi:percent",
                50,
                150,
                1,
                PERCENTAGE,
            )
        )

    # ========================================
    # GWC SYSTEM PARAMETERS
    # ========================================
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

    # ========================================
    # SPECIAL FUNCTION COEFFICIENTS
    # ========================================
    special_coeffs = [
        ("hood_supply_coef", "Intensywność OKAP nawiew", "mdi:kitchen", 100, 150),
        ("hood_exhaust_coef", "Intensywność OKAP wywiew", "mdi:kitchen", 100, 150),
        ("fireplace_supply_coef", "Różnicowanie KOMINEK", "mdi:fireplace", 5, 50),
        ("airing_coef", "Intensywność WIETRZENIE", "mdi:fan-auto", 100, 150),
        ("contamination_coef", "Intensywność czujnik jakości", "mdi:air-filter", 100, 150),
        ("empty_house_coef", "Intensywność PUSTY DOM", "mdi:home-minus", 10, 50),
        ("airing_bathroom_coef", "Intensywność WIETRZENIE łazienka", "mdi:shower", 100, 150),
        ("airing_switch_coef", "Intensywność WIETRZENIE przełączniki", "mdi:light-switch", 100, 150),
        ("open_window_coef", "Intensywność OTWARTE OKNA", "mdi:window-open", 50, 150),
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

    # ========================================
    # TIME CONTROL PARAMETERS
    # ========================================
    time_controls = [
        ("airing_panel_mode_time", "Czas WIETRZENIE pokoje", "mdi:timer", 5, 180, "min"),
        ("airing_switch_mode_time", "Czas WIETRZENIE łazienka", "mdi:timer", 5, 180, "min"),
        ("fireplace_mode_time", "Czas działania KOMINEK", "mdi:timer", 10, 240, "min"),
        ("airing_switch_mode_on_delay", "Opóźnienie zał. WIETRZENIE", "mdi:timer-sand", 0, 60, "min"),
        ("airing_switch_mode_off_delay", "Opóźnienie wył. WIETRZENIE", "mdi:timer-sand", 0, 60, "min"),
    ]

    for reg_name, name, icon, min_val, max_val, unit in time_controls:
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
                    unit,
                )
            )

    if entities:
        _LOGGER.debug("Adding %d number entities (including compatibility aliases)", len(entities))
        async_add_entities(entities)


class ThesslaGreenNumber(CoordinatorEntity, NumberEntity):
    """ThesslaGreen number entity with enhanced compatibility."""

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
        custom_entity_id: str = None,  # NEW: Allow custom entity ID
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
        
        # Use custom entity_id if provided for backward compatibility
        if custom_entity_id:
            self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{custom_entity_id}"
            # Force the entity_id pattern for compatibility
            self._attr_entity_id = f"number.{custom_entity_id}"
        else:
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

        # Temperature values are already processed in coordinator (×0.5°C)
        if "temperature" in self._key and ("manual" in self._key or "temporary" in self._key):
            return float(value)  # Already converted in coordinator

        # Special temperature registers (bypass, GWC) are also pre-processed
        if self._key in ["min_bypass_temperature", "air_temperature_summer_free_heating", 
                        "air_temperature_summer_free_cooling", "min_gwc_air_temperature", 
                        "max_gwc_air_temperature", "delta_t_gwc"]:
            return float(value)  # Already converted in coordinator

        # Direct values for percentages and other numbers
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        # Temperature values need to be converted (÷0.5 for Modbus storage)
        if "temperature" in self._key and ("manual" in self._key or "temporary" in self._key):
            modbus_value = int(value * 2)  # Convert to 0.5°C resolution
        elif self._key in ["min_bypass_temperature", "air_temperature_summer_free_heating", 
                          "air_temperature_summer_free_cooling", "min_gwc_air_temperature", 
                          "max_gwc_air_temperature", "delta_t_gwc"]:
            modbus_value = int(value * 2)  # Convert to 0.5°C resolution
        else:
            modbus_value = int(value)

        # Additional validation
        if modbus_value < 0 or modbus_value > 65535:
            _LOGGER.error("Value %s out of range for %s", modbus_value, self._key)
            return

        success = await self.coordinator.async_write_register(self._key, modbus_value)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s to %s (Modbus value: %s)", self._key, value, modbus_value)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add register information for debugging
        if self._key in self.coordinator.available_registers.get("holding_registers", set()):
            from .const import HOLDING_REGISTERS
            attributes["modbus_address"] = f"0x{HOLDING_REGISTERS[self._key]:04X}"
            attributes["register_type"] = "holding"
        
        # Add compatibility note for old entity ID
        if hasattr(self, '_attr_entity_id') and 'rekuperator_predkosc' in self._attr_entity_id:
            attributes["compatibility_note"] = "Legacy entity ID for backward compatibility"
            attributes["recommended_entity"] = "number.thessla_intensywnosc_manualny"
        
        return attributes