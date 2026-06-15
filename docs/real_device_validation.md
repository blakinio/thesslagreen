# Real-Device Validation Report

**Status: Partial real-device validation / evidence collection in progress**

> Evidence from the user confirms basic integration functionality on a real ThesslaGreen AirPack
> device in Home Assistant. The 2026-05-30 HA log export confirms successful TCP setup,
> service registration, and absence of critical ThesslaGreen errors during the captured setup.
> The 2026-06-09 validate_known_registers result on HA OS 17.3 / HA Core 2026.6.1 confirms
> stable register coverage: supported=338, missing=19. All 19 missing registers are classified.
> Formal sign-off is still pending for HA state screenshots, fan percentage, clock sync, and service tests.
> This document must not be marked PASS until all evidence listed in section 4 is provided.

---

## 1. Validation Status

| Item | Status |
|------|--------|
| Overall validation | PARTIAL — HA log evidence committed; HA state/service evidence still pending |
| Quality scale gate | Bronze — no upgrade until formal evidence is complete |
| Deep scan | Not required for validation — deep scan is offline/diagnostic-only; normal scan (deep_scan=False) is sufficient for all real-device validation steps |
| Targeted read-back after writes | PENDING real-device validation — see §9 below |
| Fan percentage fix (#1682) | FIXED in code; real-device state screenshot/re-test evidence pending |
| Dangerous entities config category (#1683) | Confirmed by code audit; entity_category=config, remain enabled |
| IO ownership cleanup (#1684/#1688) | DeviceClient is sole IO owner; HA setup log after cleanup is clean/partial evidence |
| CI / Python 3.13 validation (#1686) | CI now requires Python 3.13, ruff checks blocking |
| Temperature sensors | User-reported working; HA state evidence pending |
| Vendor coverage | 353/353 registers — verified by tool (`compare_airpack4_vendor_coverage.py`) |

---

## 2. Environment

| Item | Value |
|------|-------|
| Home Assistant OS | 17.3 (confirmed 2026-06-09 validate_known_registers session) |
| Home Assistant Core | 2026.6.1 (confirmed 2026-06-09 validate_known_registers session) |
| Integration version | Current repo `main` after #1688 is `3c7215d`; installed HA commit not proven by log |
| Device model | ThesslaGreen AirPack 4 (user-reported) |
| Firmware version | Unknown / not exposed by this device scan; non-critical |
| Connection type | TCP, Auto-selected by config flow scan |
| Host / Port / Slave ID | `192.168.3.12` / `8899` / `10` |
| Scan interval | `30s` |
| max_registers_per_request | Pending user data |
| force_full_register_list | Pending user data |
| connection_mode | Auto / TCP selected |
| Python on HA host | ≥ 3.13 required by pyproject.toml; exact HA host version pending |
| Evidence source | `home-assistant_2026-05-30T10-48-08.801Z.log` |

> Note: the same HA log contains a HACS download failure for `3c7215d` because HACS tried to
> download it as a branch (`refs/heads/3c7215d.zip`). Therefore the log confirms the integration
> runs on the real device, but does **not** by itself prove that HA was running commit `3c7215d`.

---

## 3. Validated Items Checklist

| Item | Status | Evidence |
|------|--------|----------|
| Integration setup completes without traceback | PASS — log evidence | `setup completed successfully`; no ThesslaGreen traceback in exported log |
| Reload / restart works | PARTIAL PASS — log evidence | Integration unload and later setup completion observed |
| Config-flow scan cache used | PASS — log evidence | `Using config-flow scan cache` |
| Services registered | PASS — log evidence | `ThesslaGreen Modbus services registered successfully` |
| TCP connection established | PASS — log evidence | TCP connection to `192.168.3.12:8899`, slave `10` |
| Entities created after restart | User-reported ~370 entities visible | Screenshot/state export pending |
| Approximate entity count | ~367 verified by tools; user-reported ~370 | Screenshot pending |
| Temperature sensors available | User-reported working | HA state evidence pending |
| Fan percentage displays correct % after #1682 | Pending re-test | Fix in code; unit tests pass; HA state evidence pending |
| Supply fan percentage sane (0–100) | Pending re-test | — |
| Exhaust fan percentage sane (0–100) | Pending re-test | — |
| Supply m³/h sensor visible separately | Not yet verified on device | — |
| Exhaust m³/h sensor visible separately | Not yet verified on device | — |
| Bypass / free cooling | User-reported working | Screenshot/state evidence pending |
| Device clock entity visible | User-reported `clock` entity present | Screenshot/state evidence pending |
| Clock sync | Not yet tested on device | — |
| Writable entities work | Not yet verified on device | — |
| `refresh_device_data` service | Not yet tested on device | — |
| `validate_known_registers` service | PASS — stable across 3+ runs (PRs #1709/#1711, confirmed 2026-06-09 on HA OS 17.3 / Core 2026.6.1) | supported=338, missing=19 stable; all 19 classified; no transaction_id mismatch; retried_individual_count=62 |
| `scan_all_registers` service | Not yet tested on device | — |
| Diagnostics download | Not yet tested on device | — |
| No transaction_id mismatch observed | PASS — log evidence | No `transaction_id` mismatch in exported ThesslaGreen log lines |
| No blocking I/O warning in HA log | PASS — log evidence | No blocking I/O warning for ThesslaGreen in exported log |
| No false “Modbus transport disconnected” errors | PASS — log evidence | No false transport-disconnected error for ThesslaGreen in exported log |
| No ThesslaGreen ERROR entries | PASS — log evidence | No `ERROR` lines from `custom_components.thessla_green_modbus` |
| Unsupported firmware/model registers non-critical | PASS — log evidence | Firmware/version register read failed at DEBUG/WARNING, integration continued and setup completed |
| Scanner cancellation handling | PARTIAL PASS — log evidence | One cancelled `input_registers 0-0` read observed; scanner continued, detected capabilities, setup completed |
| Dangerous entities present and enabled | Confirmed by code audit | entity_category=config added in #1683, not disabled |

---

## 4. Evidence

### 4.1 HA log export — 2026-05-30

Provided file: `home-assistant_2026-05-30T10-48-08.801Z.log`.

Relevant ThesslaGreen setup lines:

```text
2026-05-30 12:44:03.898 INFO  verify_connection: connecting to 192.168.3.12:8899 (mode=tcp, timeout=10)
2026-05-30 12:44:14.761 INFO  verify_connection: auto-selected Modbus transport tcp for 192.168.3.12:8899
2026-05-30 12:44:41.941 INFO  Detected 14 capabilities
2026-05-30 12:45:20.462 DEBUG Setting up ThesslaGreen Modbus integration for ThesslaGreen
2026-05-30 12:45:20.746 INFO  Initializing ThesslaGreen device: ThesslaGreen via Modbus TCP (Auto) (192.168.3.12:8899) (slave_id=10, scan_interval=30s)
2026-05-30 12:45:20.751 INFO  Using config-flow scan cache
2026-05-30 12:46:00.838 INFO  ThesslaGreen Modbus services registered successfully
2026-05-30 12:46:00.838 INFO  ThesslaGreen Modbus integration setup completed successfully
```

Warnings observed during scan/setup:

```text
2026-05-30 12:44:15.686 DEBUG Failed to read firmware version registers: missing version_patch (4)
2026-05-30 12:44:24.763 WARNING Retry context layer=scanner op=read_input:0-0 ... reason=cancelled
2026-05-30 12:44:24.763 WARNING Aborted reading input registers 0-0 after 1/3 attempts due to timeout/cancellation
2026-05-30 12:44:41.942 WARNING The following registers were not found during scan: input_registers: version_major=0
2026-05-30 12:45:55.668 WARNING Setup of sensor platform thessla_green_modbus is taking over 10 seconds.
```

Interpretation:

- The firmware/model register warnings are non-critical for this device/firmware; setup continued.
- One scanner read cancellation was observed for `input_registers 0-0`; scanner continued and setup completed.
- Slow sensor platform setup is expected with a large entity set and completed successfully.
- No ThesslaGreen traceback, `transaction_id` mismatch, blocking I/O warning, or false transport-disconnected error was observed in the exported log.

### 4.3 validate_known_registers real-device evidence (PRs #1709 / #1711)

Real-device HA log lines observed after PRs #1709 and #1711, confirmed on HA OS 17.3 /
HA Core 2026.6.1 (2026-06-09):

```text
validate_known_registers started for climate.rekuperator_climate_control: batch=16, delay=100ms
validate_known_registers completed for climate.rekuperator_climate_control: supported=338, missing=19, by_type={'input_registers': 4, 'holding_registers': 15}
```

Stable result:

| Metric | Value |
|--------|-------|
| supported_count | 338 |
| missing_count | 19 |
| missing_by_type / input_registers | 4 |
| missing_by_type / holding_registers | 15 |
| retried_individual_count | 62 |

Result was stable across 3+ consecutive runs (same supported/missing counts each time).
No `transaction_id` mismatch was observed during or after the service call.

The `validate_known_registers` service response now includes a `register_classification`
field that maps each missing register name to its classification category. See §4.4 below
for the full classification.

**Safety note:** `validate_known_registers` uses the coordinator's active Modbus connection
under `_write_lock`. It does not open a second connection and is safe to call while the
integration is actively polling. Use this service for real-device register classification
instead of `scan_all_registers` (which opens a separate connection and causes
`transaction_id` mismatch errors).

### 4.4 Expected missing / optional registers on tested device

All 19 missing registers are classified below. These registers should **not** be removed
from the register map — they may be valid on other firmware/hardware variants.

#### Missing input_registers (4)

| Register | Classification | Notes |
|----------|---------------|-------|
| `compilation_days` | optional_firmware_metadata | Legacy firmware (FW 3.x) does not expose build timestamp |
| `compilation_seconds` | optional_firmware_metadata | Legacy firmware (FW 3.x) does not expose build timestamp |
| `version_patch` | optional_firmware_metadata | Legacy firmware exposes only version_major/version_minor |
| `water_removal_active` | optional_feature | Water removal (HEWR) feature not present on this unit |

#### Missing holding_registers (15)

| Register | Classification | Notes |
|----------|---------------|-------|
| `cfg_post_heater_mode` | hardware_gated | Post-heater capability absent on this hardware |
| `post_heater_on` | hardware_gated | Post-heater capability absent on this hardware |
| `cfgszf_fn_new` | expansion_or_service | Expansion/service firmware register |
| `cfgszf_fw_new` | expansion_or_service | Expansion/service firmware register |
| `exp_version` | expansion_or_service | Expansion module not present |
| `filter_exhaust_date_limit_get` | newer_firmware_api | Filter date API not available on this firmware |
| `filter_supply_date_limit_get` | newer_firmware_api | Filter date API not available on this firmware |
| `uart_0_baud` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_0_id` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_0_parity` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_0_stop` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_1_baud` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_1_id` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_1_parity` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_1_stop` | internal_service_uart | Internal UART configuration; inaccessible on normal device |

#### Classification categories

| Category | Meaning |
|----------|---------|
| `optional_firmware_metadata` | Build/version metadata not exposed by all firmware versions |
| `optional_feature` | Feature-gated register; absent when hardware feature is not present |
| `hardware_gated` | Register depends on hardware capability (e.g., post-heater) |
| `expansion_or_service` | Expansion module or service/firmware-related register |
| `newer_firmware_api` | API added in newer firmware; not available on legacy versions |
| `internal_service_uart` | Internal UART configuration; expected inaccessible via Modbus |
| `hardware_sensor_absent` | Hardware sensor not physically installed |

### 4.2 Evidence still needed from user

The following data must be provided and committed before formal validation is complete:

1. **HA Core version** (e.g., `2026.5.x`)
2. **Integration commit SHA actually installed in HA** (the 2026-05-30 log does not prove this because HACS failed to download `3c7215d` as a branch)
3. **max_registers_per_request / force_full_register_list / scan mode options**
4. **Screenshot or state export** after integration reload showing entity count and no errors
5. **Fan percentage result after #1682** — HA state of `fan.thesslagreen_ventilation` at various speeds
6. **Supply and exhaust m³/h sensor states** from HA Developer Tools
7. **Temperature sensor states** from HA Developer Tools
8. **Device clock state** and clock sync result if tested
9. **Service results** for `refresh_device_data`, `validate_known_registers`, `scan_all_registers`, and diagnostics
10. **Any observed errors** during normal operation

---

## 5. Automated Test Coverage

The integration has comprehensive unit tests (pytest, no real device required):

| Test area | Status |
|-----------|--------|
| Entity mapping validation | ✅ 367 entities pass |
| Fan percentage calculation | ✅ `test_fan_percentage_109_clamped_to_100` passes |
| Dangerous entity risk metadata | ✅ All risk_level/risk_category/safety_warning present |
| Dangerous entity entity_category=config | ✅ Added in #1683, tests pass |
| DeviceClient IO ownership | ✅ `test_coordinator_io_ownership.py` — 15 tests pass |
| AirPack4 vendor coverage | ✅ 0 missing registers |
| Translation keys | ✅ All pass |
| Coordinator lifecycle boundary | ✅ Coordinator no longer exposes removed lifecycle proxies after #1688 |
| Coordinator update cycle | ✅ Mocked tests pass |
| pymodbus pin consistency | ✅ manifest + pyproject consistent |

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
| `switch.bypass_off` / `switch.gwc_off` misleading names | FIXED | Translation-only fix to “Bypass Locked” / “GWC Locked”. Entity IDs unchanged. | Translation tests pass |

---

## 8. Smoke Test After Coordinator Proxy Cleanup (PRs #1697–#1702)

### Background

PRs #1697–#1702 completed a series of coordinator internal refactors with no Modbus runtime
behavior changes, no register address/name changes, and no entity/service/unique-ID changes:

| PR | Summary |
|----|---------|
| #1697 | Fixed stale `coordinator.get_register_map` test mocks and guards |
| #1698 | Removed stale `coordinator.get_register_map` mock calls from tests |
| #1699 | Removed `coordinator.slave_id` proxy; callers migrated to `coordinator.device_client.slave_id` |
| #1700 | Removed `coordinator.host`/`coordinator.port` proxies; deleted `coordinator/config_properties.py`; callers migrated to `coordinator.device_client.config.host`/`port` |
| #1701 | Aligned pydantic dev pin in `requirements-dev.txt` and `pyproject.toml` |
| #1702 | Updated `CHANGELOG.md`; added changelog policy to `claude.md` |

CI for the #1702 head commit was green. The changes affect code paths that run on every
coordinator refresh cycle. This checklist must be run against a real device before
real-device validation can be marked PASS for the post-#1702 codebase.

### 8.1 Checklist

> **Instructions:** Work through each item in order. Record the result (PASS / FAIL / N/A)
> and the evidence (log excerpt, HA screenshot filename, or "not tested") in the table.
> **Do not mark any item PASS without attaching HA log evidence or a screenshot.**

| # | Check | Expected result | Result | Evidence |
|---|-------|----------------|--------|----------|
| 1 | Restart or reload integration | Setup completes; `ThesslaGreen Modbus integration setup completed successfully` appears in HA log | — | — |
| 2 | No traceback during setup | No `Traceback`, `AttributeError`, or `ThesslaGreenModbusCoordinator` exception in HA log after reload | — | — |
| 3 | Entity count stable | Entity count in HA Developer Tools → Entities matches pre-cleanup baseline (≈367–370) | — | — |
| 4 | No duplicated entity IDs | No `Platform thessla_green_modbus does not generate unique IDs` warning in HA log | — | — |
| 5 | Device info still appears | HA → Devices → ThesslaGreen shows manufacturer, model (may be `Unknown` on legacy firmware), and connection info | — | — |
| 6 | `refresh_device_data` service works | Call `thessla_green_modbus.refresh_device_data` from HA Developer Tools → Services; no error, coordinator updates | — | — |
| 7 | `validate_known_registers` service works | Call `thessla_green_modbus.validate_known_registers`; result summary logged; no traceback | PARTIAL PASS | supported=338, missing=19 stable across 3 runs (PRs #1709/#1711); no transaction_id mismatch observed; missing registers classified via DEBUG output and service response |
| 8 | Diagnostics download works | HA → Devices → ThesslaGreen → Download Diagnostics; JSON file downloads without error; `config.host` and `config.port` fields present in JSON | — | — |
| 9 | Clock sync (if option enabled) | If clock-sync option is enabled in integration options, no `AttributeError` or crash for `coordinator.host`; clock sync log line present | — | N/A if option disabled |
| 10 | No `transaction_id` mismatch during refresh | No `transaction_id mismatch` line from `custom_components.thessla_green_modbus` in HA log during normal 30-second refresh cycle | — | — |
| 11 | No false "Modbus transport is not connected" during normal refresh | No `Modbus transport is not connected` error from integration during a clean refresh cycle (transport disconnect errors only during actual device-offline events are acceptable) | — | — |

### 8.2 Expected Notes (Not Failures)

- **Model Unknown** — `sensor.model` may read `Unknown` on AirPack4 devices running legacy
  firmware that does not expose model-version registers. This is not a regression introduced
  by PRs #1697–#1702.
- **Firmware Unknown** — `sensor.firmware` / `sw_version` in device info may read `Unknown`
  until the legacy-firmware fallback is implemented. This is a pre-existing known limitation.
- **`scan_all_registers` is not routine validation** — Do not use `scan_all_registers` as
  part of this checklist. Use `validate_known_registers` (item 7 above) instead.
  `scan_all_registers` opens a separate Modbus connection and is intended for development
  investigation only; see `claude.md §4`.
- **Deep scan (full_register_scan) is noisy and offline-only** — When the config-flow scan
  is run with `full_register_scan=True` (deep scan option), it sweeps all raw address ranges
  (e.g. input registers 0–286) in batches. Many of these raw addresses are unsupported by
  the device and return Modbus exception code 2. This is expected and produces hundreds of
  batch failures in diagnostic data (`batch_failures` field). These raw batch failures are
  NOT named-register Modbus errors: they are classified separately and shown only as a
  diagnostic note ("deep scan: N unsupported raw ranges (named registers OK)") in the
  config-flow confirmation, not as individual address error counts.
  Deep scan also opens a separate Modbus connection and can interfere with the active
  coordinator polling. It is intended for offline diagnostics / development investigation
  only; normal real-device validation should use `validate_known_registers` instead.

### 8.3 Validation Sign-off

This subsection must not be marked PASS until:

1. All checklist items in §8.1 that are applicable to the installed device have been
   completed with real HA log evidence or screenshot evidence attached or committed.
2. The HA Core version, integration commit SHA, and device host/port/slave_id used during
   validation are recorded in §2 (Environment).
3. A named tester has signed off below with the date and commit SHA tested.

**Tester sign-off:** _(pending)_
**HA Core version tested:** _(pending)_
**Integration commit SHA tested:** _(pending)_

---

## 7. Release Gate

Real-device validation is **not** complete until:

1. All test cases in section 3 are marked **Pass** with committed evidence.
2. The remaining evidence in section 4.2 is fully populated.
3. A named tester has signed off with the commit SHA actually installed in HA.

Until that point, quality_scale remains **bronze** and this document is **not a release sign-off**.

---

## 9. Targeted Read-back After Writes — Pending Real-Device Validation

This section tracks validation of the targeted read-back feature added in [Unreleased].

**Do not mark any item PASS without attached HA log evidence or a screenshot.**

### 9.1 How it works

After a successful write to a safe single holding register (e.g. `mode`,
`air_flow_rate_manual`, `special_mode`, `comfort_temperature`, `required_temperature`),
the coordinator immediately reads back only the written register under the same
`_write_lock`.  The decoded value is applied to `coordinator.data` and HA listeners
are notified via `async_set_updated_data` — without triggering a full register scan.
If the read-back fails, the coordinator falls back to a full refresh.

### 9.2 Excluded registers (full_refresh_only / no_readback)

- Reset/trigger: `hard_reset_settings`, `hard_reset_schedule`, `filter_change`,
  `airflow_rate_change_flag`, `temperature_change_flag`, `cfg_mode_1`, `cfg_mode_2`,
  `pres_check_day_2`, `pres_check_time_2`
- Schedule BCD-time registers: all `schedule_*`
- AATT schedule-setting registers: all `setting_*`
- Coil registers (function=1): no holding-register read-back
- Multi-word registers (e.g. `device_name`): full_refresh_only
- Fan setpoint registers: full_refresh_only (fan display reads from `supply_percentage`)

### 9.3 Real-device checklist

| # | Check | Expected result | Result | Evidence |
|---|-------|----------------|--------|----------|
| 1 | Restart HA with updated integration | Setup completes without traceback; no `AttributeError` or `ThesslaGreenModbusCoordinator` error in HA log | — | — |
| 2 | Change a safe switch entity (e.g. `switch.boost_mode`) | HA UI updates within one Modbus read-back round-trip (≪ 30 s); no full scan seen in logs immediately after | — | — |
| 3 | Change a number entity (e.g. `number.comfort_temperature`) | HA UI reflects new value quickly; no full scan seen in logs immediately after | — | — |
| 4 | Change a select entity (e.g. `select.mode`) | HA UI reflects new option quickly | — | — |
| 5 | Confirm no transaction_id mismatch during or after writes | No `transaction_id mismatch` line in HA log after write operations | — | — |
| 6 | Confirm no false "Modbus transport disconnected" errors | No false transport-disconnected error from integration after writes | — | — |
| 7 | Periodic full refresh still works after writes | Coordinator continues normal 30-second scans; all sensor values update | — | — |
| 8 | Call `reset_filters` or `reset_settings` service | Service succeeds; no targeted read-back attempted (confirm by no DEBUG read-back log line); full refresh follows if needed | — | — |
| 9 | Confirm fan percentage still updates after fan speed change | Fan entity percentage updates correctly after a speed change (full refresh still happens for fan) | — | — |
| 10 | Capture HA log lines showing targeted read-back and fallback | Confirm `Targeted read-back for <register> decoded to` and/or `Targeted read-back failed for <register>` lines appear at DEBUG level | — | — |

### 9.4 Sign-off

**Tester sign-off:** _(pending)_
**HA Core version tested:** _(pending)_
**Integration commit SHA tested:** _(pending)_
