# Repository File Inventory Audit — `blakinio/thesslagreen`

**Branch:** `main` (audited from `claude/thesslagreen-repo-audit-enlmhx`, level with `origin/main`).
**Date:** 2026-07-07
**Scope:** Full per-file audit of every tracked file. Classify each as needed /
legacy / duplicate / one-shot / safe-to-remove, with evidence.

> This is an **audit-only** pass. Per the task rules, **no runtime code, register
> addresses/names, entity/unique/service IDs, translation keys, or config/options
> flow behaviour were changed**, and **no files were deleted** — the evidence did
> not meet the deletion bar for any file (see §7).

---

## 1. Totals

| Metric | Count |
|---|---:|
| **Total tracked files** (`git ls-files`) | **564** |
| `tests/` | 270 |
| `custom_components/thessla_green_modbus/` | 193 (174 `.py` + 19 package data) |
| `docs/` | 51 (of which `docs/archive/` = 29, `docs/architecture/` = 3, `docs/releases/` = 1, `docs/audits/` = 1→2 after this file) |
| `tools/` | 17 (of which `tools/manual/` = 5) |
| `.github/` | 6 |
| root files | 27 |

**Orphan analysis:** a strict import-graph scan of all 174 runtime `.py` modules
found **0 orphans** — every runtime module is imported by at least one other
runtime module or test. A byte-level content-hash scan across all 564 files found
**0 duplicate files**.

---

## 2. Step-5 verification — files confirmed **NOT present** (good)

