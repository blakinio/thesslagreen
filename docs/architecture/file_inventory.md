# File inventory — thessla_green_modbus

Concise map of what each important file/folder owns and how risky it is to change.
Read this **before** editing, so a change does not silently break existing user
installations.

> **Hard invariants (from `CLAUDE.md`).** Never change Modbus register
> addresses/names, entity IDs, unique IDs, service IDs, or translation keys — they
> are public contracts. Do not change config/options-flow behaviour, reintroduce
> `modbus_helpers.py`, or break layer isolation
> (`transport/ core/ scanner/ registers/ modbus/` must not import Home Assistant
> outside `TYPE_CHECKING`, nor import from `coordinator/`/platforms). Do not touch
> the `{16, 8192}` batch boundaries in `const.py`.

Layering (allowed dependency direction, top → bottom):

```text
HA platforms → coordinator/ → core/ → registers/ + scanner/ → transport/
```

Risk legend: **🟥 high** (public contract / device I/O / write path),
**🟧 medium** (behaviour-shaping logic), **🟩 low** (isolated, well-tested, or docs).

## Integration entry point & lifecycle

| Path | Role | Kind | When to change | Risk | Related tests/tools | Notes / do-not-change |
|---|---|---|---|---|---|---|
| `__init__.py` | HA `async_setup_entry` / `async_unload_entry` / `async_update_options` / `async_migrate_entry`; wires coordinator, mappings, unique-id migration, platforms, clock sync, services. | Runtime | Only for lifecycle wiring changes. | 🟥 | `tests/test_init*.py`, `test_setup*` | Options update does a **full reload** on purpose. Services registered only for the first entry, unloaded on the last. |
| `_setup.py` | Setup helpers: build coordinator, start/first-refresh, load mappings/options, migrate unique IDs, forward platform setup. | Runtime | With lifecycle changes. | 🟥 | `tests/test_setup*.py` | Translates connect/auth errors into `ConfigEntryNotReady`/reauth. |
| `_migrations.py`, `_entry_migrations.py` | Config-entry schema migrations. | Runtime | Only when bumping entry version. | 🟧 | `tests/test_migrations*.py` | Never rewrite historical migration steps. |
| `manifest.json` | HA integration manifest (domain, version, `quality_scale`, `pymodbus>=3.6,<4.0`, discovery). | Runtime | Version bumps, deps, discovery. | 🟥 | `hassfest` (CI) | Do **not** raise `quality_scale` above `bronze` until real-device validation is PASS. Keep pymodbus pin `<4.0`. |
| `const.py` | Domain, `PLATFORMS`, config keys/defaults, batch boundaries, maps. | Runtime | New config keys/defaults. | 🟥 | `tests/test_const*.py` | Do **not** change `{16, 8192}` batch boundaries or `DOMAIN`. |
| `utils.py`, `protocols.py`, `capability_rules.py`, `error_*.py`, `errors.py` | Shared helpers, typing protocols, capability gating, error contracts. | Runtime | Rarely. | 🟧 | related unit tests | Error-classification contracts are relied on by callers; grep call sites first. |
| `repairs.py` | HA repairs issues. | Runtime | New repair flows. | 🟩 | `tests/test_repairs.py` | — |

## HA platforms (entities)

| Path | Role | Kind | When to change | Risk | Related tests/tools | Notes / do-not-change |
|---|---|---|---|---|---|---|
| `entity.py` | `ThesslaGreenEntity` base: `unique_id`, `suggested_object_id`, `available`, `_write_register`. | Runtime | Base entity behaviour. | 🟥 | `tests/test_write_readback.py`, `test_entity*` | `unique_id`/`suggested_object_id` are **public contracts** — do not alter their format. `_write_register` delegates refresh/read-back policy to the coordinator. |
| `fan.py` | Fan entity; percentage from **status** registers; optimistic pending-percentage; writes `mode`/`air_flow_rate_manual`/`on_off_panel_mode`. | Runtime | Fan UX/write sequencing. | 🟥 | `tests/test_fan.py`, `test_write_readback.py` | Writes pass `targeted_readback=False` and do a **single** trailing refresh. Setpoints ≠ display registers. See `write_path.md`. |
| `climate.py` | Climate entity; hvac/temperature/fan/preset. | Runtime | Climate UX/write sequencing. | 🟥 | `tests/test_climate*.py` | All write paths pass `refresh=False,targeted_readback=False` + one refresh. See `write_path.md`. |
| `number.py` | Numeric setpoints (e.g. `air_flow_rate_manual`, temps, `uart_*_id`, `lock_pass`, `rtc_cal`). | Runtime | New number entities. | 🟧 | `tests/test_number*.py` | Writes via base `_write_register` (read-back active for 1:1 setpoints). |
| `switch.py` | On/off holding/coil registers. | Runtime | New switch entities. | 🟧 | `tests/test_switch*.py` | Reads current state from `coordinator.data`. |
| `select.py` | Enum/option registers. | Runtime | New select entities. | 🟧 | `tests/test_select*.py` | `schedule_`/`setting_` prefixes excluded from read-back. |
| `sensor.py` | Read-only measurements (temperatures, airflow, efficiency, power, error/status codes). | Runtime | New sensors. | 🟧 | `tests/test_sensor*.py` | Status-only — must **not** be optimistic. |
| `binary_sensor.py` | Read-only flags, alarms (`e_*`/`s_*`/`f_*`), diagnostics. | Runtime | New binary sensors. | 🟩 | `tests/test_binary_sensor.py` | Alarm/error state is read-only. |
| `button.py` | Momentary actions (e.g. resets/tests). | Runtime | New buttons. | 🟧 | `tests/test_button.py` | Triggers may target destructive registers. |
| `text.py`, `time.py` | Device name (multi-word) / BCD schedule-time slots. | Runtime | New text/time entities. | 🟧 | `tests/test_text*.py`, `test_time*` | Multi-word / `schedule_`/`setting_` writes are excluded from read-back. |
| `clock_sync.py` | `ClockSyncManager`: optional periodic device-clock sync. | Runtime | Clock-sync behaviour. | 🟧 | `tests/test_clock_sync.py` | Multi-register block write; no single-register read-back. |

