# Coordinator Proxy Removal Report

- Proxy count before: 40 device-state proxies in `coordinator.py`.
- Proxy count after: 35 device-state proxies in `coordinator.py`.
- Removed proxies in this slice:
  - `_last_power_timestamp`
  - `_total_energy`
  - `_consecutive_failures`
  - `_max_failures`
  - `_failed_registers`
- Why safe: these are internal device-runtime fields already owned by `ThesslaGreenDeviceClient`; production and tests were migrated to explicit `coordinator.device_client.*` access before proxy deletion.
- Remaining proxy count: 35.
