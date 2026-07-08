# Changelog

All notable changes to the ThesslaGreen Modbus Integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Internal

- **Targeted read-back restricted to an explicit safe allow-list.** The post-write
  targeted read-back policy (`coordinator/schedule.py`) was changed from a permissive
  deny-list (any single-word holding register was eligible unless enumerated) to an
  explicit `_READBACK_ALLOW_LIST` of registers known to be 1:1 with a single displayed
  entity state — airflow / temperature / coefficient / timing setpoints and operational
  mode controls exposed via the number/select/switch platforms. Dangerous configuration
  registers written through those same platforms — communication config (`uart_*`),
  security (`lock_*`, `access_level`), configuration mode (`configuration_mode`,
  `cfg_mode_*`), device config/clock (`language`, `rtc_cal`), reset/trigger/self-clearing
  registers, and schedule/setting BCD-AATT slots — are no longer read-back eligible and
  now converge via the existing debounced full refresh. The `function == 3` /
  `length == 1` checks are kept as defence-in-depth. Fan, climate, and service write
  paths already opt out with `targeted_readback=False` and are unchanged; a read-back
  read/decode failure still never fails a successful write, and enum read-back still
  stores the raw int. No Modbus register addresses/names, entity IDs, unique IDs, service
  IDs, translation keys, or config/options-flow behavior changed. See
  `docs/architecture/write_path.md` and
  `docs/audits/targeted_readback_write_path_audit.md` ("Stage 2").

## [2.8.2] - 2026-07-08

> Mostly tooling and documentation cleanup, plus the already-merged safe optimistic
> UI for controllable/setpoint entities. No Modbus register addresses/names, entity
> IDs, unique IDs, service IDs, translation keys, or config/options-flow behavior
> changed.

### Added