## Coordinator (`coordinator/`)

HA-boundary adapter around `DataUpdateCoordinator`. Owns the update cycle, offline
state, scan cache in the config entry, and the **write path**. Delegates all Modbus
I/O to `core/` — it must never call raw Modbus itself.

| Path | Role | Risk | Notes / do-not-change |
|---|---|---|---|
| `coordinator/coordinator.py` | `ThesslaGreenModbusCoordinator` — mixin assembler; owns `device_client`, setup, shutdown, boundary adapters. | 🟥 | Keep as an assembler; do not merge mixins into a monolith. |
| `coordinator/schedule.py` | Write mixin: `async_write_register(s)`, `_targeted_readback_safe`, `_NO_READBACK_REGISTERS`, locked read-back. | 🟥 | The single source of the read-back policy. See `write_path.md` before touching. |
| `coordinator/write_path.py` | Retry loops + `finalize_write_result` for single/multi writes. | 🟥 | Preserve "successful write never fails due to read-back" invariant. |
| `coordinator/update.py`, `update_state.py`, `update_result.py` | Poll cycle, in-progress guard, success/stats application. | 🟥 | `_read_all_register_data()` is delegated to `core/`. |
| `coordinator/scan.py`, `scan_result.py`, `schedule_helpers`→`scan.py` | Prepare registers from full-list / cache / device scan; store scan cache in entry options. | 🟧 | Writes to entry options; only place allowed to. |
| `coordinator/lifecycle.py`, `runtime.py`, `state.py`, `init_config.py`, `config_normalization.py`, `factory.py` | Setup orchestration, runtime state init, config normalisation, `from_params`. | 🟧 | — |
| `coordinator/device_info.py`, `diagnostics.py`, `errors.py` | Device-info warnings, diagnostic payload, update error handling. | 🟩 | — |

## Core device layer (`core/`)

Home-Assistant-free device domain. `ThesslaGreenDeviceClient` is the **sole owner**
of the Modbus connection and I/O and is assembled from mixins.

| Path | Role | Risk | Notes / do-not-change |
|---|---|---|---|
| `core/client.py` | `ThesslaGreenDeviceClient` mixin assembler (connect/close, read snapshot, scan, write). | 🟥 | **Keep as the mixin assembler** — do not merge into a monolith (CLAUDE.md). |
| `core/write_path.py` | `SingleWritePlan`, `encode_write_value` (user units → raw). | 🟥 | Encoding correctness = correct device behaviour. |
| `core/client_connection.py`, `connection*.py`, `disconnect.py`, `transport_select.py`, `retry.py`, `runtime_io.py`, `io_mixin.py` | Connection lifecycle, transport selection, retry/backoff, low-level I/O. | 🟥 | Sole I/O owner; do not add a second Modbus client path. |
| `core/client_registers.py`, `read_*.py`, `register_*.py` | Batched register reads, decoding to snapshot values. | 🟥 | Respect batch boundaries from `const.py`. |
| `core/client_scanner.py`, `scan_helpers.py`, `capabilities_mixin.py` | Capability discovery orchestration. | 🟧 | Treat Modbus exception code 2 as unsupported, not fatal. |
| `core/models.py` | `CoordinatorConfig`, domain models. | 🟧 | — |
| `modbus/` | Low-level pymodbus call wrappers, framing, frame logging, client close. | 🟥 | Pymodbus-facing; pin `<4.0`. |

## Protocol, scanner, transport

