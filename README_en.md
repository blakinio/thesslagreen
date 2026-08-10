# ThesslaGreen Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/blakinio/thesslagreen.svg)](https://github.com/blakinio/thesslagreen/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.1.0%2B-blue.svg)](https://home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://python.org/)

A local-polling Home Assistant hub integration for ThesslaGreen AirPack ventilation units over Modbus.

The integration provides UI configuration, device/register discovery, Home Assistant entities, writable controls, diagnostics, and advanced validation tools. Register definitions are based on the vendor protocol documentation and are validated by repository tooling, but physical-device support still depends on the installed AirPack model, firmware, options, and transport.

## Requirements

- Home Assistant **2026.1.0+**
- Python **3.13+**
- `pymodbus>=3.6.0,<4.0`

## Supported connection modes

- Modbus TCP
- raw RTU-over-TCP
- Modbus RTU / USB serial

For production RTU installations prefer a persistent Linux device path:

```text
/dev/serial/by-id/usb-...
```

instead of `/dev/ttyUSB0`, because `ttyUSB` numbering can change after host or USB restarts.

## Main features

- automatic register/capability detection;
- Climate and Fan control;
- sensors, binary sensors, numbers, selects, switches, buttons, text and time entities where supported;
- weekly schedule and special ventilation modes;
- GWC and bypass controls where the device exposes them;
- diagnostics download with sensitive-field redaction;
- known-register validation;
- advanced full-register diagnostics;
- translated Home Assistant-facing write errors;
- Repairs issue on a final Modbus write failure, cleared by the next confirmed successful write;
- instantaneous estimated electrical power (`electrical_power`).

`electrical_power` is an **estimate**, not a metered energy value. The integration intentionally does not expose a process-memory `total_energy` counter because such a value would reset on restart and would not satisfy durable Home Assistant energy semantics.

## Installation

### HACS

1. HACS → **Integrations** → `⋮` → **Custom repositories**.
2. Add `https://github.com/blakinio/thesslagreen` as an **Integration** repository.
3. Install **ThesslaGreen Modbus**.
4. Restart Home Assistant.
5. Add the integration from **Settings → Devices & Services**.

### Manual

```bash
cd /config
git clone https://github.com/blakinio/thesslagreen.git
cp -r thesslagreen/custom_components/thessla_green_modbus custom_components/
```

Restart Home Assistant afterwards.

## Configuration

Choose the transport used by the AirPack installation and enter the corresponding endpoint, serial parameters, and slave/device ID.

The integration scans the device and stores detected capabilities/register availability. Only supported entities are normally instantiated. `force_full_register_list` is an advanced option and can expose definitions the tested device does not actually implement.

### Polling

The default polling interval is 30 seconds. Do not lower the interval aggressively without real-device validation; AirPack controllers and gateways can become less reliable under unnecessary request load.

Modbus requests are intentionally bounded to at most 16 registers per request by the integration's transport-safety policy.

## Services / actions

The integration exposes actions for areas including:

- special modes;
- airflow/schedule configuration;
- bypass and GWC parameters;
- air-quality thresholds;
- resets and maintenance operations;
- data refresh;
- clock synchronization;
- `validate_known_registers`;
- `scan_all_registers`;
- temporary logging changes.

The canonical list and schemas are in [`custom_components/thessla_green_modbus/services.yaml`](custom_components/thessla_green_modbus/services.yaml).

Home Assistant target resolution supports normal framework targets rather than only raw entity IDs, including indirect device/area/floor/label targeting when Home Assistant resolves those targets to integration entities.

## Register validation

### `validate_known_registers`

This is the preferred normal validation path. It uses controlled coordinator I/O and reports supported, unsupported, and indeterminate transport-failure outcomes separately.

A timeout or network error is **not** automatically classified as an unsupported register.

### `scan_all_registers`

This is an advanced diagnostic operation, not a routine automation action.

During the full scan the integration serializes coordinator I/O, disconnects the primary transport, scans using the configured transport semantics, restores the primary connection, and only then releases normal I/O ownership. The operation can still be slow and should be used intentionally.

## Write safety

Writable paths use bounded Modbus operations and explicit Home Assistant error semantics.

A rejected or failed final write must not appear as a successful Home Assistant action. Safe single-register writes may use targeted read-back. Registers that are unsafe, self-clearing, multi-word, schedule-related, communication-related, or otherwise unsuitable for direct read-back are excluded from that path.

Mappings marked with a risk level are disabled by default in the entity registry and categorized as configuration entities.

## Diagnostics

Enable debug logging with:

```yaml
logger:
  logs:
    custom_components.thessla_green_modbus: debug
```

Download diagnostics from **Settings → Devices & Services → ThesslaGreen Modbus → Download diagnostics**.

If Modbus errors occur:

- verify the device/gateway endpoint and slave ID;
- make sure another tool is not maintaining a competing Modbus session;
- for RTU, verify the adapter path and serial settings;
- inspect the Repairs dashboard after a failed write;
- use `validate_known_registers` before resorting to a full scan.

## Compatibility and validation status

| Item | Current status |
|---|---|
| Current published release | `v2.8.3` |
| Minimum Home Assistant | `2026.1.0` |
| Python | `3.13+` |
| pymodbus | `>=3.6.0,<4.0` |
| Manifest quality declaration | `bronze` |
| Automated hardening CI | PR #1762 / CI #1146 passed |
| Physical-device validation | partial; post-hardening revalidation pending |

See the canonical status at [`docs/quality/STATUS.md`](docs/quality/STATUS.md).

The repository does **not** infer physical-device correctness from CI. Existing AirPack 4 TCP evidence predates the 2026-08-10 hardening changes; post-hardening TCP/RTU/reconnect/soak validation is tracked in [`docs/real_device_validation.md`](docs/real_device_validation.md).

## Development

Use Python 3.13.

```bash
pip install -r requirements-dev.txt
ruff check custom_components tests tools
ruff check --select I custom_components tests tools
ruff format --check custom_components tests tools
mypy custom_components/thessla_green_modbus
pytest tests/ -q
python tools/validate_entity_mappings.py
python tools/check_translations.py
```

GitHub CI additionally runs:

- vendor register comparison;
- AirPack 4 vendor coverage checks;
- maintainability checks;
- focused API-contract tests on minimum Home Assistant `2026.1.0`;
- Hassfest;
- HACS validation.

Third-party GitHub Actions used by CI/release workflows are pinned to immutable commit SHAs.

## Architecture

The main runtime layers are intentionally separated:

```text
Home Assistant entities/actions
        ↓
Coordinator / HA adapter
        ↓
Device client / register processing
        ↓
Scanner / register definitions
        ↓
Transport TCP / RTU-over-TCP / RTU
```

`core/`, `transport/`, `registers/`, and `scanner/` are kept free of Home Assistant imports by repository architecture rules.

Further broad read-path/mixin consolidation is deliberately deferred until longer physical-device validation. See [`docs/core_consolidation_plan.md`](docs/core_consolidation_plan.md).

## Documentation

- [Canonical quality status](docs/quality/STATUS.md)
- [Home Assistant Quality Scale audit](docs/ha_quality_scale_audit.md)
- [Real-device validation](docs/real_device_validation.md)
- [Release readiness](docs/release_readiness.md)
- [Release process](docs/release_process.md)
- [Architecture](docs/thesslagreen_architecture.md)
- [Runtime flow](docs/architecture/runtime_flow.md)
- [Write path/read-back](docs/architecture/write_path.md)
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).
