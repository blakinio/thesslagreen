# Pre-Device Integration Validation

Date: 2026-05-09
Branch: `claude/finalize-release-readiness-ozgQt`
Python: 3.13.12 (venv `/tmp/venv_thessla`)

This document records the results of a full pre-device validation pass
performed before connecting to physical ThesslaGreen AirPack hardware.
It covers: all static validation gates, test-suite execution, targeted
coverage gaps closed, HACS/hassfest manifest audit, and a readiness
verdict for on-device testing.

---

## 1. Baseline Validation Gates

All gates run on Python 3.13.12.

| Gate | Command | Result |
|------|---------|--------|
| ruff lint | `ruff check custom_components tests tools` | ✅ PASS — All checks passed |
| ruff import order | `ruff check --select I custom_components tests tools` | ✅ PASS |
| ruff format | `ruff format --check custom_components tests tools` | ✅ PASS — 421 files formatted |
| compileall | `python3.13 -m compileall -q custom_components tests tools` | ✅ PASS |
| compare_registers | `python3.13 tools/compare_registers_with_reference.py` | ✅ PASS (exit 0) |
| check_maintainability | `python3.13 tools/check_maintainability.py` | ✅ PASS |
| validate_entity_mappings | `python tools/validate_entity_mappings.py` | ✅ PASS — 366 entities validated |
| **pytest** | `python -m pytest tests/ -q` | ✅ PASS — **1959 passed, 4 skipped** |

---

## 2. Test Coverage Inventory

236 test files across all integration areas:

| Area | Files | Notes |
|------|-------|-------|
| Config flow | 13 | TCP, RTU, reauth, options, validation, duplicates |
| Coordinator | 26 | lifecycle, reconnect, error paths, writes, scan, statistics |
| Scanner | 19 | capabilities, firmware, IO paths, error paths, cache |
| Modbus transport | 8 | TCP, RTU, retry, errors, close |
| Entity platforms | 8 | sensor, binary_sensor, climate, fan, number, select, switch, text |
| Services | 10 | dispatch, handlers (modes, maintenance, schedule, temperature, bypass, GWC) |
| Register data | 14 | loaders, schema, decoders, JSON schema, uniqueness |
| Entity mappings | 8 | static, builder, transformations, platform contracts |
| Diagnostics | 2 | redaction, offline error formatting |
| Translations | 3 | strings, unused, JSON validity |
| Tools | 4 | validate_entity_mappings, compare_registers, check_maintainability, validate_dashboard |
| Misc | 17 | backoff, chunking, migration, API contracts, etc. |

---

## 3. Coverage Gaps Identified and Closed

### 3.1 `repairs.py` — zero coverage → closed

`async_create_fix_flow` had no tests. Added `tests/test_repairs.py` with 4 tests:

| Test | Verifies |
|------|---------|
| `test_async_create_fix_flow_returns_confirm_repair_flow` | Returns `ConfirmRepairFlow` for known issue_id |
| `test_async_create_fix_flow_unknown_issue_id` | Unknown issue_ids handled gracefully |
| `test_async_create_fix_flow_none_data` | `None` data accepted without raising |
| `test_async_create_fix_flow_with_data_dict` | Non-None data dict accepted |

### 3.2 `entity_registry_enabled_default` — zero coverage → closed

The Silver quality-scale change in `sensor.py` and `binary_sensor.py`
(`_attr_entity_registry_enabled_default = False` for DIAGNOSTIC entities)
had no test coverage. Added `tests/test_entity_disabled_by_default.py`
with 6 tests:

| Test | Verifies |
|------|---------|
| `test_diagnostic_sensor_disabled_by_default` | Single DIAGNOSTIC sensor is disabled by default |
| `test_non_diagnostic_sensor_enabled_by_default` | Non-DIAGNOSTIC sensor is not disabled |
| `test_all_diagnostic_sensors_disabled_by_default` | All 7 DIAGNOSTIC sensor definitions disabled |
| `test_diagnostic_binary_sensor_disabled_by_default` | Single DIAGNOSTIC binary sensor disabled |
| `test_non_diagnostic_binary_sensor_enabled_by_default` | Non-DIAGNOSTIC binary sensor not disabled |
| `test_all_diagnostic_binary_sensors_disabled_by_default` | All 56 DIAGNOSTIC binary sensor definitions disabled |