| Path | Role | Kind | Risk | Notes / do-not-change |
|---|---|---|---|---|
| `registers/` | Register definitions, JSON loader, cache, codec, read planner, schema, maps. | Runtime | 🟥 | `registers/thessla_green_registers_full.json` is the **single source of truth** for register names/addresses — do not edit names/addresses. No I/O here, no HA imports. |
| `register_map.py`, `register_defs_cache.py`, `entity_lookup.py`, `unique_id_migration.py` | Register lookups, cached defs, entity lookup, unique-id migration. | Runtime | 🟧 | `unique_id_migration.py` protects existing entity IDs — never weaken. |
| `scanner/` | Model/firmware/capability detection; safe/normal/deep scan; unsupported-register handling. | Runtime | 🟧 | Never auto-add unknown registers as entities. `scan_all_registers` opens a separate connection and must stay read-only. No HA imports. |
| `transport/` | Modbus TCP / RTU / RTU-over-TCP, retry, backoff, CRC/framing, error classification. | Runtime | 🟥 | Knows only Modbus — must not know register names, snapshots, or HA. |
| `mappings/` | Map domain data → HA entity descriptions (sensors, numbers, discrete, special modes). | Runtime | 🟧 | May import HA; must not do Modbus I/O or decode raw registers. Changing a mapping can change entity IDs/categories — verify with `validate_entity_mappings.py`. |
| `options/` + `options/*.json` | Option lists (bypass/gwc modes, days, baud/parity/stop, special modes). | Runtime | 🟩 | Option values feed selects/services; keep keys stable. |

## Services, config flow, diagnostics, UI text

| Path | Role | Kind | When to change | Risk | Related tests/tools | Notes / do-not-change |
|---|---|---|---|---|---|---|
| `services/` | Service registration + handlers (mode, schedule, parameters, maintenance, data, logging). | Runtime | New/changed services. | 🟥 | `tests/test_services*.py` | **Service IDs are a public contract.** All service register writes pass `targeted_readback=False`. `services.yaml` names must match handlers. |
| `services.yaml` | Service metadata for HA UI. | Runtime | With service changes. | 🟥 | `check_translations.py` | Keep service/field IDs aligned with `services/` and translations. |
| `config_flow.py` | Thin public HA entrypoint (re-exports `ThesslaGreenConfigFlow`). | Runtime | Never add logic here. | 🟧 | hassfest | Implementation lives in `_config_flow/`. Exists only to satisfy hassfest. |
| `_config_flow/` | Config & options flow implementation: user/network/schema/validation/device scan/reauth/options. | Runtime | Flow changes only if task requires. | 🟥 | `tests/test_config_flow_*.py` | **Do not change config/options-flow behaviour** unless explicitly required. Scan runs here; result cached into entry options. |
| `diagnostics.py` | Config-entry diagnostics payload with IP/serial redaction. | Runtime | New diagnostic fields. | 🟧 | `tests/test_diagnostics*.py` | Keep redaction of host/serial/error messages. Diagnostics are status-only. |
| `strings.json` | Source translation strings (entities, config flow, services, error/status codes). | Runtime | New UI strings. | 🟥 | `check_translations.py`, `generate_strings.py` | **Translation keys are a public contract** — add, do not rename. |
| `translations/en.json`, `pl.json` | Localised strings generated from `strings.json`. | Runtime | Regenerate after `strings.json`. | 🟧 | `check_translations.py` | Keep keys in sync across locales. |
| `brand/` | HA brand icon/logo assets. | Runtime | Branding. | 🟩 | — | — |

## Tests, tools, docs

| Path | Role | Kind | When to change | Risk | Related tests/tools | Notes / do-not-change |
|---|---|---|---|---|---|---|
| `tests/` | Pytest suite (~250 files): entities, coordinator, write/read-back, services, config flow, dependency direction, register/vendor coverage. | Test | With any behaviour change. | 🟧 | needs **Python 3.13** + HA test stack | `test_dependency_direction.py` enforces layer isolation — may be strengthened, never weakened. Do not edit tests just to collect on older Python. |
| `tools/` | Standalone validators/utilities: `check_maintainability.py`, `validate_entity_mappings.py`, `check_translations.py`, `compare_registers_with_reference.py`, `compare_airpack4_vendor_coverage.py`, `validate_registers.py`, `generate_strings.py`, `sort_registers_json.py`, `migrate_register_names.py`, `cleanup_old_entities.py`, `clear_airflow_stats.py`, `validate_dashboard_entities.py`, `translate_register_descriptions.py`. | Tool | New checks/generators. | 🟩 | run in CI / manually | Lightweight validators need only `pydantic`/`PyYAML`/`voluptuous`. Generators must not silently change register names/IDs. |
| `docs/` | Architecture, plans, audits, real-device validation, release docs. | Docs | Documentation updates. | 🟩 | — | `real_device_validation.md` gates the quality scale. Plan docs (`*_plan.md`) are the source of truth for refactors. This inventory + `runtime_flow.md` + `write_path.md` live in `docs/architecture/`. |
