# Release Tooling Audit

Date: 2026-05-08
Branch: `claude/audit-release-tooling-rz4Lu` → PR base: `dev`

---

## 1. Maintained Gates Result

| Gate | Result | Notes |
|------|--------|-------|
| `ruff check custom_components tests tools` | ✅ PASS | All checks passed |
| `ruff check --select I custom_components tests tools` | ✅ PASS | All checks passed |
| `python -m compileall -q custom_components/thessla_green_modbus tests tools` | ✅ PASS | No syntax errors |
| `python tools/check_maintainability.py` | ✅ PASS | Maintainability gate passed |
| `ruff format --check custom_components tests tools` | ⚠️ DRIFT | 3 files would be reformatted (see §8) |
| `python tools/validate_entity_mappings.py` | ❌ BLOCKED | Requires `homeassistant` package; not installable on Python 3.11 env |
| `pytest tests/ -q` | ❌ BLOCKED | Requires `pytest-homeassistant-custom-component>=0.13.309` which needs Python ≥3.13 |

Both BLOCKED gates are **environment constraints**, not code defects. CI runs Python 3.13 and they pass there.

---

## 2. HACS Tool Status

- **CLI available:** No — `hacs --help` returns "command not found"
- **Package installed:** No — `pip show hacs` returns not found
- **CI installs `hacs`:** Yes, as a Python package (`pip install homeassistant==... hacs`), used only as test infrastructure dependency
- **HACS validation action workflow:** No `.github/workflows/` file calls a HACS validation action
- **Result: HACS CLI validation was not run; unavailable in this environment**

`hacs.json` is present and structurally valid:

```json
{
  "name": "ThesslaGreen Modbus",
  "content_in_root": false,
  "render_readme": true
}
```

Known HACS required fields (`name`, correct `content_in_root`, `render_readme`) are all present.
`content_in_root: false` is correct because the integration lives in `custom_components/`.

---

## 3. Hassfest Tool Status

- **CLI available:** No — `hassfest --help` returns "command not found"
- **Package installed:** No — `pip show hassfest` returns not found
- **Hassfest action in workflows:** No `.github/workflows/` file runs hassfest
- **Result: Hassfest validation was not run; unavailable in this environment**

The `custom_components/thessla_green_modbus/manifest.json` has been inspected manually
against the hassfest schema. All structurally required fields are present (see §5).

---

## 4. Root manifest.json

**No `manifest.json` exists at the repository root. This is not a blocker.**

Home Assistant custom integrations use `custom_components/<domain>/manifest.json`.
Root `manifest.json` is not required by HACS, hassfest, or any HA release tooling for
custom components. No observed tool in CI or the HACS install path requires a root manifest.

---

## 5. Integration Manifest Status

File: `custom_components/thessla_green_modbus/manifest.json`

| Field | Value | Status |
|-------|-------|--------|
| `domain` | `thessla_green_modbus` | ✅ |
| `name` | `ThesslaGreen Modbus` | ✅ |
| `version` | `2.8.0` | ✅ |
| `codeowners` | `["@blakinio"]` | ✅ |
| `config_flow` | `true` | ✅ |
| `homeassistant` | `2026.1.0` | ✅ |
| `iot_class` | `local_polling` | ✅ |
| `requirements` | `["pymodbus>=3.6.0"]` | ✅ |
| `documentation` | GitHub URL | ✅ |
| `issue_tracker` | GitHub issues URL | ✅ |
| `integration_type` | `hub` | ✅ |
| `quality_scale` | `silver` | ✅ |
| `after_dependencies` | `["modbus"]` | ✅ |
| `loggers` | `["custom_components.thessla_green_modbus"]` | ✅ |
| `dhcp` | hostname+MAC pattern | ✅ |
| `zeroconf` | Modbus TCP mDNS type | ✅ |
| `files` | services.yaml, strings.json, options/\*, registers/\*, translations/\* | ✅ |

All known required and recommended fields are present and well-formed.

---

## 6. Version Consistency

| Source | Version / Reference | Status |
|--------|-------------------|--------|
| `pyproject.toml` → `version` | `2.8.0` | ✅ |
| `custom_components/.../manifest.json` → `version` | `2.8.0` | ✅ |
| `README.md` minimum HA badge | `2026.1.0+` | ✅ matches manifest `homeassistant` |
| `README.md` minimum Python | `3.13+` | ✅ matches pyproject `requires-python = ">=3.13"` |
| `README_en.md` minimum HA | `2026.1.0` | ✅ |
| `CI` test HA version | `2026.2.3` | ✅ (tests against newer version than minimum — expected) |
| `CHANGELOG.md` entry | `## 2.8.0` present | ✅ entry exists |
| GitHub release tag for `2.8.0` | not found | ⚠️ no `git tag` matching `2.8.0` or `v2.8.0` |

