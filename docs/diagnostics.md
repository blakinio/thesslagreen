# Diagnostics Fields

The Thessla Green Modbus integration exposes several fields via the Home Assistant diagnostics panel. These fields provide insight into device state and communication issues.

- `registers_hash`: Stable hash of the register definitions packaged with the integration.
- `capabilities`: Features supported by the connected device.
- `firmware_version`: Firmware version reported by the device.
- `total_available_registers`: Count of registers known to the integration.
- `last_scan`: ISO-8601 timestamp of the most recent register scan.
- `error_statistics`: Breakdown of recent connection and timeout errors.
- `raw_registers`: Raw register dump returned during the last scan, when available.
- `unknown_registers`: Registers read from the device that are not in the register map.
- `failed_addresses`: Addresses skipped during scanning due to errors.
- `active_errors`: Currently active error or status codes with translations when available.

All IP addresses shown in diagnostics are masked to hide network details. When an IPv6
address includes a zone index (for example `fe80::1%eth0`), the zone portion is removed
before masking so interface names are not revealed.

These diagnostics make it easier to troubleshoot setup issues and confirm device behavior.
