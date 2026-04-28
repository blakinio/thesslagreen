# Supported functionality

## Platforms
- sensor
- binary_sensor
- switch
- number
- select
- text
- time
- fan
- climate

## Device functions
- temperatures
- airflow
- ventilation intensity
- bypass
- GWC
- special modes
- schedule
- filters / maintenance
- diagnostics
- firmware/model/serial information

## Climate entity
Climate functionality depends on detected capabilities and available registers.

## Fan entity
Fan functionality depends on detected capabilities and available registers.

## Services/actions
Service availability depends on integration setup and the selected entity target.
See `docs/services.md` for details.

## Limitations
Entities are created only when the matching register/function is detected as available.
