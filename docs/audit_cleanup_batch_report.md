# Audit Cleanup Batch Report — 2026-05-17

## Summary

This report documents the cleanup batch applied on branch `refactor/audit-cleanup-batch`
based on the 2026-05-17 audit plan. The changes are incremental, reversible, and do not
alter any Modbus behaviour, entity IDs, unique IDs, service IDs, register names, register
addresses, config/options flow behaviour, or translation keys.

---

## Phase 1 — coordinator/scan.py hidden re-export removed

**Problem:** `coordinator/scan.py` imported `normalise_cached_register_name` from
`core.scan_helpers` but did not use it locally; it was annotated `# noqa: F401 –
re-exported for coordinator internal use`. `normalise_available_registers` was imported
from the same block but IS used internally in `apply_scan_cache`. The `noqa` block
masked the redundant re-export.

**Changes:**
- `coordinator/scan.py`: Removed `normalise_cached_register_name` from the import;
  stripped the `# noqa: F401` comment; retained only `normalise_available_registers`
  (which is used locally).
- `coordinator/coordinator.py`: Updated the two `.scan` re-export consumers to import
  `normalise_available_registers` and `normalise_cached_register_name` directly from
  `..core.scan_helpers`. Import block re-sorted by ruff.

**Outcome:** No hidden re-exports remain in `coordinator/scan.py`.

---

## Phase 2A — entity_lookup._ENTITY_LOOKUP replaced by functools.cache

**Problem:** `entity_lookup.py` used a module-level `_ENTITY_LOOKUP: ... | None = None`
sentinel with a `global` statement inside `_build_entity_lookup()`.

**Changes:**
- `entity_lookup.py`: Removed `_ENTITY_LOOKUP` global. Decorated `_build_entity_lookup`
  with `@functools.cache`. Updated `__all__` to remove `_ENTITY_LOOKUP`.
- `tests/test_migrate_unique_id.py`:
  - Removed `import … entity_lookup as lookup_mod` (no longer needed).
  - Extended the local `migrate_unique_id` wrapper with an optional `get_entity_lookup`
    parameter (defaults to the imported `_build_entity_lookup`).
  - Updated `test_migrate_unique_id_register_to_key_lookup` to pass
    `get_entity_lookup=lambda: fake_lookup` directly, eliminating all monkeypatch
    setattr calls on `_ENTITY_LOOKUP`.

**Outcome:** `_ENTITY_LOOKUP` global eliminated. Cache reset available via
`_build_entity_lookup.cache_clear()`.

---

## Phase 2B — mappings/_helpers._REGISTER_INFO_CACHE replaced by functools.cache

**Problem:** `mappings/_helpers.py` maintained `_REGISTER_INFO_CACHE: ... | None = None`
with a `global` statement. The cache was populated inside `_get_register_info` using a
complex parent-module lookup (`sys.modules.get(__package__)`) to support test
monkeypatching via `em._REGISTER_INFO_CACHE`.

**Changes:**
- `mappings/_helpers.py`:
  - Added `import functools`.
  - Removed `_REGISTER_INFO_CACHE` global.
  - Added `@functools.cache`-decorated `_load_register_info()` that builds and returns
    the full register-info dict; retains parent-module lookup for `get_all_registers` so
    test patching of `em.get_all_registers` still works after `cache_clear()`.
  - Simplified `_get_register_info(name)` to call `_load_register_info()` directly
    (plain call, no global state).
  - Updated `__all__`: removed `_REGISTER_INFO_CACHE`, added `_load_register_info`.
- `mappings/__init__.py`:
  - Replaced `_REGISTER_INFO_CACHE` import with `_load_register_info`.
  - Updated `__all__` accordingly.
- `tests/test_entity_mappings_base.py`:
  - `monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)` → `em._helpers._load_register_info.cache_clear()`
  - `monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", {})` → `monkeypatch.setattr(em._helpers, "_load_register_info", lambda: {})`
- `tests/test_entity_mappings_discrete.py`:
  - `monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)` → `em._helpers._load_register_info.cache_clear()`
  - `monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", {...})` → `monkeypatch.setattr(em._helpers, "_load_register_info", lambda: {...})`
  - `monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", {})` → `monkeypatch.setattr(em._helpers, "_load_register_info", lambda: {})`

**Outcome:** `_REGISTER_INFO_CACHE` global eliminated. Cache reset available via
`_helpers._load_register_info.cache_clear()` (also exposed through `em._helpers`).

---

## Phase 3 — Coordinator proxy migration / client accessor

**Status: Confirmed and deferred.**

`coordinator.device_client` property already exists and returns
`self._device_client` (a `ThesslaGreenDeviceClient`). This is the public accessor for
the underlying device client.