**New total: 1959 passed, 4 skipped** (10 tests added, 0 regressions).

---

## 4. HACS / Hassfest Manifest Audit

### manifest.json
- `files` key: **absent** ✅ (removed in PR #1604 — was causing hassfest/HACS CI failures)
- All keys validated against `homeassistant.loader.Manifest` TypedDict: **no unknown keys** ✅
- `homeassistant` key (min HA version `2026.1.0`): standard for custom components, accepted by hassfest ✅
- JSON parses without error ✅

Manifest keys present: `domain`, `name`, `codeowners`, `config_flow`, `dependencies`,
`documentation`, `homeassistant`, `iot_class`, `issue_tracker`, `quality_scale`,
`requirements`, `version`, `integration_type`, `after_dependencies`, `loggers`, `dhcp`, `zeroconf`

### hacs.json
- `name`: `"ThesslaGreen Modbus"` ✅
- `content_in_root`: `false` ✅ (integration under `custom_components/`)
- `render_readme`: `true` ✅
- JSON parses without error ✅

### CI jobs (`.github/workflows/ci.yaml`)
- `home-assistant/actions/hassfest@main` job: present ✅
- `hacs/action@main` job (`category: integration`): present ✅
- Both jobs: **fix applied in PR #1604, pending re-run CI confirmation**

---

## 5. Static File Completeness

Verified by `tests/test_manifest_files.py::test_required_static_files_exist_on_disk`:
`services.yaml`, `strings.json`, all `options/*.json`, `registers/*.json`, `translations/*.json` — all present ✅

---

## 6. Other Pre-Device Checks

### Integration import
```
python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools
```
✅ PASS — all `.py` files compile without errors.

### No HA imports in scanner
Invariant: `scanner/` module must not import from `homeassistant.*`.
✅ Confirmed by existing test gate and invariant check.

### Coordinator `__all__`
```python
coordinator.__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]
```
✅ Confirmed by invariant check.

### Flat `coordinator.py` absent
✅ Confirmed — coordinator is a package (`coordinator/`), not a flat file.

---

## 7. Areas NOT Covered by Simulated Tests (Require Real Device)

The following can only be validated with a physical ThesslaGreen AirPack unit:

| Area | Why simulation is insufficient |
|------|-------------------------------|
| Actual Modbus TCP connection | Mock transport; real register map and timing unknown |
| Firmware version detection | Requires real device to return version registers |
| Register availability scan | `DeviceScanner` probes ranges that vary by firmware |
| Fan/climate control writes | Requires round-trip read-back to verify effect |
| Multi-register write paths | Requires real register coherence |
| Reconnect after network drop | Timing-sensitive; OS-level TCP behavior |
| HA restart recovery | Requires HA running with real persistent state |
| Energy sensor accumulation | Requires continuous operation |

See [docs/real_device_validation.md](real_device_validation.md) for the full
checklist and evidence template.

---

## 8. Readiness Verdict

| Item | Status |
|------|--------|
| All static gates (ruff, compileall, compare, maintainability, entity_mappings) | ✅ PASS |
| Full pytest suite | ✅ **1959 passed, 4 skipped** |
| Repairs platform coverage | ✅ Added (4 tests) |
| Disabled-by-default DIAGNOSTIC entities coverage | ✅ Added (6 tests) |
| manifest.json hassfest-clean | ✅ No unknown keys |
| hacs.json valid | ✅ All required fields |
| CI hassfest job | ⚠️ Fix applied (PR #1604), CI re-run pending |
| CI HACS job | ⚠️ Fix applied (PR #1604), CI re-run pending |
| Real-device validation | ⛔ Not yet — requires physical hardware |
| GitHub release tag `v2.8.0` | ⛔ Not yet created |

**Pre-device validation: COMPLETE.** The integration is ready for on-device
testing as soon as CI re-runs confirm the hassfest/HACS fixes hold.
Real-device validation remains the final open blocker before a formal release.

---

## 9. Files Changed in This Pass

| File | Change |
|------|--------|
| `tests/test_repairs.py` | **New** — 4 tests for `async_create_fix_flow` |
| `tests/test_entity_disabled_by_default.py` | **New** — 6 tests for disabled-by-default DIAGNOSTIC entities |
| `docs/pre_device_validation.md` | **New** — this document |
