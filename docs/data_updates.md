# Data updates

## Polling model
The integration uses local polling.
Data is read from the device using Modbus.
The exact entity set depends on detected capabilities and available registers.

## Default scan interval
TODO: verify from code.

## Options
Polling-related options are configured via integration options flow.
TODO: verify exact option names from code.

## Modbus request batching
Reads may be grouped into batched requests to reduce round-trips.
TODO: verify exact batching limits from code.

## Limitations
- Devices with partial register support may expose fewer entities.
- Busy/slow communication links may increase update latency.

## Why too frequent polling may be harmful
- Increases load on device and network.
- Raises timeout risk.
- Can degrade responsiveness for other Modbus clients.

## One active Modbus client recommendation
Use one active Modbus client per device whenever possible to avoid contention.
