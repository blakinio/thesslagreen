# ThesslaGreen Modbus — Quick Start

## Requirements

- Home Assistant **2026.1.0+**
- ThesslaGreen AirPack with Modbus enabled
- HACS for the recommended installation path, or access to `/config/custom_components`

The integration supports Modbus TCP, raw RTU-over-TCP, and Modbus RTU/USB. The actual slave ID, port, baud rate, parity, and stop bits must match the AirPack/gateway configuration.

## Install with HACS

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/blakinio/thesslagreen` as an **Integration** repository.
3. Install **ThesslaGreen Modbus**.
4. Restart Home Assistant.
5. Open **Settings → Devices & Services → Add Integration** and select **ThesslaGreen Modbus**.

## Manual installation

Copy `custom_components/thessla_green_modbus` into the Home Assistant configuration directory:

```text
/config/custom_components/thessla_green_modbus
```

Restart Home Assistant and add the integration from **Settings → Devices & Services**.

## TCP setup

Enter the AirPack/gateway host, port, and Modbus slave ID configured on the device. Do not assume port `502` or slave ID `10` if the installation uses different settings.

**Security:** Modbus TCP and raw RTU-over-TCP have no application-layer authentication or encryption. Keep the endpoint on a trusted LAN, restrict it with firewall/VLAN rules, and never port-forward it directly to the public Internet. See [`SECURITY.md`](SECURITY.md).

## RTU / USB setup

Prefer a persistent device path such as:

```text
/dev/serial/by-id/usb-...
```

instead of `/dev/ttyUSB0`, because USB enumeration can change after a reboot or reconnect. Configure baud rate, parity, stop bits, and slave ID to match the AirPack/controller.

## First setup

During configuration the integration validates the connection and discovers supported registers/capabilities. Normal operation creates only entities supported by the detected device.

The advanced `force_full_register_list` option can expose predefined entities without normal availability filtering. Use it only for diagnostics/development because unsupported definitions can remain unavailable.

## Normal operation

The coordinator performs the initial refresh before entity platforms are created, then polls at the configured interval. The default interval is 30 seconds; avoid aggressive polling without real-device validation.

Writable entities/actions report final Modbus failures to Home Assistant instead of silently succeeding. A persistent final write failure also creates a Home Assistant Repairs issue; the next confirmed successful write clears it.

## Register diagnostics

Use `thessla_green_modbus.validate_known_registers` for normal register classification. It distinguishes:

- supported registers;
- explicitly unsupported registers;
- indeterminate results caused by transport/network failure.

`thessla_green_modbus.scan_all_registers` is an advanced diagnostic operation. It serializes normal integration I/O, temporarily disconnects the primary transport, performs the scan with the configured transport type, restores the normal connection, and should not be used as a recurring automation.

## Troubleshooting

Enable integration debug logging when needed:

```yaml
logger:
  logs:
    custom_components.thessla_green_modbus: debug
```

Then check:

- **Settings → System → Logs**;
- **Settings → Devices & Services → ThesslaGreen Modbus → Download diagnostics**;
- the Home Assistant **Repairs** dashboard after write failures;
- network reachability or RTU adapter/serial parameters;
- whether another Modbus client is concurrently using the same controller/gateway.

For current quality and physical-device validation status see [`docs/quality/STATUS.md`](docs/quality/STATUS.md) and [`docs/real_device_validation.md`](docs/real_device_validation.md).