| Expected-absent path | Status |
|---|---|
| `modbus_helpers.py` | ✅ absent (deliberately removed; `CLAUDE.md` §1 forbids reintroduction) |
| `custom_components/thessla_green_modbus/transport/rtu_over_tcp.py` | ✅ absent (functionality lives in `transport/tcp_rtu.py`) |
| `custom_components/thessla_green_modbus/_legacy.py` | ✅ absent |
| `custom_components/thessla_green_modbus/mappings/legacy.py` | ✅ absent |
| `custom_components/thessla_green_modbus/scanner_io.py` | ✅ absent (scanner IO split across `scanner/io*.py`) |
| `tools/py_compile_all.py` | ✅ absent |
| duplicate `.github/workflows/release.yml` | ✅ absent — only `release.yaml` exists (the duplicate was removed in PR #1739) |

**Note — legacy-named tests are NOT stale.** Four tests carry historical names but
import current modules and are valid:

| Test file | Imports (all exist) | Verdict |
|---|---|---|
| `tests/test_modbus_helpers_call_flow.py` | `modbus.call`, `modbus.client_close`, `registers.read_planner` | keep (current) |
| `tests/test_modbus_helpers_frames_and_chunks.py` | `modbus.*` frame helpers | keep (current) |
| `tests/test_modbus_transport_rtu_over_tcp_helpers.py` | `transport.crc`, `transport.tcp_rtu.RawRtuOverTcpTransport` | keep (current) |
| `tests/test_raw_rtu_over_tcp_transport.py` | `transport.crc`, `transport.tcp_rtu.RawRtuOverTcpTransport` | keep (current) |

---

## 3. Category legend

`runtime` · `test` · `validator/tool` · `manual/one-shot` · `docs` ·
`CI/release` · `metadata` · `asset` · `suspected-stale` · `safe-delete`

---

## 4. Per-file / per-group inventory

### 4.1 Root files (27)

| Path | Category | Needed | Evidence | Recommendation | Risk |
|---|---|---|---|---|---|
| `claude.md` | metadata | yes | agent guideline file, auto-read; referenced by many docs | keep | none |
| `README.md` | docs | yes | HACS `render_readme:true`; anchors architecture docs | keep (public contract) | none |
| `README_en.md` | docs | yes | ref by `CHANGELOG.md`, `docs/ha_quality_scale_audit.md` | keep | none |
| `CHANGELOG.md` | docs | yes | `CLAUDE.md` §7 policy; release history | keep (public contract) | none |
| `CONTRIBUTING.md` | docs | yes | refs tools, `.bandit`, `DEPLOYMENT.md` | keep | none |
| `DEPLOYMENT.md` | docs | yes | ref by `CONTRIBUTING`, `QUICK_START`, `README_en` | keep | none |
| `QUICK_START.md` | docs | yes | ref by `README_en.md` | keep | none |
| `info.md` | asset/metadata | yes* | HACS "Information" pane convention file | keep | low — possibly redundant vs `render_readme:true` (maintainer decision) |
| `LICENSE` | metadata | yes | legal | keep | none |
| `hacs.json` | metadata | yes | HACS required manifest | keep (public contract) | none |
| `pyproject.toml` | metadata | yes | build/tooling config (ruff, mypy) | keep | none |
| `pytest.ini` | metadata | yes | pytest config | keep | none |
| `MANIFEST.in` | metadata | yes | sdist packaging manifest | keep | none |
| `constraints.txt` | metadata | yes | ref by `.github/workflows/ci.yaml` | keep | none |
| `requirements.txt` | metadata | yes | runtime deps | keep | none |
| `requirements-dev.txt` | metadata | yes | dev deps | keep | none |
| `requirements-test-min.txt` | metadata | yes | lightweight validator deps (`CLAUDE.md` §2) | keep | none |
| `.pre-commit-config.yaml` | CI/release | yes | pre-commit hooks | keep | none |
| `.bandit` | metadata | yes | ref by `CONTRIBUTING.md` (documented dev step) | keep | low — bandit not wired into CI/pre-commit (manual only) |
| `.yamllint.yaml` | metadata | yes | yaml lint config | keep | none |
| `.gitignore` / `.gitattributes` | metadata | yes | git config | keep | none |
| `.python-version` / `.tool-versions` | metadata | yes | pins Python 3.13 (`CLAUDE.md` §2) | keep | none |
| `example_configuration.yaml` | asset | yes | ref by `tests/test_example_configuration.py` | keep | none |
| `example_dashboard.yaml` | asset | yes | ref by `tests/test_dashboard_writable_entities.py`, `tests/test_validate_dashboard_entities_tool.py` | keep | none |
| `airpack4_modbus.json` | asset | yes | vendor reference; ref by tools + tests + docs | keep (public contract data) | none |

### 4.2 `.github/` (6)

| Path | Category | Needed | Evidence | Recommendation | Risk |
|---|---|---|---|---|---|
| `.github/workflows/ci.yaml` | CI/release | yes | main CI (lint/tests/hassfest/HACS) | keep | none |
| `.github/workflows/release.yaml` | CI/release | yes | release automation (single canonical workflow) | keep | none |
| `.github/workflows/auto-merge-codex.yml` | CI/release | **uncertain** | active; auto-enables squash-merge for PRs from `codex/*` branches | **maintainer decision** | med — auto-merges PRs; dead automation if Codex agent no longer used |
| `.github/dependabot.yml` | CI/release | yes | dependency update config | keep | none |
| `.github/pull_request_template.md` | metadata | yes | PR template; refs `check_maintainability` | keep | none |
| `.github/RELEASE_TEMPLATE.md` | metadata | yes | release notes template | keep | none |

### 4.3 `tools/` (17)

| Path | Category | Needed | Evidence | Recommendation | Risk |
|---|---|---|---|---|---|
| `tools/__init__.py` | validator/tool | yes | package root; tests do `from tools import …` | keep | none |
| `tools/README.md` | docs | yes | documents tools | keep | none |
| `tools/check_maintainability.py` | validator/tool | yes | CI + `CLAUDE.md` §5 + PR template | keep | none |
| `tools/check_translations.py` | validator/tool | yes | CI + `CLAUDE.md` §5 | keep | none |
| `tools/compare_airpack4_vendor_coverage.py` | validator/tool | yes | CI + `CLAUDE.md` §5 (regenerates coverage docs) | keep | none |
| `tools/compare_registers_with_reference.py` | validator/tool | yes | CI + `CLAUDE.md` §5 + `CHANGELOG` | keep | none |
| `tools/validate_entity_mappings.py` | validator/tool | yes | CI + `CLAUDE.md` §5 + `CONTRIBUTING` | keep | none |
| `tools/validate_dashboard_entities.py` | validator/tool | yes | ref by `tests/test_validate_dashboard_entities_tool.py` | keep | none |
| `tools/validate_registers.py` | validator/tool | yes | pre-commit hook + `README` + `tests/test_validate_registers.py` | keep — **but CLI/pre-commit path is broken**, see §8 | **med** — latent bug |
| `tools/generate_strings.py` | manual/one-shot | yes | `strings.json` generator; ref by `file_inventory.md` | keep-but-manual | low |
| `tools/sort_registers_json.py` | manual/one-shot | yes | ref by `tools/README.md`, `file_inventory.md` | keep-but-manual | low |
| `tools/cleanup_old_entities.py` | manual/one-shot | yes | ref by `tests/test_cleanup_old_entities.py`, `file_inventory.md` | keep-but-manual (tested) | low |
| `tools/manual/README.md` | docs | yes | documents the one-shot tools | keep | none |
| `tools/manual/migrate_register_names.py` | manual/one-shot | yes | documented one-shot; ref `CHANGELOG`, `file_inventory` | keep-but-manual | low |
| `tools/manual/translate_register_descriptions.py` | manual/one-shot | yes | documented one-shot; ref `CHANGELOG`, `pyproject` | keep-but-manual | low |
| `tools/manual/clear_airflow_stats.py` | manual/one-shot | yes | documented one-shot; ref `CHANGELOG`, `file_inventory` | keep-but-manual | low |
| `tools/manual/delete_stale_branches.sh` | manual/one-shot | yes | documented maintainer script; ref `CHANGELOG`, `file_inventory` | keep-but-manual | low |

### 4.4 `docs/` (51)

**Active / referenced from protected sources (README, CHANGELOG, CLAUDE.md,
docs/architecture, release docs) — keep, do NOT remove:**

| Path | Referenced by | Recommendation |
|---|---|---|
| `docs/architecture/file_inventory.md` | README, CHANGELOG | keep |
| `docs/architecture/runtime_flow.md` | README, CHANGELOG | keep |
| `docs/architecture/write_path.md` | README, CHANGELOG | keep |
| `docs/real_device_validation.md` | README, CHANGELOG, CLAUDE.md (17 refs; gates `quality_scale`) | keep (public contract) |
| `docs/thesslagreen_architecture.md` | README, CLAUDE.md | keep |
| `docs/thesslagreen_guidelines.md` | README, CLAUDE.md | keep |
| `docs/refactor_status.md` | README, CONTRIBUTING | keep |
| `docs/coordinator_proxy_remaining_plan.md` | CLAUDE.md | keep |
| `docs/core_consolidation_plan.md` | CLAUDE.md | keep |
| `docs/development_validation.md` | CLAUDE.md | keep |
| `docs/pymodbus_4_migration_plan.md` | CLAUDE.md | keep |
| `docs/releases/v2.8.x.md` | CHANGELOG (release doc) | keep |
| `docs/ha_quality_scale_audit.md` | README_en | keep |
| `docs/release_readiness.md` | README_en | keep |
| `docs/airpack4_vendor_reference_coverage.json` / `.md` | CHANGELOG + `compare_airpack4_vendor_coverage.py` (generated) | keep |
| `docs/airpack4_deferred_registers.md` | `tests/test_airpack4_vendor_reference_coverage.py` | keep |
| `docs/airpack4_dangerous_entities_inventory.md` | `docs/airpack4_register_exposure_policy.md` | keep |
| `docs/device_client_redesign.md` | `coordinator_proxy_remaining_plan.md` | keep |
| `docs/audits/targeted_readback_write_path_audit.md` | `docs/architecture/write_path.md` | keep |

**Standalone reference/policy docs (0 inbound refs but human-facing, intentional) — keep:**

| Path | Note |
|---|---|
| `docs/airpack4_register_exposure_policy.md` | exposure policy for dangerous entities; standalone reference |
| `docs/release_process.md` | release procedure; standalone reference |

**`docs/archive/` (29 files) — historical reports, intentionally archived
(commit `e16e9b4` "archive one-shot tools/docs"). Category `docs`, keep.**
Several are cross-referenced by other archive docs / plan docs (e.g.
`coordinator_proxy_cleanup.md`, `final_architecture_cleanup.md`,
`maintainability_audit.md`, `release_tooling_audit.md` ← CHANGELOG). None are
referenced by runtime/tests/CI. They do **not** meet the safe-delete bar (they
are docs). A maintainer may eventually prune the fully-superseded ones — listed
in §9 as a low-priority decision, not a recommendation to delete now.

### 4.5 Runtime — `custom_components/thessla_green_modbus/` (193)

All 174 `.py` modules are import-referenced (0 orphans). Grouped by the layered
architecture (`transport → core → coordinator → platforms`; `CLAUDE.md` §1):

| Group | Files | Category | Needed | Evidence | Risk |
|---|---:|---|---|---|---|
| package root (`__init__`, `_setup`, `const`, `entity`, `utils`, `protocols`, `errors`, `error_policy`, `error_contract`, `diagnostics`, `repairs`, `capability_rules`, `optimistic`, `clock_sync`, `schedule_helpers`, `entity_lookup`, `register_defs_cache`, `register_map`) | ~19 | runtime | yes | all imported; `const.py` holds batch boundaries `{16,8192}` (do not touch) | keep-because-runtime / public contract |
| platforms (`binary_sensor`, `button`, `climate`, `fan`, `number`, `select`, `sensor`, `switch`, `text`, `time`) | 10 | runtime | yes | HA entity platforms → entity IDs / unique IDs | keep (public contract) |
| `config_flow.py` + `_config_flow/` | 1 + 16 | runtime | yes | Hassfest-required entrypoint re-exporting `_config_flow` package | keep (public contract; not a removable shim — HA requires `<domain>/config_flow.py`) |
| migrations: `_migrations.py`, `_entry_migrations.py`, `unique_id_migration.py` | 3 | runtime | yes | `_migrations`←`__init__`; `_entry_migrations`←`_migrations`; `unique_id_migration`←`_setup`,`entity`,tests | keep (proven in-use; not obsolete) |
| `transport/` | 10 | runtime | yes | all imported; layer-isolated | keep |
| `core/` | 24 | runtime | yes | mixin assembler `client.py` + helpers (`CLAUDE.md` §1) | keep |
| `coordinator/` | 21 | runtime | yes | all imported | keep |
| `scanner/` | 27 | runtime | yes | all imported | keep |
| `registers/` | 15 (14 `.py` + `thessla_green_registers_full.json`) | runtime | yes | register map source of truth (addresses/names) | keep (public contract) |
| `mappings/` | 19 | runtime | yes | all imported | keep |
| `modbus/` | 5 | runtime | yes | all imported | keep |
| `services/` | 15 | runtime | yes | service handlers → service IDs | keep (public contract) |
| package data: `manifest.json`, `strings.json`, `services.yaml`, `translations/en.json`, `translations/pl.json`, `options/*.json` (11), `brand/icon.png`, `brand/logo.png` | 19 | asset/metadata | yes | HA/HACS required; translation keys; options selectors; service IDs | keep (public contract) |

### 4.6 `tests/` (270)

All 270 files are Python tests collected by pytest. Category `test`, **keep**.
Notable: the enforcement test `tests/test_dependency_direction.py` guards layer
isolation (`CLAUDE.md` §1 — never weaken). The four legacy-named tests are valid
(see §2). No stale/orphan tests were found — every test imports live modules.

---

## 5. Safe-delete candidates

**None.** No tracked file satisfies the deletion bar from task step 7 (proven
duplicate **AND** unreferenced **AND** not runtime/test/docs/CI **AND** zero
behaviour impact):

- 0 byte-identical duplicate files.
- 0 orphaned runtime modules.
- All docs are either referenced or intentional archive/reference docs.
- All step-5 legacy artifacts are already absent (prior PRs removed them).

## 6. Keep-but-manual files

`tools/generate_strings.py`, `tools/sort_registers_json.py`,
`tools/cleanup_old_entities.py`, and all of `tools/manual/`
(`migrate_register_names.py`, `translate_register_descriptions.py`,
`clear_airflow_stats.py`, `delete_stale_branches.sh`, `README.md`). One-shot /
generator utilities, not in the automated pipeline; documented and referenced.

## 7. Keep-because-runtime files

All 174 `.py` under `custom_components/thessla_green_modbus/` (0 orphans) plus the
package data files. See §4.5 for the layered grouping.

## 8. Keep-because-public-contract files

Files whose change would break existing installations or HACS/HA integration:

- `custom_components/.../manifest.json`, `hacs.json`, `info.md`, `brand/*`
- `custom_components/.../strings.json`, `translations/en.json`, `translations/pl.json` (translation keys)
- `custom_components/.../services.yaml` + `services/` (service IDs)
- `custom_components/.../registers/thessla_green_registers_full.json` + `airpack4_modbus.json` (register addresses/names)
- `custom_components/.../options/*.json` (options-flow selectors)
- platform modules (entity IDs / unique IDs), `config_flow.py` (Hassfest entrypoint), migration modules
- `const.py` (batch boundaries `{16, 8192}`), `README.md`, `CHANGELOG.md`

## 9. Uncertain — files requiring maintainer decision

| Item | Why uncertain | Suggested decision |
|---|---|---|
| `.github/workflows/auto-merge-codex.yml` | Active workflow that auto-squash-merges PRs from `codex/*` branches. If the OpenAI Codex agent flow is no longer used, this is dead (and behaviour-bearing) automation. | Confirm whether `codex/*` PRs are still produced; remove the workflow if not. |
| `tools/validate_registers.py` (CLI/pre-commit path) | Latent bug — see §10. Not a deletion; needs a 1-line stub fix. | Fix the stub (see §10) or drop the `validate-registers` pre-commit hook. |
| `info.md` | Possibly redundant given `hacs.json: "render_readme": true`. | Keep unless HACS "Information" pane is confirmed unused. |
| `docs/archive/*` fully-superseded reports (subset of the 29) | Historical value only; none referenced by runtime/tests/CI. | Optional future prune; **not** deleting in this audit (they are docs). |
| `.bandit` | Config for a linter not wired into CI/pre-commit (manual-only, documented in `CONTRIBUTING.md`). | Keep, or wire bandit into CI to make it load-bearing. |

---

## 10. Findings (bugs surfaced during the audit — reported, not fixed)

### 10.1 `tools/validate_registers.py` — CLI/pre-commit path is broken

**Symptom:** `python tools/validate_registers.py` fails with
`ImportError: cannot import name 'group_registers' from ...registers.read_planner (unknown location)`.

**Root cause:** `_prepare_environment()` installs a **stub** `read_planner` module
exposing only `group_reads`:

```python
read_planner_stub.group_reads = lambda *_, **__: None
sys.modules.setdefault("custom_components.thessla_green_modbus.registers.read_planner", read_planner_stub)
```

but `registers/loader.py` (imported by `main()`) now also imports
`group_registers`:

```python
from .read_planner import group_registers as _group_registers_impl
```

so the import against the stub fails. The stub was last touched in the same merge
(`5419d58`) where `loader.py` gained the `group_registers` import, but the stub
was not updated to match.

**Why it is not caught by CI/tests:**
- CI (`ci.yaml`) does **not** invoke `validate_registers.py` — it is only run by
  the `validate-registers` **pre-commit** hook (`entry: python tools/validate_registers.py`),
  which the CI workflow does not execute.
- `tests/test_validate_registers.py` calls `validate_registers.main(...)` **and
  passes**, because its module-level `from custom_components...registers.schema
  import RegisterType` imports the **real** `read_planner` into `sys.modules`
  first, so the later `setdefault` stub is a no-op. Standalone CLI invocation has
  no such prior import, so the stub wins and `main()` breaks.

**Suggested one-line fix (maintainer decision — not applied here):** add
`read_planner_stub.group_registers = lambda *_, **__: None` alongside the existing
`group_reads` stub. This is a tool-only change with no runtime/behaviour impact.

---

## 11. Validation results

Environment: **Python 3.11.15** (repo requires **3.13**). Per `CLAUDE.md` §2,
`pytest` cannot run here — **full pytest must be verified in CI on Python 3.13.**

| Command | Result |
|---|---|
| `python -m compileall -q custom_components/thessla_green_modbus tests tools` | ✅ pass |
| `pytest --collect-only -q` | ⚠️ not run — pytest unavailable on 3.11 (flag for CI/3.13) |
| `ruff check custom_components tests tools` | ✅ pass ("All checks passed!") |
| `ruff check --select I custom_components tests tools` | ✅ pass |
| `ruff format --check custom_components tests tools` | ✅ pass (456 files already formatted) |
| `python tools/check_maintainability.py` | ✅ pass ("Maintainability gate passed.") |
| `python tools/validate_entity_mappings.py` | ✅ pass ("OK: 367 entities validated") |
| `python tools/check_translations.py` | ✅ pass ("All translation keys present.") |
| `python tools/compare_registers_with_reference.py --show-renames` | ✅ exit 0 (reports vendor↔main name mapping) |
| `python tools/compare_airpack4_vendor_coverage.py` | ✅ exit 0 (regenerated coverage docs identically — no diff) |
| `python tools/validate_registers.py` | ❌ **fails** — see §10 (pre-existing tool bug, not introduced by this audit) |

**Rules self-audit:** No Modbus register addresses/names, entity IDs, unique IDs,
service IDs, translation keys, or config/options-flow behaviour were changed. No
runtime code was modified. `dev` branch and `modbus_helpers.py` were not
reintroduced. No files were deleted. Only this report was added.