`coordinator.client` is already taken as a proxy for the low-level Modbus transport
connection (`self._device_client.client`). Renaming `coordinator.client` to mean
`ThesslaGreenDeviceClient` would break ~15 test files that assign `coordinator.client =
MagicMock(...)` for transport mocking.

No proxy migrations were performed in this PR. The existing proxy boilerplate carries a
clear retention rationale and a documented future removal path (see coordinator.py
comment block). Full proxy elimination is deferred — see Remaining Technical Debt.

---

## Phase 4 — Coordinator test fixture consolidation

Four test files contained a private `_make_coordinator()` function identical to
`tests/helpers_coordinator.make_coordinator`. These duplicates were removed and replaced
with an import from the shared helper:

| File | Change |
|---|---|
| `tests/test_coordinator_lifecycle.py` | Removed private `_make_coordinator`; import from `helpers_coordinator` |
| `tests/test_coordinator_capabilities.py` | Same |
| `tests/test_coordinator_update_statistics.py` | Same |
| `tests/test_coordinator_setup.py` | Same |

Unused imports (`MagicMock`, `ThesslaGreenModbusCoordinator` from direct path) were also
removed from the affected files as a side effect of the factory removal.

---

## Phase 5 — Large-function decomposition (deferred)

**Targets considered:**
- `unique_id_migration.py:migrate_unique_id` — 106-line function with two nested
  helpers. Decomposition was assessed as low-risk but deferred: pytest cannot run in
  this environment (Python 3.11, requires ≥3.12), and the function is already
  well-structured with inline helpers `_bit_index` and `_register_address`.
- `core/read_batches.py:read_input_registers_optimized` — 100-line function with an
  inline per-register fallback block. The extraction of
  `_fallback_individual_input_reads` was similarly deferred due to inability to run
  tests.

**Reason for deferral:** Cannot execute pytest in this environment (Python 3.11 vs
required ≥3.12). Both decompositions are mechanical and carry negligible semantic risk,
but they touch hot paths (register reads, unique-ID migration) where silent behavioural
regressions are unacceptable without test confirmation. Recommend performing these in a
follow-up PR after real-device validation.

---

## Validation results

| Check | Result |
|---|---|
| `python -m compileall` | ✅ clean |
| `ruff check` | ✅ all checks passed |
| `ruff check --select I` | ✅ all checks passed |
| `ruff format --check` | ✅ 433 files already formatted |
| `tools/check_maintainability.py` | ✅ maintainability gate passed |
| `tools/validate_entity_mappings.py` | ✅ 366 entities validated |
| `tools/check_translations.py` | ✅ all translation keys present |
| `pytest` | ⚠️ cannot run — Python 3.11 environment, requires ≥3.12 |

**pytest limitation:** The integration requires `pytest-homeassistant-custom-component
>=0.13.309,<0.13.317` which requires Python ≥3.12. The container runs Python 3.11.15.
All static checks pass. Physical device and pytest validation recommended before merge.

---

## Safety checks

- No hidden re-exports (`# noqa: F401`) remain in coordinator scan path.
- `_ENTITY_LOOKUP` global removed from `entity_lookup.py`.
- `_REGISTER_INFO_CACHE` global removed from `mappings/_helpers.py`.
- `coordinator.device_client` property confirmed present.
- No merge conflict markers found.
- `git diff --check` clean.
- No shims reintroduced.

Pre-existing `global REGISTER_HASH` in `scanner/register_maps.py` is out of scope for
this PR and remains unchanged.

---

## Coordinator proxies removed

None in this PR. Proxy elimination requires per-proxy caller analysis and test
confirmation. Deferred to full proxy elimination phase.

## Coordinator proxies retained and why

All existing coordinator proxies (`coordinator.timeout`, `coordinator.retry`,
`coordinator.effective_batch`, `coordinator.available_registers`, etc.) are retained
because:
- Coordinator submodules receive `self` (the coordinator) via duck-typing and access
  these attributes directly.
- Test files assign values to these attributes on the coordinator object.
- Entity platform files read `coordinator.available_registers`, `coordinator.capabilities`,
  `coordinator.statistics`, etc.

Removal path: when a submodule is refactored to accept `ThesslaGreenDeviceClient`
directly instead of the coordinator, the corresponding proxy can be removed.

---

## Remaining technical debt

| Item | Notes |
|---|---|
| Full coordinator proxy elimination | Requires per-proxy caller migration across submodules and tests; high impact |
| Options globals / DI | `mutable_global_state_inventory.md` documents remaining globals |
| Real-device validation | **Recommended before release** — no physical device access available |
| Remaining test fixture consolidation | Several coordinator test files still use inline `from_params` calls |
| `migrate_unique_id` decomposition | Deferred — needs pytest green |
| `read_input_registers_optimized` decomposition | Deferred — needs pytest green |
| `scanner/register_maps.py:REGISTER_HASH` | Pre-existing mutable global; out of scope here |
