# Code Cleanup Audit

- Date: 2026-05-09
- Branch analyzed: `chore/dead-code-legacy-cleanup`
- Commit analyzed: `6f347d55`

## Categories checked
1. Branch/CI residue (dev vs main instructions and references)
2. Manifest/HACS/Hassfest related metadata files
3. Dead/legacy Python modules and placeholders
4. Translation/service metadata consistency surfaces
5. Tooling scripts and maintainability guards

## Confirmed removals / cleanups applied
- Replaced misleading `TODO: module scaffold for branch test refactor.` docstrings in placeholder modules with neutral, accurate reserved-module docstrings.
- Updated stale `docs/release_readiness.md` wording that incorrectly stated main branch is not used.

## Changed files
- `custom_components/thessla_green_modbus/core/__init__.py`
- `custom_components/thessla_green_modbus/core/client.py`
- `custom_components/thessla_green_modbus/core/config.py`
- `custom_components/thessla_green_modbus/core/errors.py`
- `custom_components/thessla_green_modbus/core/snapshot.py`
- `custom_components/thessla_green_modbus/transport/factory.py`
- `custom_components/thessla_green_modbus/registers/reference.py`
- `docs/release_readiness.md`
- `docs/code_cleanup_audit.md`

## Items intentionally kept
- Legacy/compatibility runtime paths that are still part of public service compatibility (`sync_time`, service aliases) were preserved.
- Migration and unique-id compatibility paths were preserved due to Home Assistant registry/data migration behavior.
- Validation tooling under `tools/` was preserved, including required scripts.

## Uncertain candidates requiring manual review
- Whether placeholder package modules under `core/`, `transport/factory.py`, and `registers/reference.py` should be fully removed in a future major cleanup. They currently remain as explicit placeholders to avoid import-path breakage risk.
- Historical `dev` mentions in changelog/history-style docs may be kept where contextual/historical rather than instructive.

## Validation commands run
- Initial repo and branch checks (`git branch --show-current`, `git status --short`, `git log --oneline -n 10`)
- Inventory and static searches (`find`, `rg` for legacy/dev/smell patterns)
- Dependency/bootstrap install commands
- Lint/format/compile/tests and project tools (listed in command history)

## Dev reference cleanup summary
- Removed one active-instruction stale reference in `docs/release_readiness.md`.
- Remaining references appear historical or policy documentation and were not changed in this cleanup.

---

# Coordinator Helper Consolidation

- Date: 2026-05-10
- Branch: `refactor/move-coordinator-helpers`

## Files moved into `coordinator/` package

| Old root path | New path in `coordinator/` |
|---|---|
| `_coordinator_connection_test.py` | `coordinator/connection_test.py` |
| `_coordinator_device_info.py` | `coordinator/device_info.py` |
| `_coordinator_factory.py` | `coordinator/factory.py` |
| `_coordinator_init.py` | `coordinator/init_config.py` |
| `_coordinator_read_batches.py` | `coordinator/read_batches.py` |
| `_coordinator_read_bits.py` | `coordinator/read_bits.py` |
| `_coordinator_read_common.py` | `coordinator/read_common.py` |
| `_coordinator_register_groups.py` | `coordinator/register_groups.py` |
| `_coordinator_register_processing.py` | `coordinator/register_processing.py` |
| `_coordinator_runtime_io.py` | `coordinator/runtime_io.py` |
| `_coordinator_scan_result.py` | `coordinator/scan_result.py` |
| `_coordinator_scanner_kwargs.py` | `coordinator/scanner_kwargs.py` |
| `_coordinator_transport_select.py` | `coordinator/transport_select.py` |
| `coordinator_config.py` | `coordinator/config_normalization.py` |
| `coordinator_diagnostics.py` | `coordinator/diagnostics.py` |
| `coordinator_runtime.py` | `coordinator/runtime.py` |
| `coordinator_state.py` | `coordinator/state.py` |

## Import cleanup summary

- `coordinator/coordinator.py`: All 17 `from .._coordinator_*` and `from ..coordinator_*` imports updated to intra-package relative imports.
- `coordinator/io.py`: All 8 `from .._coordinator_*` imports updated to intra-package relative imports.
- `coordinator/models.py`: Lazy `from ..coordinator_config` import updated to `from .config_normalization`.
- Moved files' own internal imports updated: single-dot references to root-level siblings (`.const`, `.modbus_exceptions`, etc.) changed to double-dot (`..const`, etc.); `.coordinator.retry` references changed to `.retry`.
- Tests updated: `test_coordinator_availability.py`, `test_coordinator_device_info.py`, `test_coordinator_scan_cache_extra.py`, `test_coordinator_schedule.py`, `test_optimized_integration_updates.py`.

## Compatibility files remaining at root level

None. All coordinator helper modules have been moved. No compatibility shims were required because all callers were updated in the same PR.

## Behavior unchanged

All moved modules are pure helpers with no side effects. Function signatures, register names, entity IDs, service IDs, and Modbus behavior are unchanged.

## Validation results

- `ruff check`: all checks passed
- `ruff format --check`: 436 files already formatted
- `python -m compileall -q`: no syntax errors
- `tools/compare_registers_with_reference.py`: passed (same baseline as main)
- `tools/check_maintainability.py`: maintainability gate passed
- `tools/validate_entity_mappings.py`: 366 entities validated
- `tools/check_translations.py`: all translation keys present
- `pytest -k "coordinator or connection or scan or diagnostics"`: same pass/fail profile as main (all new failures pre-existing)

