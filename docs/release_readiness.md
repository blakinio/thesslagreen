# Release Readiness Audit

Date: 2026-05-09
Branch: `claude/release-readiness-audit-5xXvn` → PR base: `dev`

---

## 1. Version

| Source | Value |
|--------|-------|
| `custom_components/thessla_green_modbus/manifest.json` → `version` | `2.8.0` |
| `pyproject.toml` → `version` | `2.8.0` |
| Versions consistent | ✅ |

---

## 2. Python Interpreter

Python 3.13.12 (via `python3.13`; venv at `/tmp/thessla_venv`).

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

## 5. HACS Validation

**Not proven locally — tooling unavailable.**

- `hacs` CLI: not found (`hacs --help` → command not found).
- `hacs` pip package: not installed in dev environment.
- CI workflow (`ci.yaml`): installs `hacs` as a pip package for test infrastructure only. **No `hacs/action@main` or equivalent HACS validation workflow step exists.**
- `hacs.json` is structurally valid and all known required fields (`name`, `content_in_root`, `render_readme`) are present.

---

## 6. Hassfest Validation

**Not proven locally — tooling unavailable.**

- `hassfest` CLI: not found (`hassfest --help` → command not found).
- `hassfest` pip package: not installed in dev environment.
- CI workflow (`ci.yaml`): **no `home-assistant/hassfest` GitHub Actions step exists.**
- `manifest.json` was manually reviewed against known hassfest schema requirements; all structurally required and recommended fields are present (domain, name, version, codeowners, config_flow, homeassistant, iot_class, requirements, documentation, issue_tracker, integration_type, quality_scale, after_dependencies, loggers, dhcp, zeroconf, files).

---

## 7. Real-Device Validation

**Not proven.**

No evidence of on-device testing against a physical ThesslaGreen AirPack device was found in `docs/`, `README.md`, `README_en.md`, `CHANGELOG.md`, or any test file.

### Manual real-device validation checklist

1. Install integration from HACS custom repository on Home Assistant ≥ 2026.1.0.
2. Add integration via UI config flow; provide controller IP and port.
3. Verify TCP connection to ThesslaGreen controller is established (no repeated exceptions in logs).
4. Verify entity creation count matches expected (~366 mapped entities for AirPack).
5. Verify fan, climate, and sensor entities update on state changes.
6. Verify single register write path (e.g., fan speed change).
7. Verify multi-register write path if applicable.
8. Verify automatic reconnect after controller restart or network loss.
9. Verify logs contain no repeated exceptions during steady-state polling.
10. Verify unload and reload of the integration.
11. Verify Home Assistant restart recovery (integration re-initialises cleanly).

---

## 8. Release Blockers

| # | Blocker | Detail |
|---|---------|--------|
| **B1** | No hassfest validation in CI | No `home-assistant/hassfest` action step in `.github/workflows/ci.yaml`. Required to confirm manifest machine-validity before HACS listing. |
| **B2** | No HACS validation action in CI | No `hacs/action@main` workflow step. CI installs `hacs` as pip test infra only, which is not equivalent to HACS manifest validation. |
| **B3** | No GitHub release tag for `2.8.0` | No git tag `2.8.0` or `v2.8.0`. HACS requires a GitHub release with matching tag to distribute. |
| **B4** | Real-device validation undocumented | No evidence of testing against a physical ThesslaGreen device. Required for credible release notes and `quality_scale: silver` maintenance. |

---

## 9. Non-Blocking Follow-Ups

| # | Item |
|---|------|
| N1 | **Dependabot PR #1567** (pydantic update) remains separate and untouched by this audit. |
| N2 | CHANGELOG heading for 2.8.0 uses `## 2.8.0 —` format; older entries use `## [X.Y.Z] - date` anchored format. Cosmetic inconsistency — may affect automated changelog tooling. |
| N3 | CI `push` trigger only covers `main`/`master`; does not trigger on push to `dev`. |
| N4 | No GitHub release tag or release notes entry for `v2.8.0`. |

---

## 10. Confirmations

- **pydantic**: unchanged. Still pinned at `2.12.2`. No version bump, no dependency changes.
- **PR #1567**: untouched. Not referenced, not cherry-picked, not merged.
- **main branch**: not used. All work is on `claude/release-readiness-audit-5xXvn` targeting `dev`. `main` was not read as source of truth, not merged, not compared.
- **Runtime code**: unchanged. Only documentation files created/modified in this audit.
- **CI**: not weakened. `.github/workflows/ci.yaml` was not modified.
- **Tests**: not removed, not skipped, not xfailed.

---

## 11. Files Changed in This Audit

- `docs/release_readiness.md` — this file (new)

No production code, tests, CI workflows, manifest.json, hacs.json, or dependency files were modified.

---

## 12. PR Target Branch

**PR base: `dev`**

Do not merge to `main`.