- **Comprehensive, safe optimistic UI state for controllable/setpoint entities**
  ([#1734](https://github.com/blakinio/thesslagreen/pull/1734)).
  A new shared helper `custom_components/thessla_green_modbus/optimistic.py`
  (`OptimisticState`) lets control entities reflect a *requested* value in the GUI
  immediately after a confirmed-successful write, instead of lagging one full
  coordinator poll behind the physical device. The helper supports
  `set_pending`/`get_pending`/`clear_pending`/`clear_if_confirmed`, a TTL (default
  10 s), and an optional float tolerance. It is wired into:
  - **Number** (`native_value`) — shows the pending setpoint after a successful write.
  - **Switch** (`is_on`) — stores the pending raw register value so simple, bit, and
    mutually-exclusive `special_mode` switches evaluate consistently.
  - **Select** (`current_option`) — shows the pending option; schedule/setting/BCD-time
    selects are deliberately excluded.
  - **Climate** — `target_temperature`, `hvac_mode`, `fan_mode`, `preset_mode`, and the
    visible mode after turn on/off. `current_temperature` and `hvac_action` stay
    confirmed-only; airflow/temperature extra attributes are never made optimistic.

  Optimistic state is stored only after a confirmed-successful write, never mutates
  `coordinator.data`, self-expires after the TTL, and is cleared as soon as the
  coordinator confirms the real value. Failed writes never update the GUI
  optimistically. The full post-write refresh is preserved everywhere; for the climate
  multi-register flows the pending value is set before awaiting the refresh so the GUI
  updates immediately. The fan keeps its existing dedicated optimistic-percentage
  implementation (unchanged; targeted read-back stays disabled for fan writes). No
  Modbus register addresses, register/entity/unique/service IDs, or translation keys
  changed. (Runtime code merged in [#1734]; this entry restores a changelog note that
  was clobbered by a later merge.)

### Docs

- **Added architecture / file-inventory documentation** under `docs/architecture/`:
  `file_inventory.md` (per-file ownership, risk level, and do-not-change warnings),
  `runtime_flow.md` (config-flow scan, DeviceClient ownership, coordinator/entity
  setup, polling, service registration, unload/reload, real-device validation
  expectations), and `write_path.md` (HA entity → Modbus write, targeted read-back
  rules, full-refresh fallback, why fan/climate disable read-back, and optimistic-UI
  policy). Docs-only; no runtime code, register addresses/names, entity/unique/service
  IDs, or translation keys changed. Linked from the README documentation list.
- Added §11 "Optimistic UI validation for controllable entities" to
  `docs/real_device_validation.md` with a real-device checklist and PASS criteria
  ([#1734](https://github.com/blakinio/thesslagreen/pull/1734)).

### Internal

- **Restored `pydantic==2.12.2` dev pin (revert of Dependabot #1741; no runtime
  change).** `pytest-homeassistant-custom-component 0.13.309–0.13.316` (the range
  pinned in `requirements-dev.txt` / `pyproject.toml`) all depend on
  `pydantic==2.12.2`, so the Dependabot minor bump to `pydantic==2.13.4`
  ([#1741](https://github.com/blakinio/thesslagreen/pull/1741)) made
  `pip install -r requirements-dev.txt` fail with `ResolutionImpossible`, breaking
  the CI dependency-install step on `main` (commit `0c46629`: the Lint job failed and
  Tests / Entity-mappings were skipped). Reverted the pin to `2.12.2` in both
  `requirements-dev.txt` and `pyproject.toml` and restored the accurate
  `pyproject.toml` comment (Dependabot had rewritten it to claim the plugin pins
  2.13.4). This is a repeat of the #1708 regression fixed in 2.8.1. No runtime code,
  Modbus register addresses/names, entity/unique/service IDs, translation keys, or
  config/options-flow behavior changed.
- **Repository cleanup follow-up (tooling/docs; no runtime change).** Removed the
  stale `info.md` (its counts/capabilities were outdated and `hacs.json:
  render_readme:true` makes `README.md` canonical) and the unused `.yamllint.yaml`
  (not run by CI or pre-commit — pre-commit uses `check-yaml`, not `yamllint`);
  relocated the three remaining manual/one-shot `tools/` scripts
  (`cleanup_old_entities.py`, `generate_strings.py`, `sort_registers_json.py`) into
  `tools/manual/` via `git mv` so the top-level `tools/` holds only recurring
  CI/pre-commit validators/generators; fixed the `tools/validate_registers.py`
  CLI/pre-commit path (the `read_planner` stub was missing `group_registers` /
  `plan_group_reads`, so standalone `python tools/validate_registers.py` raised
  `ImportError`); updated `tools/README.md`, `tools/manual/README.md`,
  `docs/architecture/file_inventory.md`, the repository file-inventory audit, and the
  `tests/test_cleanup_old_entities.py` import path. No Modbus register addresses/names,
  entity/unique/service IDs, translation keys, or config/options-flow behavior changed;
  no runtime module was touched.
- **Repository structure cleanup (tooling/docs reorganization; no runtime change).**
  Moved one-shot / manual utilities out of `tools/` into a new `tools/manual/`
  (`migrate_register_names.py`, `translate_register_descriptions.py`,
  `clear_airflow_stats.py`, and the root `delete_stale_branches.sh`) so that `tools/`
  holds only the recurring CI/pre-commit validators and generators; archived the
  dated one-shot `docs/release_tooling_audit.md` into `docs/archive/`; removed a dead
  `docs/register_scanning.md` link from `README_en.md`; updated `pyproject.toml`
  (ruff per-file-ignore path) and `docs/architecture/file_inventory.md`. All moves use
  `git mv` (history preserved). No Modbus register addresses/names, entity/unique/service
  IDs, translation keys, or config/options-flow behavior changed; no runtime module moved.

## [2.8.1] - 2026-07-06

> Enum targeted read-back representation fix and fan percentage GUI responsiveness.
> No Modbus register addresses, register/entity/unique/service IDs, or translation
> keys changed. Real-device validation for the fan GUI path is still required.

### Fixed

- **Fan optimistic percentage is now published before the post-write refresh, not
  after** ([#1732](https://github.com/blakinio/thesslagreen/pull/1732)):
  `async_set_percentage` set `_pending_percentage` (which writes the HA state)
  only *after* awaiting `coordinator.async_request_refresh()`, so the optimistic GUI
  update from the previous fix was delayed until the full refresh completed. The
  ordering is now inverted for both the manual and temporary write paths — the pending
  value is recorded and pushed to the GUI immediately after the confirmed-successful
  airflow write, then the refresh is awaited to reconcile against the real
  `supply_percentage` / `exhaust_percentage` status registers. Write failures still set
  no pending value and fire no refresh; targeted read-back stays disabled for fan writes.

- **Fan percentage now updates in the GUI immediately after a successful airflow
  write** ([#1731](https://github.com/blakinio/thesslagreen/pull/1731)):
  `fan.percentage` is derived from the status registers `supply_percentage` /
  `exhaust_percentage`, but fan writes target the setpoint registers `mode`,
  `air_flow_rate_manual`, and `air_flow_rate_temporary_2` and deliberately keep
  `targeted_readback=False` (the setpoints are not 1:1 with the displayed status
  registers).  The GUI therefore lagged one full poll interval behind the physical
  device even though the write itself succeeded instantly.  The fan entity now keeps a
  short-lived optimistic `_pending_percentage` (default 10 s TTL) that is set only
  after a confirmed-successful airflow write and returned by `percentage`/`is_on` until
  the status registers catch up.  The optimistic value is dropped as soon as a poll
  reports `supply_percentage` / `exhaust_percentage` within 2 pp of the request, on
  timeout, or on `turn_off`; it is never set when the write fails.  Targeted read-back
  stays disabled for the fan write path and no second Modbus client/connection is
  introduced.

- **Targeted read-back now stores enum registers as raw ints, matching the polling
  pipeline** ([#1730](https://github.com/blakinio/thesslagreen/pull/1730)):
  after a successful write to an enum-labelled holding register (e.g.
  `mode`, `season_mode`, `special_mode`, `bypass_off`, `gwc_off`), the targeted
  read-back applied `RegisterDef.decode()` directly, which stores the enum *label*
  (e.g. `'manualny'`, `'ZIMA'`) into `coordinator.data`, while the regular polling
  pipeline (`process_register_value`) stores the raw int for enum registers.  The
  mismatched representation broke `switch.is_on` (a non-empty label string is truthy,
  so a switch turned OFF displayed ON) and `select.current_option` (label not found
  in the reverse option map → "unknown") until the next full poll.  The read-back
  path now reverts enum-label decodes to the raw register value, exactly like the
  polling pipeline.

### Known limitations

- **Fan pending percentage ordering — real-device validation still required**: the
  optimistic `_pending_percentage` publish/refresh ordering
  ([#1730](https://github.com/blakinio/thesslagreen/pull/1730),
  [#1731](https://github.com/blakinio/thesslagreen/pull/1731),
  [#1732](https://github.com/blakinio/thesslagreen/pull/1732)) has so far only been
  validated against unit tests and mocked coordinators. On real AirPack4 hardware the
  post-write `supply_percentage` / `exhaust_percentage` status registers may settle on a
  different cadence than the mocks assume; if the fan slider still snaps back or lags after
  a write on a physical device, the pending-value TTL and the ±2 pp reconciliation threshold
  in `fan.py` may need further tuning. Tracked as a follow-up in
  `docs/real_device_validation.md`.

### Internal

- **Restored `pydantic==2.12.2` dev pin to match
  `pytest-homeassistant-custom-component 0.13.309–0.13.316`** (all of which pin
  `pydantic==2.12.2`).  The Dependabot bump to `pydantic==2.13.4` (#1708) made
  `pip install -r requirements-dev.txt` fail with `ResolutionImpossible`, breaking
  the CI install step on `main`.  Also corrected the stale comment in
  `pyproject.toml` that claimed the plugin pins 2.13.4.

- **Targeted read-back after successful single holding-register writes**: after a
  successful write to a safe single holding register, the coordinator now immediately
  reads back only the written register under the same `_write_lock` (no second
  Modbus connection; no second lock; no `scan_all_registers`).  The returned raw
  value is decoded via the existing `RegisterDef.decode` path and applied to
  `coordinator.data`, then HA listeners are notified directly via
  `async_set_updated_data`.  This eliminates the full coordinator scan that
  previously followed every safe single-register write from `switch`, `number`,
  `select`, `time`, and `text` entities, reducing post-write UI latency from the
  full-scan duration (many seconds) to one short Modbus round-trip.
  When read-back fails the coordinator falls back to a full refresh automatically.
  HA state is updated only from confirmed device data — no optimistic state is used.
  **Registers excluded from targeted read-back** (full_refresh_only or no_readback):
  `hard_reset_settings`, `hard_reset_schedule`, `filter_change`,
  `airflow_rate_change_flag`, `temperature_change_flag`, `cfg_mode_1`, `cfg_mode_2`,
  `pres_check_day_2`, `pres_check_time_2`, all `schedule_*` BCD-time registers,
  all `setting_*` AATT schedule-setting registers, coil registers (function=1),
  and multi-word registers.  Fan writes remain on full_refresh_only because the fan
  entity's displayed percentage reads from `supply_percentage` / `exhaust_percentage`
  (status registers) rather than from the written setpoint registers.  Climate
  writes already use `refresh=False` with manual coordinator refresh calls and are
  unaffected by this change.  Real-device validation is still pending (see
  `docs/real_device_validation.md`).

- **`PARALLEL_UPDATES = 1` declared on all platform modules**: all 10 HA platform
  modules (`sensor`, `binary_sensor`, `number`, `switch`, `select`, `climate`, `fan`,
  `time`, `text`, `button`) now set `PARALLEL_UPDATES = 1` at module level. This aligns
  with HA quality-scale requirements and correctly reflects the serialised single-connection
  Modbus I/O model used by the integration's DeviceClient.

### Fixed

- **Fan/climate/service writes no longer sandwich a full refresh between sequential
  register writes, and fan/climate/service register writes no longer trigger targeted
  read-back**: `async_write_register(..., refresh=False)` disables the *full-refresh
  fallback* but, contrary to the note in the previous changelog entry, it never disabled
  targeted read-back on its own — read-back ran whenever `_targeted_readback_safe()`
  returned `True`, regardless of `refresh`. `ThesslaGreenFan._write_register()` combined
  this with an unconditional caller-side `async_request_refresh()` after every write, so
  `async_set_percentage()` in manual mode produced `write mode=1 → full refresh →
  write air_flow_rate_manual=<value> → full refresh` instead of writing both registers
  back-to-back and refreshing once. `async_write_register()` gains a keyword-only
  `targeted_readback: bool = True` parameter (default preserves existing switch/number/
  select/text behavior). Fan and climate now pass `targeted_readback=False` from their
  `_write_register()` wrappers (and from the one direct `comfort_temperature` write in
  climate), and `async_set_percentage()`'s manual-mode branch writes `mode` and
  `air_flow_rate_manual` with `refresh=False` followed by a single
  `async_request_refresh()`. `services/dispatch.py::write_register()` and
  `write_device_name_chunks()` also pass `targeted_readback=False`, since service writes
  perform their own refresh/logging and may target internal/dangerous registers.
  Additionally, a read-back decode failure (as opposed to a failed read) no longer changes
  `async_write_register()`'s return value — the write already succeeded, so a full refresh
  fallback is used instead (when `refresh=True`) rather than surfacing an exception.
- **Normal scan no longer shows recovered batch failures as Modbus errors in confirmation popup**:
  in a normal config-flow scan on firmware where registers 4/14/15 (`version_patch`,
  `compilation_days`, `compilation_seconds`) are absent, the device returns exception code 2 for
  the 0–15 batch. This caused `mark_failed_addresses` to pre-add addresses 0–3
  (`version_major`, `version_minor`, `day_of_week`, `period`) to `modbus_exceptions` before
  `scan_register_batch` ran its individual fallback probes. The fallback probes succeeded, but
  the addresses remained in `modbus_exceptions`, producing a spurious
  "Błędy Modbus: input_registers: 4" in the confirmation popup.
  Fix: `scan_register_batch` now discards an address from `modbus_exceptions` when its fallback
  probe returns data (protocol-level success), ensuring only truly unrecovered failures count.
- **Truly-absent named registers no longer double-counted as both "Brakujące" and Modbus errors**:
  if a named register fails both batch and individual probe (it is absent on this device),
  it was shown in both `missing_registers_summary` and `modbus_failed_summary`. The confirm
  step now also excludes from the Modbus error count any address already captured in
  `missing_registers`, so it appears only under "Brakujące".
- **`_summarize_address_dict` uses set difference** instead of raw count subtraction when
  computing the exclusion, preventing incorrect counts when the exclude list contains addresses
  not present in the main set.

- **Deep scan raw unsupported ranges no longer shown as Modbus errors in confirmation popup**:
  when `deep_scan=True` (named scan mode), raw input register reads (addresses 0–286) produced
  Modbus exception responses for unsupported ranges and those addresses were incorrectly stored in
  `failed_addresses.modbus_exceptions`, causing the confirmation popup to show
  "Błędy Modbus: input_registers: 269". The fix isolates raw-scan failures in a dedicated
  `deep_scan_raw_failures` bucket (diagnostic-only) and restores `modbus_exceptions` to its
  pre-raw-scan state. The popup now shows the same concise diagnostic note as full-scan mode:
  "deep scan: N unsupported raw ranges (named registers OK)" when named registers are all OK.

### Diagnostics

- `failed_addresses.recovered_batch_failures` added to scan result: per-register-type list of
  addresses that had a batch read failure but were successfully recovered by individual fallback
  probes. Diagnostic-only; never shown as Modbus errors.
- `failed_addresses.unrecovered_modbus_errors` added to scan result: per-register-type list of
  `{addr, name}` dicts for addresses that truly failed both batch and individual probe.
  Enables identification of exactly which named registers caused a Modbus error.
- `failed_addresses.deep_scan_raw_failures` added to scan result: contains input-register
  addresses that failed only during the deep-scan raw accumulation pass; excluded from
  user-facing Modbus error summary.
- Deep scan UI description updated to clarify offline/diagnostic-only purpose and that it is
  not required for normal setup or real-device validation.

---

---

## [2.8.0] - 2026-06-10

> Detailed release notes: [docs/releases/v2.8.x.md](docs/releases/v2.8.x.md).

### ⚠️ Breaking
- Config entry v2/v3 (pre-2023) no longer migrate — remove and re-add the integration.
- Legacy service call entity IDs (`rekuperator_*` old names) no longer mapped —
  update automations to use current entity names.

### Fixed
- **Config-flow no longer reports recovered batch failures as Modbus errors**: when a
  batch register read fails and the fallback individual probes succeed, the recovered
  addresses are no longer counted in the config-flow confirmation "Modbus errors" summary.
  Only addresses where both the batch read AND the individual probe failed are counted.
  Batch failure ranges are preserved in `failed_addresses.batch_failures` for diagnostic use.
- **Deep scan raw unsupported ranges separated from named Modbus errors**: when a full /
  deep register scan is run, the hundreds of expected Modbus exception code 2 responses for
  raw unsupported address ranges are recorded in `batch_failures` (diagnostic) instead of
  `modbus_exceptions`. The confirmation popup shows a brief note
  ("deep scan: N unsupported raw ranges (named registers OK)") rather than inflated error
  counts. Deep scan is documented as offline/diagnostic-only (not for real-device validation).
- **`validate_known_registers` response visible in Developer Tools**: service now registered
  with `SupportsResponse.ONLY` so the full response (including `missing_registers`) is
  visible in Home Assistant Developer Tools → Actions. `available_registers` values are now
  sorted lists instead of sets, making the entire response JSON-safe.
- **`validate_known_registers` individual-read fallback**: when a batch read fails
  (e.g. device returns exception code 2 for one unsupported register in a batch),
  the service now falls back to individual address reads through the same active
  connection. Only truly unsupported registers are marked missing; valid registers
  that shared the failed batch are correctly reported as available.
- **`validate_known_registers` diagnostics**: output now includes
  `missing_registers` (per register type), `failed_ranges` (batches that triggered
  fallback), and `summary.missing_by_type` (per-type missing counts). Existing
  `available_registers` and `summary.{supported,missing}_count` fields are unchanged.
- **Fan percentage clamped to 0–100**
  ([#1682](https://github.com/blakinio/thesslagreen/pull/1682)):
  `fan.thesslagreen_ventilation` no longer reports `percentage` > 100 to Home Assistant
  (device can report up to 109 %). Raw value preserved in
  `extra_state_attributes.supply_percentage`.
- **RTC clock sync: atomic write with read-back**
  ([#1662](https://github.com/blakinio/thesslagreen/pull/1662)):
  clock registers now written atomically and verified with a read-back check to prevent
  stale or partial time writes.
- **Real HA log fixes**
  ([#1660](https://github.com/blakinio/thesslagreen/pull/1660)):
  corrected misleading log messages and entity state reporting identified from real
  Home Assistant log analysis.
- **Stale coordinator IO ownership test guard removed**
  ([#1697](https://github.com/blakinio/thesslagreen/pull/1697)):
  removed stale guard condition that caused the IO ownership test to pass incorrectly
  on certain code paths.
- **Active errors sensor no longer shows «unknown»**: `sensor.rekuperator_active_errors`
  now shows `none` when the coordinator is connected and no error codes are active,
  instead of the misleading «unknown» state.
- **`switch.bypass_off` / `switch.gwc_off` display names corrected**: underlying
  register uses inverse semantics (value 1 = deactivated); renamed to "Bypass Locked" /
  "GWC Locked" (PL: "Bypass zablokowany" / "GWC zablokowany"). Entity IDs and unique
  IDs are unchanged.
- **Device `sw_version` populated from version registers**: when the firmware string is
  unavailable, `sw_version` is assembled from `version_major`, `version_minor`, and
  `cf_version` (e.g. `3.11 CF13`).

### Changed
- **Config-flow confirmation: real scan diagnostics, removed fake `scan_success_rate`**
  ([#1712](https://github.com/blakinio/thesslagreen/pull/1712)):
  the confirmation popup now shows factual scan data (register count, read attempts,
  successful reads, scan duration, missing registers, failed address counts) and splits
  capabilities into detected vs. not-detected/not-confirmed, instead of the misleading
  "Scan success rate: 100%" that was hardcoded whenever any register was detected.
  Fallback indicator changed from English "Unknown" to language-neutral "—".
  No runtime Modbus behavior changed.
- **Cleanup and stabilisation**
  ([#1661](https://github.com/blakinio/thesslagreen/pull/1661)):
  dead code removed and minor consistency fixes across coordinator and entity modules;
  no runtime behavior change.
- **Dangerous entity category/config cleanup**
  ([#1683](https://github.com/blakinio/thesslagreen/pull/1683)):
  advanced/diagnostic entities moved to `entity_category=config`; remain enabled by
  default. No entity IDs or unique IDs changed.
- **AirPack4 register map and vendor alignment**
  ([#1678](https://github.com/blakinio/thesslagreen/pull/1678)/[#1679](https://github.com/blakinio/thesslagreen/pull/1679)):
  register map aligned with AirPack4 vendor reference documentation. No register
  addresses, register names, or entity IDs changed.

### Diagnostics
- **`validate_known_registers` response includes `register_classification` metadata**:
  missing registers now include a classification category (e.g., `optional_firmware_metadata`,
  `hardware_gated`, `internal_service_uart`) in the service response. Existing response
  fields (`available_registers`, `missing_registers`, `failed_ranges`, `summary`) are unchanged.
- **Config-flow confirmation excludes expected-optional firmware failures from Modbus error count**:
  firmware-version registers (addresses ≤ 15, exception code 2) that are expected to be absent
  on some firmware versions are no longer counted in the user-visible "Modbus errors" line during
  config-flow confirmation. The underlying `failed_addresses.modbus_exceptions` field in the scan
  result is unchanged; a new `failed_addresses.expected_optional` field identifies the excluded
  addresses.

### Removed
- Entity registry migrations (`async_migrate_entity_ids`, `async_migrate_unique_ids`)
  no longer run on startup — idempotent since 2022, dead after 2+ years.
- `_entity_registry_migrations.py`, `_legacy.py` (dead code after migration removal).
- `mappings/legacy.py` `LEGACY_ENTITY_ID_OBJECT_ALIASES` (70 entries) and
  `map_legacy_entity_id` function.
- `scanner_io.py` shim (no importers). `tools/py_compile_all.py`.
- `"unit"` key from new config entries. v2/v3 migration paths.

### Internal
- **Removed dead RTU-over-TCP helper duplicate**:
  deleted `custom_components/thessla_green_modbus/transport/rtu_over_tcp.py` (free
  `validate_crc`/`build_read_frame` functions never imported by production code);
  retargeted CRC/frame helper tests in
  `tests/test_modbus_transport_rtu_over_tcp_helpers.py` to
  `RawRtuOverTcpTransport._validate_crc` and `RawRtuOverTcpTransport._build_read_frame`
  in the live transport; updated expected exception type from `ValueError` to
  `ModbusIOException`; added negative guard test to prevent re-introduction of the
  dead module. No runtime Modbus behavior changed.
- **Improved `validate_known_registers` missing-register diagnostics**: `missing_registers`
  in the service response now contains sorted lists (deterministic, JSON-serializable) instead
  of sets. `summary` gains `retried_individual_count` (individual fallback reads performed after
  batch failures). DEBUG logging changed from a single combined message to per-register-type
  lines (`missing input_registers: [...]`, `missing holding_registers: [...]`, etc.) so
  individual types can be filtered in HA logs. No runtime Modbus behavior changed.
  Real-device evidence committed: stable result (supported=338, missing=19) across 3 runs,
  no `transaction_id` mismatch observed (PRs #1709/#1711).
- **Removed obsolete PDF-based register validation**: deleted
  `tests/test_register_pdf_mapping.py` and the committed vendor PDF
  `ProtokolModbusRTU_AirPack4.pdf`. The five non-PDF spot-check assertions
  (addresses, function codes, units, access flags, enum values) were migrated
  to `tests/test_register_json_contracts.py` using `thessla_green_registers_full.json`
  only. The `pypdf`/PDF coverage test is superseded by `test_registers_vs_reference.py`
  (vendor JSON). `*.pdf binary` removed from `.gitattributes`; P2-2 audit item retired.
- **Fixed Codecov upload configuration** (CI only): corrected `file:` → `files:` input
  (the old key was silently ignored by `codecov/codecov-action@v6`); added
  `disable_search: true` so only `coverage.xml` is uploaded and
  `docs/airpack4_vendor_reference_coverage.json` is no longer auto-discovered;
  set `fail_ci_if_error: false` — upload is **optional** (no `CODECOV_TOKEN` secret
  is configured; add one to enable authenticated uploads).
- **Coordinator proxy cleanup and DeviceClient IO ownership**
  ([#1664](https://github.com/blakinio/thesslagreen/pull/1664)/[#1669](https://github.com/blakinio/thesslagreen/pull/1669)/[#1690](https://github.com/blakinio/thesslagreen/pull/1690)/[#1694](https://github.com/blakinio/thesslagreen/pull/1694)/[#1696](https://github.com/blakinio/thesslagreen/pull/1696)):
  removed coordinator delegate methods and `_ModbusIOMixin`; `DeviceClient` is now the
  true single IO owner. 15 new tests added in `test_coordinator_io_ownership.py`.
- **Schedule register discovery regression tests**
  ([#1681](https://github.com/blakinio/thesslagreen/pull/1681)):
  new regression tests to prevent future regressions in schedule register discovery.
- **Tightened Claude agent guidelines**
  ([#1695](https://github.com/blakinio/thesslagreen/pull/1695)):
  `claude.md` hardened with stricter rules for branch management, public contract
  preservation, and changelog update policy.

### Docs
- **Real-device missing register classification documented**:
  `docs/real_device_validation.md` updated with HA OS 17.3 / HA Core 2026.6.1 validation
  results. All 19 missing registers classified into 7 categories. New §4.4 "Expected missing /
  optional registers on tested device" added.
- **README badge cleanup and register validation wording**:
  removed broken GitHub Releases badge (no tag/release exists for shields.io to resolve);
  replaced "automatyczne skanowanie rejestrów" with "automatyczna detekcja dostępnych funkcji
  urządzenia oraz walidacja znanych rejestrów"; clarified that `validate_known_registers`
  reuses the active Modbus connection (safe during polling) while `scan_all_registers` opens
  a separate connection (offline/advanced only); added warning block and `quality_scale: bronze`
  notice.
- **Real-device HA log evidence**
  ([#1689](https://github.com/blakinio/thesslagreen/pull/1689)):
  committed real-device Home Assistant log evidence supporting entity state and
  behavior validation in `docs/real_device_validation.md`.

### Tests
- Removed: `test_legacy_entity_id_aliases.py`, `test_legacy_entity_migration.py`,
  `test_services_legacy_ids.py`.
- Fixed: `test_migration.py` — v1/v2/v3 now expect `False`; added explicit v4 test.
- Infrastructure: `pytest-homeassistant-custom-component` plugin re-enabled,
  `conftest.py` rebuilt on real HA fixtures.
- `test_coordinator.py`: removed 130-line module-level HA stub block.
- `test_services.py`: removed 18 HA module stubs.
- `test_config_flow.py`: consolidated duplicate register loader stubs.
- `test_coordinator_coverage.py`: replaced `is not None` assertions with type checks.
- `test_optimized_integration.py`: replaced `CoordinatorMock` with `MagicMock`.

### CI / Release Readiness
- Added `hassfest` CI job (`home-assistant/actions/hassfest@main`) — validates
  `manifest.json` and integration structure on every PR and push.
- Added `hacs` CI job (`hacs/action@main`, `category: integration`) — validates
  `hacs.json` and HACS repository requirements on every PR and push.
- **Fixed hassfest/HACS CI failures**: removed non-HA `files` key from `manifest.json`
  (not in `homeassistant.loader.Manifest` TypedDict; caused both CI jobs to fail).
  HACS installs the entire `custom_components/thessla_green_modbus/` directory
  automatically when `files` is absent. `test_manifest_files.py` updated accordingly.
- Added `docs/real_device_validation.md` — structured checklist and evidence template
  for real-device validation against ThesslaGreen AirPack hardware.
- Implemented `repairs.py` — `async_create_fix_flow` returns `ConfirmRepairFlow` for
  `modbus_write_failed` and any future repair issues.
- Applied `disabled_by_default` for entities with `EntityCategory.DIAGNOSTIC` —
  `sensor.py` and `binary_sensor.py` now set `_attr_entity_registry_enabled_default = False`
  for all diagnostic-category entities. User-facing control/status entities unchanged.
- Updated `README_en.md` — Python version corrected to 3.13+, diagnostics privacy
  section added, quality/release status table added, links to audit docs added.
- Entity mapping validation: 366 entities confirmed.
- `pydantic` remains pinned at `2.12.2` — PR #1567 (Dependabot pydantic update)
  is separate and untouched.

### Confirmed correct (no code change)
- `binary_sensor.fire_alarm`: raw True = NC contact closed = no alarm = `off` state.
  Correct and intentional; documented with tests.
- `binary_sensor.dp_duct_filter_overflow`: raw True = problem detected = `on` state.
  Correct for a filter pressure-differential overflow; documented with tests.
- Polish state wording "nie działa" appears only in S30/S31 error-code sensor names,
  not in normal inactive state labels. No change needed.

### Needs vendor confirmation
- `number.airing_coef` / `number.airing_switch_coef`: device reports values (50, 0)
  outside the declared range 100–150. No write-range change until vendor docs confirm
  whether these are valid set-points or factory defaults.

---

## [2.7.0] — Dead fallback & pragma cleanup

### Removed
- `_get_platforms` try/except for missing `homeassistant.const.Platform`; now uses `Platform(d)` directly.
- `scanner_register_maps.py` loader fallback stubs (5 dummy functions).
- `modbus_exceptions.py` fallback exception classes; now a direct pymodbus re-export.
- pydantic v1 compatibility shims in `registers/schema.py` (`RootModel`, `model_validator`).
- `from types import SimpleNamespace` in `services.py`.
- ~100 spurious `# pragma: no cover - defensive` annotations across entity platform files,
  coordinator.py, registers/schema.py, scanner_device_info.py, and support modules.

### Changed
- `services.py`: `SimpleNamespace` → typed `_MappedCall` inner class.
- `config_flow.py`: collapsed duplicate `isinstance` branches in `_prepare_entry_payload`
  and `_async_show_confirmation` caps_obj handling.
- `modbus_helpers.py`: cleaned pragma comments on framer imports.
- `scanner/core.py`: simplified pymodbus.client attach error handling.
- `_coordinator_io.py`, `registers/loader.py`, `modbus_transport.py`: pragma comments
  simplified (removed verbose suffixes, kept `# pragma: no cover` where truly unreachable).

---

## [2.6.0] — Dead fallback cleanup

### Removed
- `OptionsFlow` defensive `getattr(super(), ...)` wrappers for `async_show_form`,
  `async_create_entry`, `async_abort` — HA guarantees these since 2022.
- `try/except ImportError` fallbacks for `entity_registry` in `__init__.py`,
  `get_registers_by_function` in `const.py`, `get_all_registers` in
  `mappings/_helpers.py` and `mappings/_loaders.py`, and 5 loader stubs in
  `scanner/core.py` — all guarding symbols always present given
  `homeassistant>=2026.1.0`.
- `try/except (ImportError, AttributeError)` dead path in
  `register_map._resolve_entity_domain`; ENTITY_MAPPINGS is always available.
- `hass is not None` guard in `_load_scanner_module`; `validate_input` now
  requires `HomeAssistant` (not `None`).
- `# re-exported for test monkeypatching` comment on `scanner/core.asdict`.
- Unused `RegisterDef` TYPE_CHECKING imports in `const.py`, `mappings/_helpers.py`,
  `mappings/_loaders.py`, `scanner/core.py` (were only needed for fallback stubs).

### Changed
- `_entity_registry_migrations`: uses `er.async_entries_for_config_entry` directly
  in both `async_migrate_entity_ids` and `async_migrate_unique_ids` instead of
  `getattr(er, "async_entries_for_config_entry", None)` + `callable()` guard.
- `list[object]` annotation in `async_migrate_entity_ids` replaced with `list[Any]`.
- `scanner/core.py` now imports only `async_get_all_registers` from `registers.loader`
  (the other 4 symbols were only present as fallback re-exports).

---

## [2.5.1] — Config flow cleanup

### Removed
- 5 defensive `getattr(super(), ...)` method wrappers in `ConfigFlow`
  (`async_set_unique_id`, `_abort_if_unique_id_configured`, `async_show_form`,
  `async_create_entry`, `async_abort`). These methods exist in
  `homeassistant.config_entries.ConfigFlow` since HA 2022; the fallbacks
  were test-compat code for SimpleNamespace stubs.
- `try/except ImportError` guard around `homeassistant.helpers` imports in
  `_entity_registry_migrations.py`. HA helpers are always available given
  manifest requirement >=2026.1.0.
- Defensive `getattr(super(), "async_shutdown", None)` in
  `ThesslaGreenModbusCoordinator.async_shutdown`; replaced with direct
  `await super().async_shutdown()`.

### Changed
- `_load_scanner_module` in `config_flow.py` simplified: removed
  `getattr(hass, "async_add_executor_job", None)` fallback and
  `inspect.isawaitable` check; now uses `hass.async_add_executor_job` directly.
  Parameter type narrowed from `Any` to `HomeAssistant | None`.
- `BIT_ENTITY_KEYS` in `_legacy.py` comment updated to match canonical
  "NOT LEGACY — active functional requirement" format.
- `VERSION = 4` class attribute in `ConfigFlow` no longer has spurious
  `# pragma: no cover - defensive` annotation.

---

## [2.5.0] — Legacy cleanup (BREAKING)

### ⚠️ Breaking changes
- Config entry version 1 (pre-2021) no longer migrates automatically — remove
  and re-add the integration.
- Polish-language entity IDs (`rekuperator_moc_odzysku_ciepla` etc.) no longer
  have migration aliases — update automations to use current English entity names.
- Legacy fan entity IDs (`number.rekuperator_predkosc`, `number.rekuperator_speed`)
  are not cleaned up automatically — remove them manually from entity registry if
  present.

### Removed
- `config_entry.version == 1` migration path.
- `LEGACY_DEFAULT_PORT = 8899` constant.
- Polish-language entity_id aliases in `mappings/legacy.py`.
- `LEGACY_FAN_ENTITY_IDS` list and `async_cleanup_legacy_fan_entity` function.
- `predkosc`/`speed` entries from `LEGACY_ENTITY_ID_ALIASES`.
- `scanner_core.py` shim — use `scanner.core` directly.

### Changed
- `scanner_io.py` reduced to thin re-export shim of `scanner/io.py`.
- `BIT_ENTITY_KEYS` documented as active functional requirement (e_196_e_199
  bitmask), not legacy.
- `LEGACY_KEY_RENAMES` annotated with deprecation schedule (2.7.0+).

---

## [2.4.4] — Python 3.13 environment enforcement

### Added
- `.python-version` (pyenv) and `.tool-versions` (asdf) declare Python 3.13.
- Explicit `sys.version_info` check in `__init__.py` — clear error on older Python.
- `.pre-commit-config.yaml` rebuilt: `default_language_version: python3.13`,
  replaced `black`+`isort` with `ruff-format`, expanded mypy scope to full package.
- README development setup section.

---

## [2.4.3] — Critical fix: ImportError at integration load

### Fixed
- `_coordinator_update.py` imported `utcnow` from `utils` but the function
  did not exist — integration failed to load in HA with `ImportError`. Added
  `utcnow()` helper to `utils.py`.
- Ruff I001 in `coordinator.py` (import order) and F401 in `__init__.py`
  (unused `CONF_SLAVE_ID`).
- 9 mypy errors in `_entity_registry_migrations.py` (`dict[str, object]`
  replaced with `dict[str, Any]` + `getattr` access).

---

## [2.4.2] — Detox regression fixes

Fixes several test-compat fallbacks that had crept back into production code
after the 2.4.1 detox, and completes the `CoordinatorConfig` refactor started
in 2.4.1.

### Removed
- `_supports_typed_factory` function and dual-path coordinator construction in `_setup.async_create_coordinator`. Production code no longer imports `unittest.mock.Mock` at runtime; `from_config` is the single code path.
- `try/except ImportError` fallbacks in `_compat.py`. `_compat.py` is now a pure re-export module as intended after v2.4.0.
- `DhcpServiceInfo` / `ZeroconfServiceInfo` / `ConfigFlowResult` fallback imports in `config_flow.py`. These HA symbols are stable; direct imports are used.
- `PLATFORMS` string-list fallback in `const.py`. Direct `Platform` enum is used.
- `get_all_registers()` fallback in `register_map.py`. Register loader failure now raises import errors explicitly instead of returning an empty register list.

### Changed
- Comment in `modbus_helpers._call_modbus` updated to describe production behavior (pymodbus signature-introspection fallback) instead of referring to test `Mock` handling.
- Added a design-note docstring on `mappings/_loaders._get_parent` explaining that the `sys.modules`-based attribute resolution pattern is intentional and should not be removed in future audits.

### Added
- `ThesslaGreenModbusCoordinator.config` attribute — a `CoordinatorConfig` dataclass snapshot of initialization parameters. This is a non-breaking addition; existing `coordinator.host`, `coordinator.port`, etc. attributes continue to work.

### Migration notes
- Tests that replaced `ThesslaGreenModbusCoordinator` with a plain `Mock()` for `async_create_coordinator` will fail because `from_config` is now called unconditionally. Use `MagicMock(spec=ThesslaGreenModbusCoordinator)` or patch `from_config` explicitly.
- Tests that depended on import-time `get_all_registers` fallbacks should monkey-patch loader functions in test setup instead.

---

## [2.4.1] — Detox completion

Completes the test-compat cleanup started in 2.4.0. Eight remaining spots where
production code tested for or worked around test mocks have been removed.

### Removed
- `_compat_asdict` wrapper in `scanner_device_info.py` that existed for test-patch compatibility. Callers now use `dataclasses.asdict` directly.
- `inspect.signature` filtering of coordinator kwargs in `__init__.py`. Incomplete coordinator stubs now raise `TypeError` explicitly instead of silently dropping kwargs.
- `sys.modules.get()` check before dynamic coordinator import in `__init__.py`. Module import now goes straight through the Home Assistant executor.
- `try/except TypeError` around `async_setup_options` / `async_setup_entity_mappings` in `_async_setup_mappings`. Real bugs in option setup are no longer masked by "Skipping in mock context" debug logs.
- `_HAS_HA` detection and `"pytest" in sys.modules` check in `const.py`. Production and test paths now execute identical code.
- Dynamic self-import via `import_module(__name__)` in `coordinator._create_scanner`. Direct reference to `ThesslaGreenDeviceScanner.create()` is used.
- `inspect.signature(write_cb)` check in `entity._write_register`. Direct call to `coordinator.async_write_register` with explicit kwargs.
- Trivial `_schema` and `_required` wrappers in `config_flow.py`. Direct `vol.Schema` / `vol.Required` calls are now used throughout.

### Migration notes
- Tests that relied on production silently filtering kwargs or falling back to sync option setup may need to use `MagicMock(spec=...)` or `pytest-homeassistant-custom-component` fixtures.
- `scanner_core.asdict` is no longer used internally, so patching it in tests has no effect.

---

## [2.4.0] — Dead code cleanup and production detox

- Removed orphan scanner mixin modules, legacy `register_addresses.py`, and root `validate.yaml`.
- Simplified compatibility layer in `_compat.py` to direct Home Assistant re-exports.
- Added register cross-check tooling: `tools/compare_registers_with_reference.py` and `tests/test_registers_vs_reference.py`.
- Removed `entity_mappings.py` shim and updated imports to `mappings`.
- Cleaned coordinator and setup error paths (`UpdateFailed`, reauth flow, fallback wrappers).

---

## [2.3.9]

### Changed
- Continued Fix #6 by extracting additional scan-orchestration helpers into `scanner/registers.py`: named-scan runner, scan-block computation, and missing-register collection.
- `scanner/core.py` now delegates `_run_named_scan`, `_compute_scan_blocks`, and `_collect_missing_registers` to the register module, further reducing scanner core complexity.

---

## [2.3.8]

### Changed
- Continued Fix #6 by extracting scanner I/O logic into `scanner/io.py` (input/holding/coil/discrete reads, retry/backoff wrappers, chunked block reads, and failure tracking helpers).
- `scanner/core.py` now delegates read-path methods (`_read_input`, `_read_holding`, `_read_bit_registers`, `_read_coil`, `_read_discrete`, `_read_register_block`) to the dedicated I/O module.

---

## [2.3.7]

### Changed
- Continued Fix #6 with real method extraction from `scanner/core.py` into dedicated modules: `scanner/capabilities.py`, `scanner/firmware.py`, and `scanner/registers.py`.
- `ThesslaGreenDeviceScanner` now delegates capability analysis, firmware parsing, and named-register scan routines to those modules, reducing core-class responsibility while keeping behavior unchanged.

---

## [2.3.6]

### Changed
- Completed the scanner refactor by moving the scanner runtime implementation from `scanner_core.py` into `scanner/core.py` and keeping `scanner_core.py` as a backwards-compatible shim alias.
- Updated integration imports to use the new scanner package (`from .scanner import ...`) in coordinator and services modules.
- Kept grouped scanner modules (`firmware.py`, `registers.py`, `io.py`, `capabilities.py`) aligned with the new package structure while preserving runtime behavior and test compatibility.

---

## [2.3.5]

### Changed
- Fully consolidated service entity/coordinator resolution in `services.py` by routing all handlers through `_iter_target_coordinators(...)`, removing repeated `_extract_legacy_entity_ids(...)` / `_get_coordinator_from_entity_id(...)` boilerplate across mode, schedule, parameter, maintenance, and data service groups.

---

## [2.3.4]

### Changed
- Added a new `scanner/` package structure (`core.py`, `firmware.py`, `registers.py`, `io.py`, `capabilities.py`) as compatibility facades to prepare the large scanner refactor while preserving existing `scanner_core` behavior.
- Added `_iter_target_coordinators(...)` helper in `services.py` and used it in data service handlers to reduce repeated entity/coordinator resolution boilerplate.

### Notes
- `scanner_core.py` remains the runtime implementation in this release for backward compatibility and stable test behavior; new package modules expose grouped scanner concerns for incremental migration.

---

## [2.3.3]

### Changed
- Removed dead `StrEnum` Python<3.11 compatibility fallback in `registers/schema.py`. Manifest and `pyproject.toml` both require Python >=3.13, so the fallback was unreachable.
- Extracted `_handle_update_error` helper in coordinator to consolidate duplicated error handling across three `except` branches in `_async_update_data`.
- Extracted `_parse_backoff_jitter` as a `@staticmethod` in coordinator, making jitter parsing directly unit-testable without constructing a full coordinator.
- Removed redundant property indirection on `coordinator.client`; direct attribute access now provides equivalent behavior.

### Fixed
- `_async_update_data` now explicitly handles `asyncio.CancelledError` by closing the transport before re-raising, preventing inconsistent mid-read transport state on integration unload.

### Added
- Direct unit tests for `_parse_backoff_jitter` covering numeric, string, sequence, and fallback inputs.
- Regression test ensuring cancellation handling in `_async_update_data` does not increment failed read counters and still disconnects cleanly.

---

## [2.3.2]

### Changed
- Replaced runtime `getattr(...)` dispatch in `climate.py` with direct imports from `homeassistant.components.climate`, removing dead fallback paths and restoring strict typing support.
- Added explicit mixin attribute and stub-method declarations in coordinator/scanner mixins so mypy can validate cross-mixin contracts without runtime changes.
- Added `assert self.client is not None` after transport reconnection in Modbus transport read/write methods to make `None` narrowing explicit for static typing.
- Aligned conditional fallback shim signatures in register loader adapters with real loader APIs.
- Refactored BCD clock decode in `_coordinator_capabilities.py` from `all(...)` generator checks to explicit `is not None` guards for mypy narrowing.

### Fixed
- Removed stale/incorrect `# type: ignore[...]` tags that no longer matched emitted mypy error codes.
- Added stricter typing/guard fixes in scanner and register helpers to reduce strict-mode typing failures.

---

## [2.3.1]

### Fixed
- Fixed `set_airflow_schedule` / `set_intensity` writing to nonexistent register names. Services now write real `schedule_<season>_<dow>_<n>` and `setting_<season>_<dow>_<n>` register pairs, with `season` support and deprecated `end_time` handling.
- Fixed FC03 partial-response tail reverting after write: when AirPack4 FW 3.11 returns fewer registers than requested in a batch, the missing tail is now retried with individual reads instead of being marked as failed, preventing the UI from reverting to stale values after a write.
- Fixed cache strip stripping registers on newer firmware: `_apply_scan_cache` now only strips `KNOWN_MISSING_REGISTERS` for FW 3.x devices; caches built on FW 4.x+ are no longer corrupted until the next full scan.
- Refactored sensor sentinel handling: consolidated three separate 0x8000 checks into a single ordered sentinel gate in `_process_register_value`, eliminated magic number `32768` in favour of `SENSOR_UNAVAILABLE`, and added public `is_temperature()` alias on register definitions.
- Fixed service schema validation gaps: `set_bypass_parameters.min_outdoor_temperature` now accepts `-20..40 °C`, and `set_gwc_parameters` now validates `min_air_temperature < max_air_temperature`.

### Changed
- Replaced `pyflakes` with `ruff` as the primary linter; `# noqa: F401` directives on intentional side-effect imports are now respected.
- Removed unused `_HAS_HA` dead code from `mappings/__init__.py`.

---

## [2.2.0] - 2025-02-15

### Added
- Pre-commit configuration with ruff, black, isort, and mypy for consistent checks.
- GitHub Actions workflow covering linting, typing, pytest, hassfest, and HACS validation.

### Changed
- Bumped integration version metadata and aligned minimum Home Assistant requirement to 2024.12.0.

---

## [2.0.0] - 2025-01-XX — Major optimization release

### Added
- Constant Flow register names (`cf_version`, `supply_air_flow`, `exhaust_air_flow`) for Series 4 units.
- Capability detection for Constant Flow and HEWR water removal.
- Airflow unit option allowing `%` or `m³/h` reporting.

### Changed
- Optimized register grouping (47 → 18 Modbus calls per cycle).
- Enforced single-request temporary writes, widened airflow handling to 0–150%, and normalized temperature sentinel values to `unknown`.
- Updated minimum Home Assistant version to 2026.1.0.
- Coordinator reads now retry transient Modbus failures with backoff and reconnects between attempts.
- Climate OFF handling now relies only on the on/off register (no OFF→AUTO mapping).

### Removed
- Custom Modbus client in favor of native `AsyncModbusTcpClient`.

---

## [1.0.0] - 2023-XX-XX — Initial release

### Added
- Basic Modbus RTU/TCP communication.
- Core temperature sensors (Outside, Supply, Exhaust).
- Basic climate control entity.
- Simple binary sensors for system status.
- Configuration through UI.
- HACS integration support.

---

[Unreleased]: https://github.com/blakinio/thesslagreen/compare/v2.8.0...HEAD
[2.8.0]: https://github.com/blakinio/thesslagreen/releases/tag/v2.8.0
[2.7.0]: https://github.com/blakinio/thesslagreen/releases/tag/v2.7.0
[2.6.0]: https://github.com/blakinio/thesslagreen/releases/tag/v2.6.0
[2.5.1]: https://github.com/blakinio/thesslagreen/releases/tag/v2.5.1
[2.5.0]: https://github.com/blakinio/thesslagreen/releases/tag/v2.5.0
[2.4.4]: https://github.com/blakinio/thesslagreen/releases/tag/v2.4.4
[2.4.3]: https://github.com/blakinio/thesslagreen/releases/tag/v2.4.3
[2.4.2]: https://github.com/blakinio/thesslagreen/releases/tag/v2.4.2
[2.4.1]: https://github.com/blakinio/thesslagreen/releases/tag/v2.4.1
[2.4.0]: https://github.com/blakinio/thesslagreen/releases/tag/v2.4.0
[2.3.9]: https://github.com/blakinio/thesslagreen/releases/tag/v2.3.9
[2.3.8]: https://github.com/blakinio/thesslagreen/releases/tag/v2.3.8
[2.3.7]: https://github.com/blakinio/thesslagreen/releases/tag/v2.3.7
[2.3.6]: https://github.com/blakinio/thesslagreen/releases/tag/v2.3.6
[2.3.5]: https://github.com/blakinio/thesslagreen/releases/tag/v2.3.5
[2.3.4]: https://github.com/blakinio/thesslagreen/releases/tag/v2.3.4
[2.3.3]: https://github.com/blakinio/thesslagreen/releases/tag/v2.3.3
[2.3.2]: https://github.com/blakinio/thesslagreen/releases/tag/v2.3.2
[2.3.1]: https://github.com/blakinio/thesslagreen/releases/tag/v2.3.1
[2.2.0]: https://github.com/blakinio/thesslagreen/releases/tag/v2.2.0
[2.0.0]: https://github.com/blakinio/thesslagreen/releases/tag/v2.0.0
[1.0.0]: https://github.com/blakinio/thesslagreen/releases/tag/v1.0.0