---

# Config Flow and Services Package Consolidation

- Date: 2026-05-10
- Branch: `claude/refactor-config-services-packages-RtYUp`

## Config flow helpers moved into `config_flow/` package

| Old root path | New path in `config_flow/` |
|---|---|
| `config_flow.py` | `config_flow/__init__.py` |
| `config_flow_confirm.py` | `config_flow/confirm.py` |
| `config_flow_device_validation.py` | `config_flow/device_validation.py` |
| `config_flow_entry.py` | `config_flow/entry.py` |
| `config_flow_errors.py` | `config_flow/errors.py` |
| `config_flow_network.py` | `config_flow/network.py` |
| `config_flow_options.py` | `config_flow/options.py` |
| `config_flow_options_form.py` | `config_flow/options_form.py` |
| `config_flow_payloads.py` | `config_flow/payloads.py` |
| `config_flow_reauth.py` | `config_flow/reauth.py` |
| `config_flow_reauth_confirm.py` | `config_flow/reauth_confirm.py` |
| `config_flow_runtime.py` | `config_flow/runtime.py` |
| `config_flow_schema.py` | `config_flow/schema.py` |
| `config_flow_steps.py` | `config_flow/steps.py` |
| `config_flow_user_submit.py` | `config_flow/user_submit.py` |
| `config_flow_validation.py` | `config_flow/validation.py` |

## Services helpers moved into `services/` package

| Old root path | New path in `services/` |
|---|---|
| `services.py` | `services/__init__.py` |
| `services_dispatch.py` | `services/dispatch.py` |
| `services_handler_deps.py` | `services/handler_deps.py` |
| `services_handlers_data.py` | `services/handlers_data.py` |
| `services_handlers_logging.py` | `services/handlers_logging.py` |
| `services_handlers_maintenance.py` | `services/handlers_maintenance.py` |
| `services_handlers_mode.py` | `services/handlers_mode.py` |
| `services_handlers_parameters.py` | `services/handlers_parameters.py` |
| `services_handlers_schedule.py` | `services/handlers_schedule.py` |
| `services_helpers.py` | `services/helpers.py` |
| `services_schema.py` | `services/schema.py` |
| `services_targets.py` | `services/targets.py` |
| `services_validation.py` | `services/validation.py` |

## Import cleanup summary

- `config_flow/__init__.py`: all 15 `from .config_flow_X import` updated to `from .X import`; parent package imports (`.const`, `.errors`, `.modbus_exceptions`, `.options`) updated to `..`-prefixed forms.
- All 15 helper files in `config_flow/`: sibling `config_flow_X` references updated to `.X`; parent package references updated to `..X`.
- `services/__init__.py`: all 12 `from .services_X import` updated to `from .X import`; `from . import services_schema` updated to `from . import schema`; parent package imports updated to `..`-prefixed forms.
- All 12 helper files in `services/`: sibling `services_X` references updated to `.X`; parent package references updated to `..X`.
- Import order auto-fixed by `ruff --select I --fix` in 7 files after sibling/parent reordering.

## Tests updated

- `tests/test_api_contracts.py`: `services_schema` → `services.schema`, `services_targets` → `services.targets`
- `tests/test_config_flow_helpers.py`: `config_flow_device_validation` → `config_flow.device_validation`, `config_flow_schema` → `config_flow.schema`, `config_flow_steps` → `config_flow.steps`
- `tests/test_config_flow_options.py`: `config_flow_options_form` → `config_flow.options_form`
- `tests/test_config_flow_runtime_validation.py`: `config_flow_device_validation` → `config_flow.device_validation`
- `tests/test_services_dispatch_validation.py`: `services_dispatch` → `services.dispatch`, `services_validation` → `services.validation`
- `tests/test_services_handlers_maintenance.py`: `services_handlers_maintenance` → `services.handlers_maintenance`, `services_schema` → `services.schema`
- `tests/test_services_handlers_parameters_registration.py`: `services_handler_deps` → `services.handler_deps`, `services_handlers_parameters` → `services.handlers_parameters`, `services_schema` → `services.schema`

## Compatibility files remaining at root level

None. All config flow and services helper modules have been moved. No compatibility shims were required because all callers (component code and tests) were updated in the same PR.

## HA entrypoint behavior unchanged

Home Assistant discovers the config flow by importing `custom_components.thessla_green_modbus.config_flow`. Moving `config_flow.py` to `config_flow/__init__.py` preserves this: Python resolves the package at the same dotted path, and the `ConfigFlow` class remains at `config_flow.ConfigFlow`. Similarly `services/__init__.py` is still imported as `services` with all the same public symbols.

## Service IDs unchanged

All service names (`set_special_mode`, `set_mode`, `set_airflow_schedule`, etc.) are unchanged. The `services.yaml` file was not modified.

## Validation results

- `ruff check`: all checks passed
- `ruff format --check`: 436 files already formatted
- `python -m compileall -q`: no syntax errors
- `tools/check_maintainability.py`: maintainability gate passed
- `tools/check_translations.py`: all translation keys present
- All moved-file imports verified (sibling-aware import checker): all correct
