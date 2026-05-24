# AirPack4 Dangerous Entities Inventory

This document lists all Home Assistant entities that carry risk metadata
(`risk_level`, `risk_category`, `safety_warning`).  These fields are set
directly in the mapping dictionaries and are surfaced as
`extra_state_attributes` on each entity so that automations and dashboards
can inspect them at runtime.

## Risk categories

| Category | Meaning |
|----------|---------|
| `destructive_action` | Writing the register destroys or resets data (settings, schedule, filter state). |
| `communication_lockout` | Writing the register may change Modbus communication parameters and make the device unreachable. |
| `security_lock` | Writing the register affects device lock/unlock state or access level. |
| `advanced_configuration` | Writing the register changes a low-level configuration parameter that normal users should not touch. |

## Inventory

### Switch entities (`SWITCH_ENTITY_MAPPINGS` in `_static_discrete.py`)

| Entity key | risk_level | risk_category | safety_warning summary |
|------------|-----------|---------------|------------------------|
| `hard_reset_settings` | `advanced` | `destructive_action` | Writing this can reset user/device settings. |
| `hard_reset_schedule` | `advanced` | `destructive_action` | Writing this can reset schedule/settings. |
| `lock_flag` | `advanced` | `security_lock` | Changing this may lock or unlock the device. |

### Select entities (`SELECT_ENTITY_MAPPINGS` in `_static_discrete.py`)

| Entity key | risk_level | risk_category | safety_warning summary |
|------------|-----------|---------------|------------------------|
| `filter_change` | `advanced` | `destructive_action` | Write values can mark filters as replaced. |
| `configuration_mode` | `advanced` | `advanced_configuration` | Use only when intentionally configuring the unit. |
| `access_level` | `advanced` | `security_lock` | Changing this affects Modbus access level. |

### Select entities (`UART_SELECT_ENTITY_MAPPINGS` in `_static_discrete_uart.py`)

| Entity key | risk_level | risk_category | safety_warning summary |
|------------|-----------|---------------|------------------------|
| `uart_0_baud` | `advanced` | `communication_lockout` | Changing this may break Modbus communication. |
| `uart_0_parity` | `advanced` | `communication_lockout` | Changing this may break Modbus communication. |
| `uart_0_stop` | `advanced` | `communication_lockout` | Changing this may break Modbus communication. |
| `uart_1_baud` | `advanced` | `communication_lockout` | Changing this may break Modbus communication. |
| `uart_1_parity` | `advanced` | `communication_lockout` | Changing this may break Modbus communication. |
| `uart_1_stop` | `advanced` | `communication_lockout` | Changing this may break Modbus communication. |

### Number entities (`NUMBER_OVERRIDES` in `_static_numbers.py`)

| Entity key | risk_level | risk_category | safety_warning summary |
|------------|-----------|---------------|------------------------|
| `uart_0_id` | `advanced` | `communication_lockout` | Changing this may break Modbus communication. |
| `uart_1_id` | `advanced` | `communication_lockout` | Changing this may break Modbus communication. |
| `lock_pass` | `advanced` | `security_lock` | Changing this may lock or unlock the device. |

### Text entities (`TEXT_ENTITY_MAPPINGS` in `mappings/__init__.py`)

| Entity key | risk_level | risk_category | safety_warning summary |
|------------|-----------|---------------|------------------------|
| `device_name` | `advanced` | `advanced_configuration` | Write only with full understanding of encoding. |

## Normal entities (no risk metadata)

All other entities — including `mode`, `season_mode`, `bypass_user_mode`,
`gwc_regen`, `language`, `special_mode`, `cfg_mode_1`, `cfg_mode_2`,
`cfg_post_heater_mode`, `pres_check_day`, `pres_check_day_4432`,
`on_off_panel_mode`, `bypass_off`, `gwc_off`, `comfort_mode_panel`,
`airflow_rate_change_flag`, `temperature_change_flag`, and all sensor /
binary-sensor entities — do NOT carry risk metadata fields.
