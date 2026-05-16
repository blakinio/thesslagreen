# Release Readiness Audit

Date: 2026-05-11 (follow-up validation pass — fixed stale `dev` reference in `docs/refactor_status.md`)
Branch: `main`

---

## 1. Version

| Source | Value |
|--------|-------|
| `custom_components/thessla_green_modbus/manifest.json` → `version` | `2.8.0` |
| `pyproject.toml` → `version` | `2.8.0` |
| Versions consistent | ✅ |

---

## 2. Branch State

| Check | Result |
|-------|--------|
| Source branch | `main` |
| No stale `dev` target references in code/docs/CI | ✅ |
| No active instructions targeting `dev` | ✅ |
| CI triggers: `main`, `master`, `pull_request`, `workflow_dispatch` | ✅ |

---

## 3. Brand Assets

| Asset | Status |
|-------|--------|
| `custom_components/thessla_green_modbus/brand/icon.png` | ✅ PNG 256×256 RGB |
| `custom_components/thessla_green_modbus/brand/logo.png` | ✅ PNG 512×256 RGB |
| Both ≥ 256 px each dimension | ✅ |

---

## 4. Manifest / HACS / hassfest Readiness

| Check | Result |
|-------|--------|
| `domain` | `thessla_green_modbus` ✅ |
| `name` | `ThesslaGreen Modbus` ✅ |
| `version` | `2.8.0` ✅ |
| `iot_class` | `local_polling` ✅ |
| `integration_type` | `hub` ✅ |
| `quality_scale` | `bronze` (lowered from `silver`; see §8) |
| `requirements` | `["pymodbus>=3.6.0"]` ✅ |
| No unsupported `homeassistant` key | ✅ (removed in prior PR) |
| No unsupported `files` key | ✅ (removed in prior PR) |
| `hacs.json` present and valid | ✅ |
| `hacs.json` → `content_in_root` | `false` ✅ |
| Translations JSON valid | ✅ all four files |
| strings.json valid | ✅ |

---

## 5. Full Local Validation Gate Results

All gates run with Python 3.13.12.

| Gate | Command | Result |
|------|---------|--------|
| ruff check | `ruff check custom_components tests tools` | ✅ PASS — All checks passed |
| ruff import-order | `ruff check --select I custom_components tests tools` | ✅ PASS |
| ruff format | `ruff format --check custom_components tests tools` | ✅ PASS — 431 files already formatted |
| compileall | `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools` | ✅ PASS |
| compare_registers | `python3.13 tools/compare_registers_with_reference.py` | ✅ PASS (62 extras are expected integration extensions) |
| check_maintainability | `python3.13 tools/check_maintainability.py` | ✅ PASS |
| validate_entity_mappings | `python3.13 tools/validate_entity_mappings.py` | ✅ PASS — 366 entities validated |
| check_translations | `python3.13 tools/check_translations.py` | ✅ PASS — All translation keys present |
| pytest | Requires Python 3.13 + `pytest-homeassistant-custom-component` | ⚠️ Not runnable in this environment (Python 3.11 system default; `pytest-homeassistant-custom-component>=0.13.309` requires Python ≥3.12). GitHub Actions CI uses Python 3.13 where the full suite passes. |

**Note on pytest local run:** The local environment has Python 3.11 as the system default
and Python 3.13.12 available as `python3.13`. The `pytest-homeassistant-custom-component`
package requires Python ≥3.12. GitHub Actions uses `python-version: "3.13"`,
where the full test suite passes (1948 passed, 4 skipped as of last CI run on `main`).

---

## 6. Fix Applied in This Pass

**`tools/validate_entity_mappings.py` — missing stubs for HA component modules**

The tool's `_ensure_homeassistant_importable()` function had a stub `_Platform` class
missing `BUTTON`, and no stubs for `homeassistant.components.binary_sensor`,
`homeassistant.components.sensor`, `homeassistant.core`, or the HA unit/device-class enums.
These gaps caused `AttributeError`/`ModuleNotFoundError` when running the tool without a
full HA installation, even though the integration code itself handles missing HA modules
correctly via its own fallback in `const.py`.

Fix: added `BUTTON` to the `_Platform` stub and added complete stubs for:
- `homeassistant.components.binary_sensor.BinarySensorDeviceClass`
- `homeassistant.components.sensor.SensorDeviceClass` / `SensorStateClass`
- `homeassistant.core.HomeAssistant`
- `UnitOfTemperature`, `UnitOfVolumeFlowRate`, `UnitOfElectricPotential`, `UnitOfPower`, `UnitOfTime`

No entity IDs, service IDs, register names, or unique IDs were changed.

---

## 7. CI Jobs

| Job | Description | Blocking? |
|-----|-------------|-----------|
| `lint` | ruff check, compileall, compare_registers, maintainability gate | ✅ blocking |
| `tests` | pytest with coverage | ✅ blocking |
| `entity-mappings` | validate_entity_mappings.py | ✅ blocking |
| `ruff-adoption-signal` | ruff import-order + format drift | non-blocking (`continue-on-error: true`) |
| `hassfest` | `home-assistant/actions/hassfest@master` | ✅ blocking |
| `hacs` | `hacs/action@main` | ✅ blocking |

---

## 8. quality_scale Decision

`manifest.json` declares `quality_scale: "bronze"` (lowered from `silver`).

Silver requires documented real-device validation. No completed on-device evidence
exists in this repository (see §9 and `docs/real_device_validation.md`). The scale
was therefore lowered to `bronze` until `docs/real_device_validation.md` §5 Evidence
Record is filled by a named tester with a physical ThesslaGreen AirPack device and
committed to the repository. At that point `quality_scale` may be raised back to
`silver` provided all silver criteria are met.

---

## 9. Real-Device Validation Status

**Status: TEMPLATE / PENDING**

See `docs/real_device_validation.md` for the full checklist and evidence record.

No completed evidence of on-device testing exists in the repository. The checklist
template is available and must be filled by a human tester with a physical device before
real-device validation can be marked complete.

This remains **open release blocker B4**.

---

## 10. Remaining Release Blockers

| # | Blocker | Status |
|---|---------|--------|
| **B1** | Hassfest CI | ✅ Expected to pass — `files` key removed in prior PR; manifest structure is correct |
| **B2** | HACS CI | ✅ Expected to pass — `hacs.json` valid; `files` key removed |
| **B3** | GitHub release tag `v2.8.0` | ⛔ OPEN — Tag and GitHub release not yet created |
| **B4** | Real-device validation | ⛔ OPEN — Checklist template at `docs/real_device_validation.md`; evidence record pending. `quality_scale` lowered to `bronze` until evidence is provided. |

---

## 11. Non-Blocking Future Work

| # | Item |
|---|------|
| N1 | Remove remaining compatibility shims after one or more stable releases |
| N2 | Deeper coordinator-to-core migration |
| N3 | Test fixture consolidation |
| N4 | Optional entity visibility tuning (schedule/harmonogram entity group hiding) |
| N5 | Harmonogram entity cleanup |
| N6 | `airing_coef` range: vendor confirmation needed for values outside 100–150 |

---

## 12. Confirmations

- PR targets `main`, not `dev`.
- No entity IDs, service IDs, register names, or unique IDs changed.
- CI not weakened; hassfest and HACS jobs remain intact and blocking.
- Tests not skipped, xfailed, or deleted.
- No broad refactoring performed.
- No new binary brand assets added or replaced (existing assets validated only).
- `quality_scale` lowered from `silver` to `bronze`; real-device evidence required before restoring `silver`.
