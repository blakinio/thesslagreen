# Maintainability audit

Date: 2026-05-03

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt` *(passed; pip warning about root user)*
- `ruff check custom_components tests tools` *(passed)*
- `python -m compileall -q custom_components/thessla_green_modbus tests tools` *(passed)*
- `python tools/compare_registers_with_reference.py` *(passed; reports 62 extra integration entries and 242 name mismatches to verify with vendor)*
- `python tools/check_maintainability.py` *(passed)*
- `pytest tests/ -q` *(passed; 4 skipped)*
- `python tools/validate_entity_mappings.py` *(passed; 366 entities validated)*
- `find custom_components/thessla_green_modbus -maxdepth 2 -name "coordinator.py" -print` *(passed; only canonical `coordinator/coordinator.py` exists)*
- `rg "from homeassistant|import homeassistant" custom_components/thessla_green_modbus/core custom_components/thessla_green_modbus/transport custom_components/thessla_green_modbus/registers custom_components/thessla_green_modbus/scanner || true` *(passed; no matches)*
- `rg "compat|shim|proxy|re-export|legacy" custom_components tests docs || true` *(informational; expected policy/test/docs references plus existing compatibility spots outside forbidden areas)*

## 1) CI status and maintained CI gates

The repository CI workflow (`.github/workflows/ci.yaml`) currently enforces three jobs:

1. **Lint**: dependency install, `ruff check custom_components tests tools`, `python -m compileall -q custom_components/thessla_green_modbus tests tools`, `python tools/compare_registers_with_reference.py`, and `python tools/check_maintainability.py`.
2. **Tests**: `pytest --cov --cov-report=xml --cov-report=term -q` plus Codecov upload.
3. **Entity mappings validation**: `python tools/validate_entity_mappings.py`.

Maintained gates intentionally exclude removed non-maintained checks (`black`, `isort`, `mypy`, `hassfest`, and HACS validation).

## 2) Largest files (by non-empty lines)

1. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (712)
2. `custom_components/thessla_green_modbus/scanner/io_read.py` (650)
3. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (560)
4. `tests/test_entity_mappings.py` (526)
5. `tests/test_coordinator.py` (502)
6. `tests/test_modbus_helpers.py` (482)
7. `tests/test_scanner_io_coverage.py` (472)
8. `custom_components/thessla_green_modbus/coordinator/schedule.py` (472)
9. `custom_components/thessla_green_modbus/scanner/core.py` (470)
10. `custom_components/thessla_green_modbus/modbus_helpers.py` (456)
11. `custom_components/thessla_green_modbus/mappings/_static_discrete.py` (438)
12. `custom_components/thessla_green_modbus/const.py` (428)
13. `custom_components/thessla_green_modbus/config_flow.py` (428)
14. `tests/test_entity_data_correctness.py` (427)
15. `tests/test_register_loader.py` (402)

Interpretation: the largest remaining production hotspots are coordinator orchestration, scanner input-read path, and mapping-builder composition.

## 3) Largest classes

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (628)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (489)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (441)
4. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (308)
5. `RegisterDef` in `registers/register_def.py` (268)
6. `ThesslaGreenFan` in `fan.py` (254)
7. `_CoordinatorCapabilitiesMixin` in `coordinator/capabilities.py` (230)
8. `ConfigFlow` in `config_flow.py` (218)
9. `BaseModbusTransport` in `modbus_transport_base.py` (210)
10. `ThesslaGreenBinarySensor` in `binary_sensor.py` (175)

## 4) Largest functions/methods

1. `register_maintenance_services` in `services_handlers_maintenance.py` (136)
2. `read_input` in `scanner/io_read.py` (132)
3. `async_write_register` in `coordinator/schedule.py` (129)
4. `run_full_scan` in `scanner/orchestration.py` (125)
5. `validate_input_impl` in `config_flow_device_validation.py` (123)
6. `_post_process_data` in `coordinator/capabilities.py` (120)
7. `read_with_retry` in `coordinator/retry.py` (106)
8. `migrate_unique_id` in `const.py` (100)
9. `read_input_registers_optimized` in `_coordinator_read_batches.py` (100)
10. `_call_modbus` in `modbus_helpers.py` (97)

## 5) Completed refactors reflected in current dev state (merged PRs #1492-#1501)

- **#1492 coordinator connection orchestration helper**: coordinator connection orchestration was moved toward helper boundaries, reducing branching pressure in main coordinator execution flow.
- **#1493 multi-register chunk executor from coordinator schedule**: coordinator schedule gained clearer chunk-execution structure for multi-register writes.
- **#1494 scanner core state helper**: scanner core state handling was split into dedicated helper logic, tightening core scan-path responsibilities.
- **#1495 mapping builder branch complexity**: mapping builder branch paths were simplified, reducing complexity concentration in mapping composition.
- **#1496 temperature sensor mapping module**: temperature-specific mapping concerns were moved into dedicated mapping module boundaries.
- **#1497 exception-function classifier in `RawRtuOverTcpTransport`**: function-level exception classification in raw RTU-over-TCP transport was clarified and isolated.
- **#1498 maintenance service registration helper**: maintenance registration flow was further extracted into helper-level structure.
- **#1499 scanner I/O register read failure finalizer**: scanner read-failure finalization logic was isolated to standardize terminal failure handling in I/O reads.
- **#1500 register test coverage split**: register-focused test coverage was split into clearer scope units to keep tests maintainable as production modules are decomposed.
- **#1501 config-flow reauth helpers**: reauth flow behavior was extracted into helpers to reduce complexity in `config_flow.py` and align with layered flow constraints.

## 6) Current invariants and architectural constraints (verified)

- `coordinator/` is canonical.
- Top-level `custom_components/thessla_green_modbus/coordinator.py` is absent and must remain absent.
- No compatibility shims.
- No proxy modules.
- No re-export-only modules.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant.

## 7) Remaining production hotspots and recommended next PRs

1. Continue splitting `custom_components/thessla_green_modbus/coordinator/coordinator.py` (712 non-empty lines) by isolating lifecycle/state transitions from update-cycle orchestration.
2. Continue decomposition of `custom_components/thessla_green_modbus/scanner/io_read.py` (650 lines), prioritizing extraction of grouped-read planning and error normalization around `read_input`/`read_bit_registers`.
3. Continue decomposition of `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (560 lines), focusing on domain/type-specific builders to reduce branch-heavy composition.
4. Reduce `custom_components/thessla_green_modbus/scanner/core.py` (470 lines) by separating scanner state initialization from runtime scan execution.
5. Reduce `register_maintenance_services` (136 lines) by extracting schema binding, target resolution wiring, and registration loops into smaller helpers.

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

Implemented in CI as `ruff-adoption-signal`: a separate workflow job that runs the two checks above and is explicitly marked non-blocking via `continue-on-error: true`. This job:

- avoid touching required branch protection gates,
- avoid secrets and external services,
- only reports drift trend.

### Stage C (targeted adoption after convergence)

When `ruff format --check` and import-order checks are routinely clean on active files, enforce them incrementally by path or module group in small PRs, never as a one-shot repository-wide rewrite.

### Current readiness snapshot (2026-05-03)

- `ruff format --check custom_components tests tools`: **fails** currently (99 files would be reformatted).
- `ruff check --select I custom_components tests tools`: **passes** currently.

Conclusion: repository is ready for import-order enforcement (already clean), but not ready for mandatory format enforcement without a dedicated formatting campaign.
