# Real-Device Validation Report

**Status: Partial real-device validation / evidence collection pending**

> Evidence from the user confirms basic integration functionality on a real ThesslaGreen AirPack
> device in Home Assistant, but formal test-case sign-off, screenshots, and full log excerpts
> have not yet been committed to this repository.
> This document must not be marked PASS until all evidence listed in section 4 is provided.

---

## 1. Validation Status

| Item | Status |
|------|--------|
| Overall validation | PARTIAL — user-reported, formal evidence pending |
| Quality scale gate | Bronze — no upgrade until formal evidence is committed |
| Fan percentage fix (#1682) | FIXED in code; real-device re-test evidence pending |
| Temperature sensors | User-reported working; no log evidence committed |
| Vendor coverage | 353/353 registers — verified by tool (`compare_airpack4_vendor_coverage.py`) |
| Dangerous entities | Present and enabled; `entity_category=config` added (this PR) |

---

## 2. Environment

| Item | Value |
|------|-------|
| Home Assistant Core | Pending user data |
| Integration version | Current `main` — commit `bea0fdc` (post-PR #1682) |
| Device model | ThesslaGreen AirPack 4 (user-reported) |
| Firmware version | Pending — device registers may not expose firmware |
| Connection type | Pending user data (TCP / RTU) |
| Host / Port / Slave ID | Pending user data |
| Python on HA host | ≥ 3.13 (required by pyproject.toml) |

---

## 3. Validated Items Checklist

| Item | Status | Evidence |
|------|--------|----------|
| Integration setup completes without traceback | User-reported OK | No log committed |
| Entity count after reload/restart | User-reported ~370 entities visible | No screenshot committed |
| Temperature sensors available | User-reported working | No log committed |
| Fan percentage displays correct % after #1682 | Pending re-test | Fix is in code (unit tests pass) |
| Bypass / free cooling | User-reported working | No log committed |
| Device clock entity visible | User-reported `clock` entity present | No screenshot committed |
| Clock sync | Not yet tested on device | — |
| Writable entities | Not yet verified on device | — |
| `validate_known_registers` service | Not yet tested on device | — |
| `scan_all_registers` service | Not yet tested on device | — |
| Diagnostics download | Not yet tested on device | — |
| No transaction_id mismatch | Not yet verified | — |
| No blocking I/O warning | Not yet verified | — |
| Dangerous entities present and enabled | Confirmed by code audit | entity_category=config added, not disabled |

---

## 4. Evidence Needed from User

The following data must be provided and committed before formal validation is complete:

1. **HA Core version** (e.g., `2026.5.x`)
2. **Integration commit SHA** installed on device (run `git log --oneline -1` in integration directory)
3. **Connection type**: TCP / RTU / TCP_RTU
4. **Host / Port / Slave ID** used in config entry
5. **Scan settings** (safe_scan, deep_scan, max_registers_per_request if non-default)
6. **Screenshot or log** after integration reload showing entity count and no errors
7. **Fan percentage result after #1682** — HA state of `fan.thesslagreen_ventilation` at various speeds
8. **Clock sync result** if tested (`sync_device_clock` service call log)
9. **Filtered log lines** from integration setup/first update cycle:
   ```
   grep "thessla_green" /config/home-assistant.log | head -50
   ```
10. **Any observed errors** during normal operation

---

## 5. Automated Test Coverage

The integration has comprehensive unit tests (pytest, no real device required):

| Test area | Status |
|-----------|--------|
| Entity mapping validation | ✅ All pass |
| Fan percentage calculation | ✅ `test_fan_percentage_109_clamped_to_100` passes |
| Dangerous entity risk metadata | ✅ All risk_level/risk_category/safety_warning present |
| Dangerous entity entity_category=config | ✅ Added in this PR, tests pass |
| AirPack4 vendor coverage | ✅ 0 missing registers |
| Translation keys | ✅ All pass |
| Coordinator update cycle | ✅ Mocked tests pass |

---

## 6. Real-Device Findings Cleanup (2026-05-09, pre-#1682)

The following findings were identified from exported HA state data and addressed:

| Finding | Status | Fix / Decision | Evidence |
|---|---|---|---|
| Fan percentage 109 (> 100) | FIXED | `fan.py` `percentage` property clamped to 100 per HA spec; raw value preserved in `supply_percentage` attribute | Unit test `test_fan_percentage_109_clamped_to_100`; #1682 |
| `number.airing_coef` state 50 outside range 100–150 | NEEDS_VENDOR_CONFIRMATION | Write range unchanged (100–150) per declared metadata. Reading 50 does not crash. | Tests `test_airing_coef_native_value_below_min_does_not_crash` |
| `binary_sensor.fire_alarm` raw true / state off | CONFIRMED_CORRECT | NC (normally-closed) contact: raw True = circuit closed = no alarm = `is_on=False`. Mapping has `inverted: True`. | Tests `test_fire_alarm_raw_true_means_no_alarm` |
| `binary_sensor.dp_duct_filter_overflow` raw true / state on | CONFIRMED_CORRECT | Raw True = problem detected. `device_class=problem` is correct. | Test `test_dp_duct_filter_overflow_raw_true_is_problem` |
| `sensor.serial_number` unavailable / device info Unknown | DEFERRED (partially improved) | `sw_version` now assembled from `version_major.version_minor CF<cf_version>`. Serial decode deferred. | Tests `test_sw_version_uses_version_registers_when_firmware_unknown` |
| `sensor.rekuperator_active_errors` state unknown | FIXED | `native_value` returns `"none"` (not Python None) when no error codes are active. | Tests `test_active_errors_sensor_returns_none_string_when_no_errors` |
| `switch.bypass_off` / `switch.gwc_off` misleading names | FIXED | Translation-only fix to "Bypass Locked" / "GWC Locked". Entity IDs unchanged. | Translation tests pass |

---

## 7. Release Gate

Real-device validation is **not** complete until:

1. All test cases in section 3 are marked **Pass** with committed evidence.
2. The Evidence section (section 4) is fully populated.
3. A named tester has signed off with the commit SHA.

Until that point, quality_scale remains **bronze** and this document is **not a release sign-off**.
