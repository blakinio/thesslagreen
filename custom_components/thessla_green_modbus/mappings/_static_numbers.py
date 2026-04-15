"""Static number mappings for ThesslaGreen entities."""

from __future__ import annotations

from typing import Any

NUMBER_OVERRIDES: dict[str, dict[str, Any]] = {
    # Temperature setpoints — multiplier=0.5, so physical = raw × 0.5 (°C)
    # PDF raw range 20–90 → physical 10–45 °C, step 0.5 °C
    "supply_air_temperature_manual": {
        "icon": "mdi:thermometer-plus",
        "min": 10,
        "max": 45,
        "step": 0.5,
    },
    "supply_air_temperature_temporary": {
        "icon": "mdi:thermometer-plus",
        "min": 10,
        "max": 45,
        "step": 0.5,
    },
    "supply_air_temperature_temporary_4404": {
        "icon": "mdi:thermometer-plus",
        "min": 10,
        "max": 45,
        "step": 0.5,
    },
    # PDF raw 10–40 → physical 5–20 °C
    "min_bypass_temperature": {"icon": "mdi:thermometer-low", "min": 5, "max": 20, "step": 0.5},
    # PDF raw 30–60 → physical 15–30 °C
    "air_temperature_summer_free_heating": {
        "icon": "mdi:thermometer",
        "min": 15,
        "max": 30,
        "step": 0.5,
    },
    "air_temperature_summer_free_cooling": {
        "icon": "mdi:thermometer",
        "min": 15,
        "max": 30,
        "step": 0.5,
    },
    # PDF raw 0–20 → physical 0–10 °C
    "min_gwc_air_temperature": {"icon": "mdi:thermometer-low", "min": 0, "max": 10, "step": 0.5},
    # PDF raw 30–80 → physical 15–40 °C
    "max_gwc_air_temperature": {"icon": "mdi:thermometer-high", "min": 15, "max": 40, "step": 0.5},
    # PDF raw 0–10 → physical 0–5 °C
    "delta_t_gwc": {"icon": "mdi:thermometer-lines", "min": 0, "max": 5, "step": 0.5},
    # Air flow intensity setpoints (%), multiplier=1
    "air_flow_rate_manual": {"icon": "mdi:fan", "min": 10, "max": 100, "step": 1},
    "air_flow_rate_temporary": {"icon": "mdi:fan", "min": 10, "max": 100, "step": 1},
    "air_flow_rate_temporary_4401": {"icon": "mdi:fan", "min": 10, "max": 100, "step": 1},
    "max_supply_air_flow_rate": {"icon": "mdi:fan-plus", "min": 100, "max": 150, "step": 1},
    "max_exhaust_air_flow_rate": {"icon": "mdi:fan-minus", "min": 100, "max": 150, "step": 1},
    "max_supply_air_flow_rate_gwc": {"icon": "mdi:fan-plus", "min": 100, "max": 150, "step": 1},
    "max_exhaust_air_flow_rate_gwc": {"icon": "mdi:fan-minus", "min": 100, "max": 150, "step": 1},
    # Nominal (calibrated) air flow (m³/h)
    "nominal_supply_air_flow": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    "nominal_exhaust_air_flow": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    "nominal_supply_air_flow_gwc": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    "nominal_exhaust_air_flow_gwc": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    # GWC timing
    "gwc_regen_period": {"icon": "mdi:timer", "min": 4, "max": 8, "step": 1},
    # Fan speed setpoints for AirS panel — speed 1/2/3 non-overlapping ranges
    "fan_speed_1_coef": {"icon": "mdi:speedometer", "min": 10, "max": 45, "step": 1},
    "fan_speed_2_coef": {"icon": "mdi:speedometer", "min": 46, "max": 75, "step": 1},
    "fan_speed_3_coef": {"icon": "mdi:speedometer", "min": 76, "max": 100, "step": 1},
    # Special-function intensity setpoints (%)
    "hood_supply_coef": {"icon": "mdi:stove", "min": 100, "max": 150, "step": 1},
    "hood_exhaust_coef": {"icon": "mdi:stove", "min": 100, "max": 150, "step": 1},
    "fireplace_supply_coef": {"icon": "mdi:fireplace", "min": 5, "max": 50, "step": 1},
    "airing_bathroom_coef": {"icon": "mdi:shower", "min": 100, "max": 150, "step": 1},
    "airing_coef": {"icon": "mdi:window-open", "min": 100, "max": 150, "step": 1},
    "contamination_coef": {"icon": "mdi:air-filter", "min": 100, "max": 150, "step": 1},
    "empty_house_coef": {"icon": "mdi:home-off", "min": 10, "max": 50, "step": 1},
    "airing_switch_coef": {"icon": "mdi:toggle-switch", "min": 100, "max": 150, "step": 1},
    "open_window_coef": {"icon": "mdi:window-open-variant", "min": 10, "max": 100, "step": 1},
    "bypass_coef_1": {"icon": "mdi:transfer", "min": 10, "max": 100, "step": 1},
    "bypass_coef_2": {"icon": "mdi:transfer", "min": 10, "max": 150, "step": 1},
    # Special-function timing (min)
    "airing_panel_mode_time": {"icon": "mdi:timer", "min": 1, "max": 45, "step": 1},
    "airing_switch_mode_time": {"icon": "mdi:timer", "min": 1, "max": 45, "step": 1},
    "airing_switch_mode_on_delay": {
        "icon": "mdi:timer-plus-outline",
        "min": 0,
        "max": 20,
        "step": 1,
    },
    "airing_switch_mode_off_delay": {
        "icon": "mdi:timer-minus-outline",
        "min": 0,
        "max": 20,
        "step": 1,
    },
    "fireplace_mode_time": {"icon": "mdi:timer", "min": 1, "max": 10, "step": 1},
    # Modbus port device IDs
    "uart_0_id": {"icon": "mdi:identifier", "min": 10, "max": 19, "step": 1},
    "uart_1_id": {"icon": "mdi:identifier", "min": 10, "max": 19, "step": 1},
    # Filter wear thresholds (0–127 %)
    "cfgszf_fn_new": {"icon": "mdi:filter-check", "min": 0, "max": 127, "step": 1},
    "cfgszf_fw_new": {"icon": "mdi:filter-check", "min": 0, "max": 127, "step": 1},
    # RTC calibration register (0–255, signed offset encoded as unsigned; no SI unit)
    "rtc_cal": {"icon": "mdi:clock-edit", "min": 0, "max": 255, "step": 1, "unit": None},
    # lock_pass — product key passphrase, first 16-bit word (0–0x423f = 16959)
    "lock_pass": {"icon": "mdi:lock", "min": 0, "max": 16959, "step": 1},
}

NUMBER_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}

__all__ = ["NUMBER_ENTITY_MAPPINGS", "NUMBER_OVERRIDES"]
