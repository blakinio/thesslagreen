# Services

## Overview
Integration exposes service actions for control, maintenance, scanning and diagnostics.
Service definitions are in `custom_components/thessla_green_modbus/services.yaml`.

## Refresh data
- Service: `refresh_device_data`
- Purpose: force immediate refresh cycle.
- Typical use: troubleshooting stale/unavailable states.

## Full register scan
- Service: `scan_all_registers`
- Purpose: diagnostic full scan of register availability.
- Limitation: may report unsupported/unknown ranges.

## Set special mode
- Service: `set_special_mode`
- Purpose: set temporary special operating mode.
- Limitation: available behavior depends on device capabilities.

## Schedule services
- Service: `set_airflow_schedule`
- Purpose: configure weekly airflow schedule.
- Notes: includes day/period/start_time and related fields.

## Bypass/GWC services
- Services: `set_bypass_parameters`, `set_gwc_parameters`
- Purpose: configure bypass and ground heat exchanger parameters.

## Maintenance/reset services
- Services: `reset_filters`, `reset_settings`, `start_pressure_test`
- Purpose: maintenance operations and selected resets/tests.

## Log level service
- Service: `set_debug_logging`
- Purpose: temporarily increase log verbosity.

## Validation errors
Typical validation problems:
- required field missing,
- value out of allowed range,
- unsupported option for current selector,
- wrong entity target domain/integration.
