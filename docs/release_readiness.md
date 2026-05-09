# Release Readiness Audit

Date: 2026-05-09 (refreshed after CI results and quality fixes)
Branch: `dev` (working branch: `claude/finalize-release-readiness-ozgQt` — second pass)

> **Related:** [HA Quality Scale Audit](ha_quality_scale_audit.md) — full rule-by-rule Bronze/Silver/Gold evaluation added 2026-05-09.

---

## 1. Version

| Source | Value |
|--------|-------|
| `custom_components/thessla_green_modbus/manifest.json` → `version` | `2.8.0` |
| `pyproject.toml` → `version` | `2.8.0` |
| Versions consistent | ✅ |

---

## 2. Python Interpreter

Python 3.13.12 (via `python3.13`; venv at `/tmp/venv_thessla`).

---

## 3. Full Gate Results

All gates run locally with Python 3.13.12 / venv.

### Import gate

```
OK pydantic: 2.12.2
OK pytest: 9.0.0
OK pytest_asyncio: 1.3.0
OK pytest_homeassistant_custom_component: installed
OK homeassistant: installed
```

### Validation gates

| Gate | Command | Result |
|------|---------|--------|
| ruff check | `ruff check custom_components tests tools` | ✅ PASS — All checks passed |
| ruff import-order | `ruff check --select I custom_components tests tools` | ✅ PASS — All checks passed |
| ruff format | `ruff format --check custom_components tests tools` | ✅ PASS — 419 files already formatted (0 drift) |
| compileall | `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools` | ✅ PASS |
| compare_registers | `python3.13 tools/compare_registers_with_reference.py` | ✅ PASS (exit 0; 62 extras in integration are expected extension beyond vendor reference) |
| check_maintainability | `python3.13 tools/check_maintainability.py` | ✅ PASS — Maintainability gate passed |
| validate_entity_mappings | `python tools/validate_entity_mappings.py` (venv) | ✅ PASS — OK: 366 entities validated |
| pytest | `python -m pytest tests/ -q` (venv) | ✅ PASS — **1948 passed, 4 skipped** |

### Final invariants

| Invariant | Result |
|-----------|--------|
| `coordinator.__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]` | ✅ PASS |
| `coordinator.py` (flat file) absent | ✅ PASS |
| No HA imports in `scanner/` | ✅ PASS |
| No dependency file changes (`pyproject.toml`, `requirements*.txt`, `constraints.txt`) | ✅ confirmed — `git diff` clean |

---

## 4. Metadata Consistency

| Check | Result |
|-------|--------|
| manifest domain | `thessla_green_modbus` ✅ |
| manifest name | `ThesslaGreen Modbus` ✅ |
| manifest version == pyproject version | `2.8.0` == `2.8.0` ✅ |
| manifest homeassistant minimum | `2026.1.0` ✅ |
| manifest integration_type | `hub` ✅ |
| manifest requirements | `["pymodbus>=3.6.0"]` ✅ |
| hacs.json present | ✅ |
| hacs.json name | `ThesslaGreen Modbus` ✅ |
| hacs.json content_in_root | `false` ✅ (integration in `custom_components/`) |
| hacs.json render_readme | `true` ✅ |
| pyproject requires-python | `>=3.13` ✅ |
| **Overall** | **metadata consistency OK** |

---

## 5. Hassfest Validation

**CI gate FAILED on first run — root cause identified and fixed.**

