# Maintainability audit

Date: 2026-04-30

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt` *(passed; pip warning about root user)*
- `ruff check custom_components tests tools` *(passed)*
- `python -m compileall -q custom_components/thessla_green_modbus tests tools` *(passed)*
- `python tools/compare_registers_with_reference.py` *(passed; reports 62 extra integration entries and 242 name mismatches to verify with vendor)*
- `python tools/check_maintainability.py` *(passed)*
- `pytest tests/ -q` *(passed; 4 skipped)*
- `python tools/validate_entity_mappings.py` *(passed; 366 entities validated)*

## 1) CI status and maintained CI gates

The repository CI workflow (`.github/workflows/ci.yaml`) currently enforces three jobs:

1. **Lint**: dependency install, `ruff check custom_components tests tools`, `python -m compileall -q custom_components/thessla_green_modbus tests tools`, `python tools/compare_registers_with_reference.py`, and `python tools/check_maintainability.py`.
2. **Tests**: `pytest --cov --cov-report=xml --cov-report=term -q` plus Codecov upload.
3. **Entity mappings validation**: `python tools/validate_entity_mappings.py`.

Maintained gates intentionally exclude removed non-maintained checks (`black`, `isort`, `mypy`, `hassfest`, and HACS validation).

## 2) Largest files (by non-empty lines)

1. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (734)
2. `custom_components/thessla_green_modbus/scanner/io_read.py` (613)
3. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (569)
4. `tests/test_entity_mappings.py` (526)
5. `tests/test_coordinator.py` (502)
6. `tests/test_modbus_helpers.py` (482)
7. `tests/test_register_loader.py` (478)
8. `custom_components/thessla_green_modbus/scanner/core.py` (477)
9. `tests/test_scanner_io_coverage.py` (472)
10. `custom_components/thessla_green_modbus/modbus_helpers.py` (456)
11. `tests/test_register_decoders.py` (455)
12. `custom_components/thessla_green_modbus/coordinator/schedule.py` (448)
13. `custom_components/thessla_green_modbus/mappings/_static_discrete.py` (438)
14. `custom_components/thessla_green_modbus/config_flow.py` (437)
15. `custom_components/thessla_green_modbus/const.py` (428)

Interpretation: the largest remaining production hotspots are coordinator orchestration, scanner input-read path, and mapping-builder composition.

## 3) Largest classes

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (658)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (460)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (449)
4. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (293)
5. `RegisterDef` in `registers/register_def.py` (268)
6. `ThesslaGreenFan` in `fan.py` (254)
7. `_CoordinatorCapabilitiesMixin` in `coordinator/capabilities.py` (230)
8. `ConfigFlow` in `config_flow.py` (217)
9. `BaseModbusTransport` in `modbus_transport_base.py` (210)
10. `ThesslaGreenBinarySensor` in `binary_sensor.py` (175)

## 4) Largest functions/methods

1. `register_maintenance_services` in `services_handlers_maintenance.py` (136)
2. `async_write_register` in `coordinator/schedule.py` (131)
3. `read_input` in `scanner/io_read.py` (129)
4. `run_full_scan` in `scanner/orchestration.py` (125)
5. `validate_input_impl` in `config_flow_device_validation.py` (123)
6. `_post_process_data` in `coordinator/capabilities.py` (120)
7. `read_with_retry` in `coordinator/retry.py` (106)
8. `migrate_unique_id` in `const.py` (100)
9. `_call_modbus` in `modbus_helpers.py` (97)
10. `async_write_registers` in `coordinator/schedule.py` (96)

## 5) Completed refactors reflected in current dev state (latest merged batch #1481 and #1485-#1490)

- **#1481 scanner orchestration helpers**: scan orchestration was further split into helper boundaries (`run_full_scan`, `scan_device`) and scanner phase transitions are now concentrated in orchestration modules.
- **#1485 config flow validation result handling**: config-flow device validation now centralizes result-normalization and validation output handling to reduce conditional sprawl in flow entry points.
- **#1486 modbus helper logic**: Modbus call/helper behavior was consolidated, reducing duplicated call/error-handling paths around `_call_modbus`.
- **#1487 maintenance service handlers**: maintenance handler registration/use-cases were split into dedicated service handler modules; service complexity hotspot now sits in a smaller, isolated target (`register_maintenance_services`).
- **#1488 mapping payload helpers**: mapping payload-building responsibilities were pushed into helpers, reducing repeated payload assembly logic across mapping paths.
- **#1489 coordinator connection state**: coordinator connection-state transitions were clarified and localized in coordinator-side modules/mixins.
- **#1490 scanner input read path**: scanner read-path handling was further segmented, with `scanner/io_read.py` now the explicit concentration point for input-read behavior.

## 6) Current invariants and architectural constraints (verified)

- `coordinator/` is canonical.
- Top-level `custom_components/thessla_green_modbus/coordinator.py` is absent and must remain absent.
- No compatibility shims.
- No proxy modules.
- No re-export-only modules.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant.

## 7) Remaining production hotspots and recommended next PRs

1. Continue splitting `custom_components/thessla_green_modbus/coordinator/coordinator.py` (734 non-empty lines) by isolating coordinator lifecycle/state and orchestration edges into narrower modules.
2. Continue decomposition of `custom_components/thessla_green_modbus/scanner/io_read.py` (613 lines), prioritizing extraction of retry/error normalization and grouped read batching helpers around `read_input`.
3. Continue decomposition of `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (569 lines), focusing on domain-specific payload builders and branch reduction.
4. Reduce `custom_components/thessla_green_modbus/scanner/core.py` (477 lines) by splitting setup/state bookkeeping from scanner runtime behavior.
5. Reduce `register_maintenance_services` (136 lines) by extracting registration slices (service schema binding, target resolution wiring, and handler registration loops).

## 8) Validation outcome summary

- Full pytest: **passed** (4 skipped).
- Maintainability gate: **passed**.

## 9) Safe CI hardening plan (staged, non-disruptive)

As of this audit, CI-required gates remain intentionally limited to Ruff linting, compile checks, register/reference comparison, maintainability checks, pytest+coverage, and entity mapping validation. The following staged plan can increase quality signal **without** re-introducing previously excluded blocking checks (`black`, `isort`, `mypy`, `hassfest`, HACS validation):

### Stage A (documentation + local developer workflow only)

1. Keep CI required jobs unchanged.
2. Encourage local informational checks for:
   - `ruff format --check custom_components tests tools`
   - `ruff check --select I custom_components tests tools`
3. Treat these as local feedback only until file churn drops; do not auto-format in broad sweep PRs.

### Stage B (optional informational CI job, non-blocking)

If desired, add a separate workflow job that runs the two checks above and is explicitly marked non-blocking (for example, `continue-on-error: true`). This job should:

- avoid touching required branch protection gates,
- avoid secrets and external services,
- only report drift trend.

### Stage C (targeted adoption after convergence)

When `ruff format --check` and import-order checks are routinely clean on active files, enforce them incrementally by path or module group in small PRs, never as a one-shot repository-wide rewrite.

### Current readiness snapshot

- `ruff format --check custom_components tests tools`: **fails** currently (94 files would be reformatted).
- `ruff check --select I custom_components tests tools`: **passes** currently.

Conclusion: repository is ready for import-order enforcement (already clean), but not ready for mandatory format enforcement without a dedicated formatting campaign.
