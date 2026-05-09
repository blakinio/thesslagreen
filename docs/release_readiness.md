# Release Readiness Audit

Date: 2026-05-09
Branch: `claude/finalize-release-readiness-OPBC9` → PR base: `dev`

---

## 1. Version

| Source | Value |
|--------|-------|
| `custom_components/thessla_green_modbus/manifest.json` → `version` | `2.8.0` |
| `pyproject.toml` → `version` | `2.8.0` |
| Versions consistent | ✅ |

---

## 2. Python Interpreter

Python 3.13.12 (via uv venv at `.venv`).

---

## 3. Full Gate Results

All gates run locally with Python 3.13.12.

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
| compileall | `python -m compileall -q custom_components/thessla_green_modbus tests tools` | ✅ PASS |
| compare_registers | `python tools/compare_registers_with_reference.py` | ✅ PASS (62 extras are expected extension beyond vendor reference) |
| check_maintainability | `python tools/check_maintainability.py` | ✅ PASS — Maintainability gate passed |
| validate_entity_mappings | `python tools/validate_entity_mappings.py` | ✅ PASS — OK: 366 entities validated |
| pytest | `python -m pytest tests/` | ✅ PASS — **1948 passed, 4 skipped** |

### Final invariants

| Invariant | Result |
|-----------|--------|
| `coordinator.__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]` | ✅ PASS |
| `coordinator.py` (flat file) absent | ✅ PASS |
| No HA imports in `scanner/` | ✅ PASS |
| Dependency files unchanged (`pyproject.toml`, `requirements*.txt`, `constraints.txt`) | ✅ confirmed |

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

## 5. Hassfest CI Validation

**Added to CI — pending first run.**

- Previous state: no hassfest job in CI (blocker B1).
- Current state: `home-assistant/actions/hassfest@master` job added to
  `.github/workflows/ci.yaml` in this PR. Runs on every pull request and push to
  `dev`, `main`, `master`.
- hassfest is not available as a local PyPI tool; validation result is only available
  from the CI run. Result will be visible after this PR is merged or on the CI run
  triggered by the PR itself.
- `manifest.json` was manually reviewed against all known hassfest-required fields:
  domain, name, version, codeowners, config_flow, homeassistant, iot_class,
  requirements, documentation, issue_tracker, integration_type, quality_scale,
  after_dependencies, loggers, dhcp, zeroconf, files — all present.

---

## 6. HACS CI Validation

**Added to CI — pending first run.**

- Previous state: no HACS validation job in CI (blocker B2). CI only installed `hacs`
  as a pip package for test infrastructure, which is not HACS repository validation.
- Current state: `hacs/action@main` job added to `.github/workflows/ci.yaml` with
  `category: integration`. Runs on every pull request and push to `dev`, `main`,
  `master`.
- HACS validation result will be visible after first CI run on this PR.
- `hacs.json` fields: `name`, `content_in_root: false`, `render_readme: true` — all
  known required fields present.

---

## 7. Real-Device Validation

**Not proven.**

No evidence of on-device testing against a physical ThesslaGreen AirPack device exists.
This remains release blocker B4.

A structured evidence template has been created at
[`docs/real_device_validation.md`](real_device_validation.md). It covers 13 test
cases from HACS install through steady-state log review, and includes an evidence
record form that must be filled before real-device validation can be claimed complete.

**Do not mark this blocker resolved until the evidence record in
`docs/real_device_validation.md` is filled with real test results.**

---

## 8. CHANGELOG / Release Notes

**Draft added to `CHANGELOG.md`.**

The 2.8.0 entry in `CHANGELOG.md` has been updated to include:
- HA ≥ 2026.1.0 and Python 3.13 requirements.
- Full gate status.
- CI additions (hassfest, HACS jobs).
- Release caveats (no tag, real-device pending, hassfest/HACS results pending CI run).

No git tag or GitHub release has been created. HACS distribution requires a GitHub
release with a matching tag (`v2.8.0` or `2.8.0`) created separately after final review.

---

## 9. Release Blockers

| # | Blocker | Status |
|---|---------|--------|
| **B1** | No hassfest validation in CI | ✅ **Addressed** — `home-assistant/actions/hassfest@master` job added. Pending first CI run to confirm pass. |
| **B2** | No HACS validation action in CI | ✅ **Addressed** — `hacs/action@main` job added. Pending first CI run to confirm pass. |
| **B3** | No GitHub release tag for `2.8.0` | ❌ **Remaining** — No `v2.8.0` or `2.8.0` git tag or GitHub release created. Must be created separately after final review. Do not create a tag from this PR. |
| **B4** | Real-device validation not proven | ❌ **Remaining** — See `docs/real_device_validation.md`. No hardware testing performed. |

---

## 10. Non-Blocking Follow-Ups

| # | Item |
|---|------|
| N1 | **Dependabot PR #1567** (pydantic update) remains separate and untouched. |
| N2 | CHANGELOG heading for 2.8.0 uses `## 2.8.0 —` format; older entries use `## [X.Y.Z] - date` anchored format. Cosmetic — may affect changelog tooling. |

---

## 11. Confirmations

- **pydantic**: unchanged. Still pinned at `2.12.2`. No version bump, no dependency changes.
- **PR #1567**: untouched. Not referenced, not cherry-picked, not merged.
- **main branch**: not used. All work targets `dev`. `main` was not read as source of
  truth, not merged, not compared.
- **Runtime code**: unchanged. No production runtime code modified.
- **CI**: not weakened. Only added new jobs (hassfest, hacs) and `dev` to push trigger.
  All existing gates retained without modification.
- **Tests**: not removed, not skipped, not xfailed.

---

## 12. Files Changed in This PR

| File | Change |
|------|--------|
| `.github/workflows/ci.yaml` | Added `hassfest` job, `hacs` job, `dev` to push trigger |
| `CHANGELOG.md` | Added requirements, CI additions, and release caveats to 2.8.0 entry |
| `docs/release_readiness.md` | This file — updated from prior audit |
| `docs/real_device_validation.md` | Created — 13-case evidence template |

No production runtime code, tests, dependency files, manifest.json, or hacs.json modified.

---

## 13. PR Target Branch

**PR base: `dev`**

Do not merge to `main`.
