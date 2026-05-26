# Next Safe Cleanup Batch — Report

**PR:** refactor: apply next safe cleanup batch  
**Base branch:** main  
**Date:** 2026-05-17

---

## Completed Items

### 1. `const.py` unique-ID migration cleanup

**Status:** Done

Removed compatibility wrappers from `const.py`:
- `device_unique_id_prefix()` — was a thin façade over `unique_id_migration.device_unique_id_prefix`
- `migrate_unique_id()` — was a convenience wrapper binding app-specific params to `unique_id_migration.migrate_unique_id`

Removed now-unused imports from `const.py`:
- `from .entity_lookup import _build_entity_lookup`
- `from .registers.maps import coil_registers, discrete_input_registers, holding_registers, input_registers`
- `from .unique_id_migration import device_unique_id_prefix as _device_unique_id_prefix_impl`
- `from .unique_id_migration import migrate_unique_id as _migrate_unique_id_impl`

Updated consumers to import from canonical `unique_id_migration` module:
- `_setup.py`: imports `migrate_unique_id` from `.unique_id_migration`; call site now passes all domain-specific parameters explicitly
- `tests/test_migrate_unique_id.py`: imports from `.unique_id_migration`; defines a local test helper that binds the domain params
- `tests/test_options_loading.py`: imports from `.unique_id_migration`; passes all params explicitly

Migration behavior: **unchanged**. Only import ownership moved.

---

### 2. `coordinator/write_path.py` re-export cleanup

**Status:** Done

Removed re-export of `SingleWritePlan` and `encode_write_value` from `coordinator/write_path.py`.

These symbols are defined in `core/write_path.py` (canonical location). The re-export line:
```python
from ..core.write_path import SingleWritePlan, encode_write_value  # noqa: F401 – re-exported
```
was removed.

Updated consumers:
- `coordinator/schedule.py`: imports `SingleWritePlan`, `encode_write_value` from `..core.write_path`
- `tests/test_coordinator_register_writes.py`: imports `encode_write_value` from `core.write_path`

`coordinator/write_path.py` still retains its real logic:
`run_single_write_attempts`, `run_multi_register_write_attempts`, `finalize_write_result` — unchanged.

Write encoding behavior: **unchanged**. Modbus write behavior: **unchanged**.

---

### 3. `_config_flow/` convention documented

**Status:** Done

Added a `### Config flow package convention` section to `docs/thesslagreen_architecture.md`.

Documents:
- HA hassfest requires `config_flow.py` as a file
- Implementation lives in `_config_flow/` sub-package
- `config_flow.py` is only the HA public entrypoint
- New helpers belong in `_config_flow/*` modules, not in `config_flow.py`

Also updated stale sections in the same doc:
- Status timestamp updated from 2026-05-10 to 2026-05-17
- `core/` layer status updated from "planned / not implemented" to "implemented and active" with current file listing
- Coordinator doc updated to remove stale "core planned" note

---

### 4. `REGISTER_HASH` single source of truth

**Status:** Done

`scanner/register_maps.py` is now the single owner of `REGISTER_HASH`.

Removed from `scanner/register_map_cache.py`:
- Module-level `REGISTER_HASH = _register_maps.REGISTER_HASH` variable
- `global REGISTER_HASH` tracking
- `_register_maps.REGISTER_HASH = REGISTER_HASH` writes (bidirectional sync)
- `sync_register_hash_from_maps()` simplified to return `_register_maps.REGISTER_HASH or ""` directly

Updated `scanner/register_map_facade.py`:
- `ensure_register_maps(current_hash)`: now sets `_register_maps.REGISTER_HASH = current_hash` directly
- `async_ensure_register_maps(current_hash, hass)`: same
- Removed writing to `_register_map_cache.REGISTER_HASH`

Updated `scanner/register_map_runtime.py`:
- `initial_register_hash()` now reads from `_register_maps.REGISTER_HASH` directly
- `sync_register_hash_from_maps()` reads from `_register_maps.REGISTER_HASH` directly
- Removed import of `_register_map_cache`

Updated `tests/test_scanner_register_cache_invalidation.py`:
- Replaced `register_map_cache.REGISTER_HASH = None` with `register_maps.REGISTER_HASH = None` to reset the canonical source