- First run (PR #1602): **FAILED** in ~2 seconds.
  - Root cause: `files` key in `manifest.json` is not a valid HA manifest field
    (not in `homeassistant.loader.Manifest` TypedDict). Hassfest rejects unknown keys.
  - Fix applied: `files` key removed from `manifest.json` in this PR.
  - `test_manifest_files.py` updated: `test_manifest_files_list_is_complete` →
    replaced with `test_manifest_does_not_have_files_key` + `test_required_static_files_exist_on_disk`.
- CI job: `home-assistant/actions/hassfest@main` — runs on every PR and push to `main`/`master`/`dev`.
- Awaiting re-run CI result to confirm fix resolves the failure.

---

## 6. HACS Validation

**CI gate FAILED on first run — root cause identified and fixed.**

- First run (PR #1602): **FAILED** in ~43 seconds.
  - Root cause: `files` key in `manifest.json` likely rejected during HACS manifest validation.
  - Fix applied: `files` key removed from `manifest.json` in this PR. HACS installs
    the entire `custom_components/thessla_green_modbus/` directory automatically.
- CI job: `hacs/action@main` (`category: integration`) — runs on every PR and push.
- `hacs.json` is structurally valid with all required fields (`name`, `content_in_root`,
  `render_readme`). `content_in_root: false` is correct because the integration lives
  under `custom_components/thessla_green_modbus/`.
- Awaiting re-run CI result to confirm fix resolves the failure.

---

## 7. Real-Device Validation

**Not proven — checklist template created.**

No evidence of on-device testing against a physical ThesslaGreen AirPack device
exists. A structured checklist and evidence template has been created:

→ **[docs/real_device_validation.md](real_device_validation.md)**

The checklist covers:
- Installation via HACS
- UI config flow
- TCP connection verification
- Entity creation (~366 entities)
- Sensor state updates
- Fan/climate control writes
- Single and multi-register write paths
- Reconnect after controller/network disruption
- Unload/reload
- HA restart recovery
- Full log review

Real-device validation remains **open blocker B4** until the Evidence Record
in that document is completed by a human tester with physical hardware.

---

## 8. Release Notes / Tag Status

- **CHANGELOG.md**: 2.8.0 entry exists and has been updated with a
  "CI / Release Readiness" section covering: hassfest gate, HACS gate, `dev`
  push trigger, `docs/real_device_validation.md`, validation suite results,
  pydantic pin confirmation, and release caveats.
- **GitHub release tag**: `v2.8.0` tag and GitHub release **not yet created**.
  This must be done separately via GitHub UI or CLI after HACS/hassfest CI jobs
  pass and real-device validation is complete.
- HACS will not distribute version 2.8.0 until a GitHub release with a matching
  tag exists.

---

## 9. Remaining Blockers

| # | Blocker | Status |
|---|---------|--------|
| **B1** | Hassfest validation in CI | ⚠️ **FIX APPLIED, PENDING RE-RUN** — First CI run FAILED (PR #1602): `files` key in `manifest.json` rejected by hassfest. Fix: `files` removed from `manifest.json`. Awaiting CI re-run to confirm. |
| **B2** | HACS validation in CI | ⚠️ **FIX APPLIED, PENDING RE-RUN** — First CI run FAILED (PR #1602). Root cause: same `files` key issue. Fix applied. Awaiting CI re-run. |
| **B3** | No GitHub release tag for `2.8.0` | ⛔ **OPEN** — Tag `v2.8.0` and GitHub release not yet created. Must be done separately after CI is green and real-device validation is complete. Do not create in this PR. |
| **B4** | Real-device validation undocumented/unproven | ⚠️ **PARTIALLY ADDRESSED** — Checklist template at `docs/real_device_validation.md`. Evidence from a real device still required to close this blocker. |

---

## 10. Non-Blocking Follow-Ups

| # | Item |
|---|------|
| N1 | **Dependabot PR #1567** (pydantic update) remains separate and untouched. |
| N2 | CHANGELOG heading style is consistent across 2.8.0 and prior entries. |
| N3 | `dev` push trigger now added to CI (`push: branches: ["main", "master", "dev"]`). |
| N4 | GitHub release tag and release notes for `v2.8.0` must be created via GitHub UI/CLI after remaining blockers are resolved. |

---

## 11. Confirmations

- **pydantic**: unchanged. Still pinned at `2.12.2`. No version bump, no dependency changes.
- **PR #1567**: untouched. Not referenced, not cherry-picked, not merged.
- **main branch**: not used. All work is on `claude/finalize-release-readiness-ozgQt`
  targeting `dev`. `main` was not read as source of truth, not merged, not compared.
- **Runtime code**: unchanged. Only CI workflow, documentation, and CHANGELOG were
  modified in this PR.
- **CI**: not weakened. New jobs (`hassfest`, `hacs`) added; existing jobs unchanged.
  Push trigger extended to include `dev`. No existing job removed or made
  `continue-on-error`.
- **Tests**: not removed, not skipped, not xfailed.

---

## 12. Files Changed in This PR

| File | Change |
|------|--------|
| `.github/workflows/ci.yaml` | Added `hassfest` and `hacs` CI jobs; added `dev` to push trigger branches |
| `CHANGELOG.md` | Added "CI / Release Readiness" and "Release caveats" sections to 2.8.0 entry |
| `docs/real_device_validation.md` | **New file** — real-device validation checklist and evidence template |
| `docs/release_readiness.md` | Updated with current date, branch, CI job status, real-device checklist link, and revised blocker table |

No production runtime code, tests, manifest.json, hacs.json, or dependency files
were modified.

---

## 13. PR Target Branch

**PR base: `dev`**

Do not merge to `main`.
