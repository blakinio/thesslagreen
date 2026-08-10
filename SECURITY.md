# Security policy

## Reporting a vulnerability

Do not publish exploitable security details in a public issue before a fix is available. Use GitHub's private vulnerability reporting for this repository when available; otherwise contact the repository owner privately and provide the affected version/commit, reproduction steps, impact, and any proposed mitigation.

## Modbus network boundary

ThesslaGreen Modbus is a local-control integration. Modbus TCP and raw RTU-over-TCP do not provide application-layer authentication or encryption.

Production deployments should therefore:

- keep the AirPack controller or Modbus gateway on a trusted local network;
- restrict access with firewall rules and, where practical, a dedicated IoT/automation VLAN;
- allow Modbus access only from the Home Assistant host and other explicitly required management systems;
- never expose or port-forward the Modbus TCP/RTU-over-TCP endpoint directly to the public Internet;
- use a VPN or another authenticated secure access layer for remote administration rather than exposing Modbus itself;
- avoid concurrent polling/control clients unless the gateway/controller is known to support them safely.

For serial RTU, prefer persistent Linux paths such as `/dev/serial/by-id/...` and restrict host/device access to the Home Assistant runtime that needs it.

## Home Assistant diagnostics

Diagnostics are intended for troubleshooting, not public telemetry. Review downloaded diagnostics before sharing them. The integration redacts sensitive device/configuration fields where supported, but local hostnames, topology details, device identifiers, or future diagnostic fields may still be operationally sensitive.

## Dependency and CI policy

Runtime dependencies are bounded in integration/package metadata. CI validates the declared minimum Home Assistant API contract, a current stable Home Assistant API contract, supported pymodbus boundary versions, strict typing, Hassfest, HACS validation, and the full test suite. Third-party GitHub Actions used by CI/release workflows are pinned to immutable commit SHAs.

Security-sensitive runtime changes must not be treated as physically validated solely because CI is green; hardware/network acceptance evidence is tracked separately in `docs/real_device_validation.md`.