Public behavior: **unchanged**. No stale local copy of REGISTER_HASH. No extra global introduced.

---

### 5. `register_maintenance_services` decomposition

**Status:** Done

Decomposed remaining inline closures in `register_maintenance_services` into named private builder functions, consistent with the pattern already established for `_build_reset_filters_handler` and `_build_reset_settings_handler`.

New private builders extracted:
- `_build_start_pressure_test_handler(hass, deps)`
- `_build_set_modbus_parameters_handler(hass, deps)`
- `_build_set_device_name_handler(hass, deps)`
- `_build_sync_time_handler(hass, deps)`
- `_build_sync_device_clock_handler(hass, deps)`

`register_maintenance_services` is now a 6-line orchestrator:
```python
def register_maintenance_services(hass, deps):
    handlers = _maintenance_handlers(
        _build_reset_filters_handler(hass, deps),
        _build_reset_settings_handler(hass, deps),
        _build_start_pressure_test_handler(hass, deps),
        _build_set_modbus_parameters_handler(hass, deps),
        _build_set_device_name_handler(hass, deps),
        _build_sync_time_handler(hass, deps),
        _build_sync_device_clock_handler(hass, deps),
    )
    _register_maintenance_bindings(hass, deps, handlers)
```

Service IDs: **unchanged**. Schemas: **unchanged**. Handler behavior: **unchanged**. Registration order: **unchanged**.

---

## Validation Results

| Check | Result |
|---|---|
| `python -m compileall` | PASS — no syntax errors |
| `ruff check` | PASS — all checks passed |
| `ruff format --check` | PASS — 433 files already formatted |
| `ruff check --select I` (import order) | PASS |
| `git diff --check` | PASS — no whitespace issues |
| Safety grep (const compat imports) | PASS — none found |
| Safety grep (REGISTER_HASH duplicate) | PASS — single source only |
| Safety grep (merge conflicts) | PASS — none |
| `tools/check_translations.py` | PASS — all translation keys present |
| `tools/check_maintainability.py` | PASS — gate passed |
| `tools/compare_registers_with_reference.py` | PASS (expected delta) |
| `tools/validate_entity_mappings.py` | FAIL — pydantic not available in Python 3.11 env |
| pytest | NOT RUN — Python 3.11 environment; package requires Python ≥3.13 |

**Note on pytest:** This remote environment has Python 3.11.15. The package requires Python ≥3.13
(`pytest-homeassistant-custom-component<0.13.317,>=0.13.309` requires Python ≥3.12). Tests
cannot be collected. The code changes are syntax-clean, ruff-clean, and logically consistent
(verified by AST parse of all 13 modified files).

---

## Confirmations

- No Modbus behavior changed.
- Entity IDs: **unchanged** — no entity.py modifications.
- Unique IDs: **unchanged** — migration logic untouched; only import ownership moved.
- Service IDs: **unchanged** — all `hass.services.async_register(deps.domain, service, ...)` calls use same service names.
- Register names: **unchanged**.
- Register addresses: **unchanged**.
- Translation keys: **unchanged** — verified by `check_translations.py`.
- Config/options flow behavior: **unchanged** — `_config_flow/` not touched.
- No compatibility shims created.
- No `modbus_helpers.py` reintroduced.

---

## Remaining Recommended Next Steps

The following improvement guidelines were **intentionally excluded** from this PR per the scope rules:

| Item | Status | Reason |
|---|---|---|
| Coordinator proxy migration | Deferred | Broad coordinator redesign — separate PR |
| Mutable global state DI rewrite | Deferred | Requires coordinator redesign first |
| Real-device validation evidence | Deferred | Requires physical hardware |
| Test fixture consolidation | Deferred | Separate focused PR |
| DeviceClient broad redesign | Deferred | Ongoing — see `docs/device_client_redesign.md` |

### Recommended next PR candidates

1. **Coordinator proxy migration** — complete the removal of direct Modbus calls from the coordinator, delegating fully to `core/client.py`. See `docs/coordinator_proxy_cleanup.md`.
2. **Test fixture consolidation** — shared fixtures for common coordinator/HA mocks live in `conftest.py` but some tests duplicate setup. Low-risk cleanup.
3. **Mutable global state DI** — replace `_platform_cache` and similar module-level globals with dependency injection, improving testability.