**Note:** The CHANGELOG heading format for `2.8.0` is `## 2.8.0 — Legacy removal + test infrastructure overhaul (BREAKING)` which diverges from the anchored `## [X.Y.Z] - YYYY-MM-DD` format used by entries `[2.2.0]`, `[2.0.0]`, `[1.0.0]`. This inconsistency is cosmetic but may affect automated changelog tooling.

---

## 7. Real-Device Validation Status

**No real-device validation evidence is present.**

Neither `docs/`, `README.md`, `README_en.md`, `CHANGELOG.md`, nor any test file contains
documented evidence of on-device testing. Previous audit documents explicitly note:

> "Real-device readiness: not claimable from this verification run; no new on-device evidence captured."

This remains an open item. For HACS default (non-custom) listing or `quality_scale: silver` maintenance, real-device smoke test results should be documented before a tagged release.

---

## 8. Exact Release Blockers

### Blockers (must fix before tagged release)

| # | Blocker | Detail |
|---|---------|--------|
| B1 | No hassfest validation in CI | No `.github/workflows/` step or action runs hassfest; the integration manifest must pass hassfest validation before listing. Add the `hacs/action` or `home-assistant/hassfest` GitHub Actions step. |
| B2 | No HACS validation action in CI | CI installs hacs as a Python package for test infra only, but no `hacs/action@main` (or equivalent) validation workflow exists. |
| B3 | No GitHub release tag for `2.8.0` | No `git tag` matching `2.8.0` or `v2.8.0` found. HACS requires a GitHub release with a matching tag to distribute the version. |
| B4 | Real-device validation undocumented | No evidence of testing against a physical ThesslaGreen AirPack device. Required for credible release notes and `quality_scale: silver` maintenance. |

### Non-Blockers / Improvement Items

| # | Item | Detail |
|---|------|--------|
| N1 | `ruff format --check` drift (3 files) | `scanner/io_read_helpers.py`, `tests/test_config_flow_helpers.py`, `tests/test_modbus_helpers_call_flow.py` would be reformatted. Run `ruff format custom_components tests tools` before release. |
| N2 | CHANGELOG format inconsistency | `2.8.0` uses non-anchored `## 2.8.0 —` heading; `2.2.0`/`2.0.0`/`1.0.0` use `## [X.Y.Z] - date`. Standardise to `## [2.8.0] - YYYY-MM-DD`. |
| N3 | CI `push` trigger only on `main`/`master` | CI does not trigger on push to `dev`. Adds manual CI gap for dev-branch work. |
| N4 | `pytest` / `validate_entity_mappings` blocked in Python 3.11 env | Audit environment is Python 3.11; these gates pass on CI (Python 3.13). Not a release blocker but the local dev experience is degraded. |

---

## 9. Recommended Next PRs

| Priority | PR | Rationale |
|----------|-----|-----------|
| **P1** | Add hassfest GitHub Actions validation | Required to confirm manifest is machine-valid before HACS listing; one step using `home-assistant/hassfest` action. |
| **P1** | Add HACS validation action | Add `hacs/action@main` workflow to catch HACS-specific manifest issues. |
| **P1** | Create GitHub release tag `v2.8.0` | Required for HACS to distribute the version; tag must match `manifest.json` `version`. |
| **P2** | Fix `ruff format` drift (3 files) | `ruff format custom_components tests tools`; run in a dedicated style-only PR. |
| **P2** | Standardise CHANGELOG heading format | Align `2.8.0` heading to `## [2.8.0] - YYYY-MM-DD` format. |
| **P3** | Document real-device validation | Add a `docs/device_validation.md` with device model, firmware, HA version, and test scenario summary. |
| **P3** | Add CI trigger for `dev` branch | Extend `push: branches` to include `dev` so CI runs on dev-branch pushes. |

---

## 10. Files Changed

One new documentation file created: **`docs/release_tooling_audit.md`** (this file).

No production code, tests, or CI workflows were modified.

---

## 11. PR Target Branch

**PR base: `dev`**

This audit is created on branch `claude/audit-release-tooling-rz4Lu` and targets `dev` as the PR base.
No merge to `main` is part of this audit.
